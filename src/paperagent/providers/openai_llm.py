"""OpenAI-compatible real LLM provider.

The adapter intentionally avoids model-name branches. It accepts the common response
shapes emitted by OpenAI-compatible gateways, validates every result against the caller's
Pydantic schema, and uses a bounded fallback/repair sequence when structured output is
not natively supported or a model wraps otherwise valid JSON in prose or content blocks.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from paperagent.errors import ProviderError, ProviderTimeoutError
from paperagent.pricing import PriceTable
from paperagent.providers.request_rate_limit import shared_request_rate_limiter
from paperagent.providers.runtime import TaskBudget, UsageRecord
from paperagent.providers.structured_output import (
    StructuredOutputFailure,
    validate_structured_response,
)
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)

_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)
_RATE_LIMIT_BACKOFF_SECONDS: tuple[float, ...] = (15.0, 30.0, 60.0)
_MAX_RETRY_AFTER_SECONDS = 300.0
_MAX_REPAIR_SOURCE_CHARS = 12_000
_STRUCTURED_OUTPUT_ERROR_CODES = {
    "LLM_RESPONSE_JSON_INVALID",
    "LLM_RESPONSE_SCHEMA_INVALID",
}


class _StructuredProviderError(ProviderError):
    def __init__(self, message: str, *, task: str, code: str, raw_output: str | None) -> None:
        super().__init__(
            message,
            provider="openai",
            task=task,
            retryable=False,
            code=code,
        )
        self.raw_output = raw_output


class OpenAILLMProvider:
    """Async provider for OpenAI Chat Completions compatible endpoints."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        connect_timeout_seconds: float | None = None,
        read_timeout_seconds: float | None = None,
        max_retries: int = 2,
        max_requests_per_minute: int | None = None,
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        native_json_schema: bool = True,
        allow_schema_repair: bool = True,
        budget: TaskBudget | None = None,
        price_table: PriceTable | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must be a non-empty string")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if connect_timeout_seconds is not None and connect_timeout_seconds <= 0:
            raise ValueError("connect_timeout_seconds must be positive")
        if read_timeout_seconds is not None and read_timeout_seconds <= 0:
            raise ValueError("read_timeout_seconds must be positive")
        if max_output_tokens is not None and max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be positive")
        if max_requests_per_minute is not None and max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be positive")

        connect_timeout = connect_timeout_seconds or timeout_seconds
        read_timeout = read_timeout_seconds or timeout_seconds

        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._total_timeout_seconds = timeout_seconds
        self._http_timeout = httpx.Timeout(
            timeout=timeout_seconds,
            connect=connect_timeout,
            read=read_timeout,
            write=timeout_seconds,
            pool=connect_timeout,
        )
        self._max_retries = max_retries
        self._max_requests_per_minute = max_requests_per_minute
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._native_json_schema = native_json_schema
        self._allow_schema_repair = allow_schema_repair
        self._budget = budget
        self._price_table = price_table
        self.last_usage: TokenUsage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms: int = 0

    @property
    def model_name(self) -> str:
        return self._model

    def _build_response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": schema.model_json_schema(),
                "strict": False,
            },
        }

    @staticmethod
    def _messages_to_openai(messages: list[Message]) -> list[dict[str, str]]:
        return [{"role": msg.role, "content": msg.content} for msg in messages]

    def _base_payload(self, messages: list[Message]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages_to_openai(messages),
            "temperature": self._temperature,
        }
        if self._max_output_tokens is not None:
            payload["max_tokens"] = self._max_output_tokens
        return payload

    def _record_usage(self, response: httpx.Response) -> None:
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            self.last_usage = TokenUsage(input_tokens=0, output_tokens=0)
            return
        usage = body.get("usage") or {}
        self.last_usage = TokenUsage(
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
        )

    def _parse_response(self, response: httpx.Response, schema: type[T], task: str) -> T:
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            raw = response.text[:_MAX_REPAIR_SOURCE_CHARS] if response.text else None
            raise _StructuredProviderError(
                "response body is not valid JSON",
                task=task,
                code="LLM_RESPONSE_JSON_INVALID",
                raw_output=raw,
            ) from exc

        try:
            return validate_structured_response(body, schema)
        except StructuredOutputFailure as exc:
            raise _StructuredProviderError(
                exc.message,
                task=task,
                code=exc.code,
                raw_output=exc.raw_output,
            ) from exc

    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T:
        del scenario, call_index, fixture_version
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"
        native_error: _StructuredProviderError | None = None

        if self._native_json_schema:
            payload = self._base_payload(messages)
            payload["response_format"] = self._build_response_format(schema)
            try:
                return await self._post_with_retries(
                    url=url,
                    payload=payload,
                    headers=headers,
                    schema=schema,
                    task=task,
                )
            except _StructuredProviderError as exc:
                native_error = exc
            except ProviderError as exc:
                if exc.code != "LLM_RESPONSE_FORMAT_UNSUPPORTED":
                    raise

        fallback_messages = self._augment_messages_with_schema(messages, schema)
        fallback_payload = self._base_payload(fallback_messages)
        try:
            return await self._post_with_retries(
                url=url,
                payload=fallback_payload,
                headers=headers,
                schema=schema,
                task=task,
            )
        except _StructuredProviderError as fallback_error:
            if not self._allow_schema_repair:
                raise
            raw_output = fallback_error.raw_output or (
                native_error.raw_output if native_error is not None else None
            )
            if not raw_output:
                raise
            repair_payload = self._base_payload(
                self._repair_messages(raw_output=raw_output, schema=schema)
            )
            return await self._post_with_retries(
                url=url,
                payload=repair_payload,
                headers=headers,
                schema=schema,
                task=f"{task}:schema-repair",
            )

    @staticmethod
    def _augment_messages_with_schema(
        messages: list[Message], schema: type[BaseModel]
    ) -> list[Message]:
        """Append a portable JSON-only instruction for providers without json_schema."""
        if not messages:
            return messages
        schema_hint = (
            "\n\n--- JSON SCHEMA (follow these field names exactly) ---\n"
            + json.dumps(schema.model_json_schema(), indent=2, ensure_ascii=False)
            + "\n--- END SCHEMA ---\n"
            "Return ONLY one JSON object that validates against this schema. "
            "Do not include markdown fences, prose, comments, or reasoning."
        )
        augmented = list(messages)
        last = augmented[-1]
        augmented[-1] = Message(role=last.role, content=last.content + schema_hint)
        return augmented

    @staticmethod
    def _repair_messages(*, raw_output: str, schema: type[BaseModel]) -> list[Message]:
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        clipped = raw_output[:_MAX_REPAIR_SOURCE_CHARS]
        return [
            Message(
                role="system",
                content=(
                    "You are a deterministic structured-output repair function. "
                    "Preserve the source meaning, remove prose and markdown, correct only "
                    "syntax or schema-shape defects, and return exactly one JSON object."
                ),
            ),
            Message(
                role="user",
                content=(
                    f"Required JSON Schema:\n{schema_json}\n\n"
                    f"Invalid provider output:\n{clipped}\n\n"
                    "Return only the repaired JSON object. Do not add facts."
                ),
            ),
        ]

    async def _post_with_retries(
        self,
        *,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str],
        schema: type[T],
        task: str,
    ) -> T:
        attempts = self._max_retries + 1

        for attempt in range(attempts):
            if self._budget is not None:
                self._budget.reserve_call(task=task)
            if self._max_requests_per_minute is not None:
                limiter = shared_request_rate_limiter(
                    namespace=f"{self._base_url}|{self._model}",
                    requests_per_minute=self._max_requests_per_minute,
                )
                await limiter.acquire()
            started = time.perf_counter()
            try:
                async with asyncio.timeout(self._total_timeout_seconds):
                    async with httpx.AsyncClient(timeout=self._http_timeout) as client:
                        response = await client.post(url, json=payload, headers=headers)
                        response.raise_for_status()
                self.last_latency_ms = int((time.perf_counter() - started) * 1000)
                self._record_usage(response)
                if self._budget is not None:
                    estimated_cost = (
                        self._price_table.estimate(
                            model=self._model,
                            input_tokens=self.last_usage.input_tokens,
                            output_tokens=self.last_usage.output_tokens,
                        )
                        if self._price_table is not None
                        else None
                    )
                    self._budget.record_usage(
                        UsageRecord(
                            input_tokens=self.last_usage.input_tokens,
                            output_tokens=self.last_usage.output_tokens,
                            estimated_cost_usd=estimated_cost,
                        ),
                        task=task,
                    )
                return self._parse_response(response, schema, task)
            except (TimeoutError, httpx.TimeoutException) as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                raise ProviderTimeoutError(
                    provider=self.provider_name,
                    task=task,
                    retryable=True,
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status == 400 and self._is_response_format_error(exc.response):
                    raise ProviderError(
                        f"{self.provider_name} rejected response_format (HTTP 400)",
                        provider=self.provider_name,
                        task=task,
                        retryable=False,
                        code="LLM_RESPONSE_FORMAT_UNSUPPORTED",
                    ) from exc
                code, retryable = self._classify_http_status(status)
                if retryable and attempt < self._max_retries:
                    await asyncio.sleep(self._http_retry_delay(exc.response, attempt))
                    continue
                raise ProviderError(
                    f"HTTP {status} from {self.provider_name}",
                    provider=self.provider_name,
                    task=task,
                    retryable=retryable,
                    code=code,
                ) from exc
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay(attempt))
                    continue
                raise ProviderError(
                    f"transport error from {self.provider_name}: {exc}",
                    provider=self.provider_name,
                    task=task,
                    retryable=True,
                    code="LLM_CONNECT",
                ) from exc

        raise ProviderError(
            f"exhausted retries for {self.provider_name}",
            provider=self.provider_name,
            task=task,
            retryable=True,
            code="LLM_PROVIDER_HTTP_ERROR",
        )

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        return _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]

    @classmethod
    def _http_retry_delay(cls, response: httpx.Response, attempt: int) -> float:
        if response.status_code != 429:
            return cls._retry_delay(attempt)
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                parsed = float(retry_after)
            except ValueError:
                parsed = -1.0
            if parsed >= 0:
                return min(parsed, _MAX_RETRY_AFTER_SECONDS)
        return _RATE_LIMIT_BACKOFF_SECONDS[min(attempt, len(_RATE_LIMIT_BACKOFF_SECONDS) - 1)]

    @staticmethod
    def _classify_http_status(status: int) -> tuple[str, bool]:
        if status == 401:
            return "LLM_AUTHENTICATION", False
        if status == 403:
            return "LLM_PERMISSION", False
        if status == 404:
            return "LLM_CONFIGURATION", False
        if status == 429:
            return "LLM_RATE_LIMITED", True
        if 500 <= status < 600:
            return "LLM_PROVIDER_5XX", True
        if status in {400, 409, 415, 422}:
            return "LLM_INVALID_REQUEST", False
        return "LLM_PROVIDER_HTTP_ERROR", False

    @staticmethod
    def _is_response_format_error(response: httpx.Response) -> bool:
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            return False
        error = body.get("error") or {}
        message = str(error.get("message") or "").lower()
        err_type = str(error.get("type") or "").lower()
        if "response_format" in message or "json_schema" in message:
            return True
        return bool(err_type == "invalid_request_error" and error.get("param") is None)


__all__ = ["OpenAILLMProvider"]

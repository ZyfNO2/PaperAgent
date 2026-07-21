"""OpenAI-compatible real LLM provider.

Implements the :class:`paperagent.providers.base.LLMProvider` protocol against the
OpenAI Chat Completions API using ``httpx`` for async transport. Structured outputs
are requested via ``response_format={"type": "json_schema", ...}`` when enabled and
validated against the supplied Pydantic schema. Providers that reject native JSON
Schema automatically fall back to a schema-augmented plain chat request.

This provider is intentionally offline-safe to import: no network access happens
until :meth:`OpenAILLMProvider.generate_structured` is awaited.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from paperagent.errors import ProviderError, ProviderTimeoutError
from paperagent.pricing import PriceTable
from paperagent.providers.runtime import TaskBudget, UsageRecord
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)

_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)
_RATE_LIMIT_BACKOFF_SECONDS: tuple[float, ...] = (15.0, 30.0, 60.0)
_MAX_RETRY_AFTER_SECONDS = 300.0


class OpenAILLMProvider:
    """Async OpenAI-compatible Chat Completions provider."""

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
        temperature: float = 0.0,
        max_output_tokens: int | None = None,
        native_json_schema: bool = True,
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
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._native_json_schema = native_json_schema
        self._budget = budget
        self._price_table = price_table
        self.last_usage: TokenUsage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms: int = 0

    @property
    def model_name(self) -> str:
        return self._model

    def _build_response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        json_schema = schema.model_json_schema()
        return {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "schema": json_schema,
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
            raise ProviderError(
                "response body is not valid JSON",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_JSON_INVALID",
            ) from exc
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "response missing choices[0].message.content",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_JSON_INVALID",
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError(
                "response content is empty or not a string",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_JSON_INVALID",
            )

        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 2 and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            stripped = "\n".join(lines).strip()
        try:
            parsed: Any = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "response content is not valid JSON",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_JSON_INVALID",
            ) from exc
        try:
            return schema.model_validate(parsed)
        except ValidationError as exc:
            raise ProviderError(
                "response failed schema validation",
                provider=self.provider_name,
                task=task,
                retryable=False,
                code="LLM_RESPONSE_SCHEMA_INVALID",
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
            except ProviderError as exc:
                if exc.code != "LLM_RESPONSE_FORMAT_UNSUPPORTED":
                    raise

        fallback_messages = self._augment_messages_with_schema(messages, schema)
        fallback_payload = self._base_payload(fallback_messages)
        return await self._post_with_retries(
            url=url,
            payload=fallback_payload,
            headers=headers,
            schema=schema,
            task=task,
        )

    @staticmethod
    def _augment_messages_with_schema(
        messages: list[Message], schema: type[BaseModel]
    ) -> list[Message]:
        """Append the JSON Schema to the final message for plain-chat fallback."""
        if not messages:
            return messages
        json_schema = schema.model_json_schema()
        schema_hint = (
            "\n\n--- JSON SCHEMA (follow these field names exactly) ---\n"
            + json.dumps(json_schema, indent=2, ensure_ascii=False)
            + "\n--- END SCHEMA ---\n"
            "Return ONLY a JSON object that validates against this schema. "
            "Do not include markdown fences, prose, or explanations."
        )
        augmented = list(messages)
        last = augmented[-1]
        augmented[-1] = Message(role=last.role, content=last.content + schema_hint)
        return augmented

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

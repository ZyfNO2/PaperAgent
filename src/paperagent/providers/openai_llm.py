"""OpenAI-compatible real LLM provider.

Implements the :class:`paperagent.providers.base.LLMProvider` protocol against the
OpenAI Chat Completions API using ``httpx`` for async transport. Structured outputs
are requested via ``response_format={"type": "json_schema", ...}`` and the returned
JSON is validated against the supplied Pydantic schema.

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

# Exponential backoff schedule (seconds) for retryable HTTP errors (429 / 5xx).
# Only the first ``max_retries`` entries are consumed.
_RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0, 2.0)


class OpenAILLMProvider:
    """Async OpenAI-compatible Chat Completions provider with structured outputs."""

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        temperature: float = 0.0,
        budget: TaskBudget | None = None,
        price_table: PriceTable | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must be a non-empty string")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._temperature = temperature
        self._budget = budget
        self._price_table = price_table
        # Last-call observability, mirrored on FakeLLMProvider for node telemetry.
        self.last_usage: TokenUsage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms: int = 0

    @property
    def model_name(self) -> str:
        return self._model

    def _build_response_format(self, schema: type[BaseModel]) -> dict[str, Any]:
        # Pydantic v2 model_json_schema may emit $defs for nested models; OpenAI
        # structured outputs accepts $defs and $ref when strict=False.
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
        # Strip markdown fences (```json ... ``` or ``` ... ```) that some models
        # add despite instructions not to. This only runs on the fallback path
        # (when response_format is rejected), but is safe for all paths.
        stripped = content.strip()
        if stripped.startswith("```"):
            # Remove the opening fence line (with optional language tag) and the
            # closing fence line, keeping the JSON body in between.
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
        del scenario, call_index, fixture_version  # unused: real provider ignores fixture keys
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages_to_openai(messages),
            "temperature": self._temperature,
            "response_format": self._build_response_format(schema),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/chat/completions"

        try:
            return await self._post_with_retries(
                url=url, payload=payload, headers=headers, schema=schema, task=task
            )
        except ProviderError as exc:
            # Some OpenAI-compatible providers (e.g. DeepSeek via proxies) reject
            # response_format={"type":"json_schema",...} with HTTP 400
            # invalid_request_error even though they honour the system prompt's
            # "Return only JSON" instruction. Fall back to a plain chat request
            # that embeds the JSON Schema in the user message so the model knows
            # the exact field names, then validate client-side.
            if exc.code != "LLM_RESPONSE_FORMAT_UNSUPPORTED":
                raise
        fallback_messages = self._augment_messages_with_schema(messages, schema)
        fallback_payload: dict[str, Any] = {
            "model": self._model,
            "messages": self._messages_to_openai(fallback_messages),
            "temperature": self._temperature,
        }
        return await self._post_with_retries(
            url=url, payload=fallback_payload, headers=headers, schema=schema, task=task
        )

    @staticmethod
    def _augment_messages_with_schema(
        messages: list[Message], schema: type[BaseModel]
    ) -> list[Message]:
        """Append the JSON Schema to the last user message on the fallback path.

        When response_format is rejected by the provider, the model has no way
        to discover the exact field names (e.g. gap_id vs id, status vs
        assessment) from the system prompt alone. Embedding the schema's
        properties and required keys in the user message gives the model a
        precise contract without forcing it to guess.
        """
        if not messages:
            return messages
        json_schema = schema.model_json_schema()
        # Keep the schema compact: properties + required + $defs is enough for
        # the model to produce correctly-named fields. Full JSON Schema is
        # verbose but models handle it well in practice.
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
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
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
            except httpx.TimeoutException as exc:
                raise ProviderTimeoutError(
                    provider=self.provider_name,
                    task=task,
                    retryable=True,
                ) from exc
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                # Detect "response_format not supported" so the caller can fall
                # back to a plain chat request. OpenAI-compatible providers
                # typically return 400 with invalid_request_error for unsupported
                # response_format shapes; surface a dedicated code for this.
                if status == 400 and self._is_response_format_error(exc.response):
                    raise ProviderError(
                        f"{self.provider_name} rejected response_format (HTTP 400)",
                        provider=self.provider_name,
                        task=task,
                        retryable=False,
                        code="LLM_RESPONSE_FORMAT_UNSUPPORTED",
                    ) from exc
                retryable_status = status == 429 or 500 <= status < 600
                if retryable_status and attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                    await asyncio.sleep(delay)
                    continue
                raise ProviderError(
                    f"HTTP {status} from {self.provider_name}",
                    provider=self.provider_name,
                    task=task,
                    retryable=retryable_status,
                    code="LLM_PROVIDER_HTTP_ERROR",
                ) from exc
            except httpx.RequestError as exc:
                # Transport-level failures (connect/read errors, proxy drops,
                # RemoteProtocolError "Server disconnected without sending a
                # response"). These are often transient on flaky proxy links,
                # so retry with backoff before surfacing to the node layer.
                if attempt < self._max_retries:
                    delay = _RETRY_BACKOFF_SECONDS[min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)]
                    await asyncio.sleep(delay)
                    continue
                raise ProviderError(
                    f"transport error from {self.provider_name}: {exc}",
                    provider=self.provider_name,
                    task=task,
                    retryable=True,
                    code="LLM_PROVIDER_HTTP_ERROR",
                ) from exc

        # Unreachable: the loop either returns on success or raises on every
        # terminal branch. Kept for exhaustiveness.
        raise ProviderError(
            f"exhausted retries for {self.provider_name}",
            provider=self.provider_name,
            task=task,
            retryable=True,
            code="LLM_PROVIDER_HTTP_ERROR",
        )

    @staticmethod
    def _is_response_format_error(response: httpx.Response) -> bool:
        """Heuristic: does this 400 body indicate response_format is unsupported?

        OpenAI-compatible providers return varied error shapes. We treat any 400
        whose body mentions ``response_format`` or the generic
        ``invalid_request_error`` type (when response_format is the only
        non-standard field in the request) as a signal to retry without it. The
        fallback path is safe: if the model still cannot produce JSON, the
        downstream _parse_response will raise LLM_RESPONSE_JSON_INVALID.
        """
        try:
            body = response.json()
        except (ValueError, json.JSONDecodeError):
            return False
        error = body.get("error") or {}
        message = str(error.get("message") or "").lower()
        err_type = str(error.get("type") or "").lower()
        if "response_format" in message:
            return True
        # DeepSeek-via-proxy shape: {"error":{"type":"invalid_request_error",
        # "message":"Error from provider (Console Go): Upstream request failed"}}
        # Only treat as response_format error when the request actually carried
        # response_format (the caller already knows that) AND the body has the
        # invalid_request_error type without a more specific param.
        return bool(err_type == "invalid_request_error" and error.get("param") is None)

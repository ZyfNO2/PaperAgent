from __future__ import annotations

import asyncio
import hashlib
import json
from typing import TypeVar
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from paperagent.providers.base import LLMProvider
from paperagent.providers.runtime import (
    InvocationTelemetry,
    ProviderError,
    ProviderErrorCode,
    ProviderRuntimeConfig,
    TaskBudget,
    TelemetrySink,
    UsageRecord,
)
from paperagent.schemas import Message

T = TypeVar("T", bound=BaseModel)


class MistralLLMProvider(LLMProvider):
    def __init__(
        self,
        config: ProviderRuntimeConfig,
        *,
        client: httpx.AsyncClient | None = None,
        telemetry: TelemetrySink | None = None,
        budget: TaskBudget | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._telemetry = telemetry or TelemetrySink()
        self._budget = budget or TaskBudget(config)

    @property
    def telemetry(self) -> TelemetrySink:
        return self._telemetry

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
        del scenario, fixture_version
        logical_call_id = uuid4().hex
        prompt_payload = [message.model_dump(mode="json") for message in messages]
        prompt_fingerprint = _fingerprint(prompt_payload)
        validation_error: ValidationError | None = None

        attempts = self._config.max_attempts
        for attempt in range(1, attempts + 1):
            self._budget.reserve_call()
            invocation_id = uuid4().hex
            started = asyncio.get_running_loop().time()
            response_fingerprint: str | None = None
            try:
                response_payload = await self._request(
                    schema=schema,
                    messages=prompt_payload,
                )
                response_fingerprint = _fingerprint(response_payload)
                content, usage = _extract_content_and_usage(response_payload)
                self._budget.record_usage(usage)
                try:
                    parsed = schema.model_validate_json(content)
                except ValidationError as exc:
                    validation_error = exc
                    raise ProviderError(
                        ProviderErrorCode.SCHEMA_VALIDATION,
                        "provider output failed schema validation",
                        retryable=self._config.allow_schema_repair and attempt < attempts,
                    ) from exc
                self._emit(
                    task=task,
                    call_index=call_index,
                    schema=schema,
                    logical_call_id=logical_call_id,
                    invocation_id=invocation_id,
                    attempt=attempt,
                    started=started,
                    usage=usage,
                    outcome="success",
                    error_code=None,
                    prompt_fingerprint=prompt_fingerprint,
                    response_fingerprint=response_fingerprint,
                )
                return parsed
            except ProviderError as exc:
                self._emit(
                    task=task,
                    call_index=call_index,
                    schema=schema,
                    logical_call_id=logical_call_id,
                    invocation_id=invocation_id,
                    attempt=attempt,
                    started=started,
                    usage=UsageRecord(),
                    outcome="error",
                    error_code=exc.code,
                    prompt_fingerprint=prompt_fingerprint,
                    response_fingerprint=response_fingerprint,
                )
                if not exc.retryable or attempt >= attempts:
                    raise
                await asyncio.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))

        if validation_error is not None:
            raise ProviderError(
                ProviderErrorCode.SCHEMA_VALIDATION,
                "provider output failed schema validation after repair",
            ) from validation_error
        raise ProviderError(ProviderErrorCode.UNKNOWN, "provider call failed without a result")

    async def _request(
        self,
        *,
        schema: type[BaseModel],
        messages: list[dict[str, object]],
    ) -> dict[str, object]:
        request = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        }
        headers = {
            "Authorization": f"Bearer {self._config.api_key.get_secret_value()}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=self._config.connect_timeout_seconds,
            read=self._config.read_timeout_seconds,
            write=self._config.total_timeout_seconds,
            pool=self._config.total_timeout_seconds,
        )
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout)
        try:
            response = await client.post(
                f"{self._config.base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=request,
            )
        except httpx.ConnectError as exc:
            raise ProviderError(
                ProviderErrorCode.CONNECT,
                "failed to connect to Mistral",
                retryable=True,
            ) from exc
        except httpx.ReadTimeout as exc:
            raise ProviderError(
                ProviderErrorCode.READ_TIMEOUT,
                "Mistral response timed out",
                retryable=False,
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code in {401}:
            raise ProviderError(
                ProviderErrorCode.AUTHENTICATION,
                "Mistral authentication failed",
                status_code=response.status_code,
            )
        if response.status_code in {403}:
            raise ProviderError(
                ProviderErrorCode.PERMISSION,
                "Mistral permission denied",
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                "Mistral rate limit exceeded",
                retryable=True,
                status_code=response.status_code,
            )
        if 500 <= response.status_code <= 599:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_5XX,
                "Mistral returned a server error",
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "Mistral rejected the request",
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Mistral returned non-JSON content",
            ) from exc
        if not isinstance(data, dict):
            raise ProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Mistral returned an invalid response envelope",
            )
        return data

    def _emit(
        self,
        *,
        task: str,
        call_index: int,
        schema: type[BaseModel],
        logical_call_id: str,
        invocation_id: str,
        attempt: int,
        started: float,
        usage: UsageRecord,
        outcome: str,
        error_code: ProviderErrorCode | None,
        prompt_fingerprint: str,
        response_fingerprint: str | None,
    ) -> None:
        if not self._config.telemetry_enabled:
            return
        latency = max(asyncio.get_running_loop().time() - started, 0.0)
        self._telemetry.emit(
            InvocationTelemetry(
                provider=self._config.provider,
                model=self._config.model,
                logical_call_id=logical_call_id,
                invocation_id=invocation_id,
                task=task,
                call_index=call_index,
                schema_name=schema.__name__,
                attempt=attempt,
                latency_seconds=latency,
                usage=usage,
                outcome=outcome,
                error_code=error_code,
                prompt_fingerprint=prompt_fingerprint,
                response_fingerprint=response_fingerprint,
            )
        )


def _extract_content_and_usage(payload: dict[str, object]) -> tuple[str, UsageRecord]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response has no choices",
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response choice is invalid",
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response message is invalid",
        )
    content = message.get("content")
    if not isinstance(content, str):
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response content is not text",
        )
    usage_payload = payload.get("usage")
    if not isinstance(usage_payload, dict):
        return content, UsageRecord()
    prompt_tokens = usage_payload.get("prompt_tokens")
    completion_tokens = usage_payload.get("completion_tokens")
    return content, UsageRecord(
        input_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        output_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
    )


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from paperagent.pricing import PriceTable
from paperagent.providers.base import FixtureKey, LLMProvider
from paperagent.providers.runtime import (
    InvocationTelemetry,
    ProviderError,
    ProviderErrorCode,
    ProviderRuntimeConfig,
    TaskBudget,
    TelemetrySink,
    UsageRecord,
)
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class MistralLLMCall:
    key: FixtureKey
    message_count: int
    schema_name: str
    logical_call_id: str


class MistralLLMProvider(LLMProvider):
    provider_name = "mistral"

    def __init__(
        self,
        config: ProviderRuntimeConfig,
        *,
        client: httpx.AsyncClient | None = None,
        telemetry: TelemetrySink | None = None,
        budget: TaskBudget | None = None,
        price_table: PriceTable | None = None,
    ) -> None:
        self._config = config
        self._client = client
        self._telemetry = telemetry or TelemetrySink()
        self._budget = budget or TaskBudget(config)
        self._price_table = price_table
        self.model_name = config.model
        self.calls: list[MistralLLMCall] = []
        self.last_usage = TokenUsage()
        self.last_latency_ms: int | None = None

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
        if not self._config.native_json_schema:
            raise ProviderError(
                ProviderErrorCode.UNSUPPORTED_SCHEMA,
                "native JSON-schema mode is required by the v0.6 provider contract",
                task=task,
            )

        logical_call_id = uuid4().hex
        key = FixtureKey(
            task=task,
            scenario=scenario,
            call_index=call_index,
            fixture_version=fixture_version,
        )
        self.calls.append(
            MistralLLMCall(
                key=key,
                message_count=len(messages),
                schema_name=schema.__name__,
                logical_call_id=logical_call_id,
            )
        )
        base_messages = [message.model_dump(mode="json") for message in messages]
        prompt_fingerprint = _fingerprint(base_messages)
        repair_instruction: str | None = None
        validation_error: ValidationError | None = None

        for attempt in range(1, self._config.max_attempts + 1):
            self._budget.reserve_call(task=task)
            invocation_id = uuid4().hex
            started = asyncio.get_running_loop().time()
            response_fingerprint: str | None = None
            usage = UsageRecord()
            attempt_messages: list[dict[str, object]] = list(base_messages)
            if repair_instruction is not None:
                attempt_messages.append({"role": "user", "content": repair_instruction})
            try:
                try:
                    async with asyncio.timeout(self._config.total_timeout_seconds):
                        response_payload = await self._request(
                            task=task,
                            schema=schema,
                            messages=attempt_messages,
                        )
                except TimeoutError as exc:
                    raise ProviderError(
                        ProviderErrorCode.READ_TIMEOUT,
                        "Mistral call exceeded the total timeout",
                        task=task,
                        retryable=False,
                    ) from exc

                response_fingerprint = _fingerprint(response_payload)
                content, usage = _extract_content_and_usage(response_payload, task=task)
                usage = self._with_estimated_cost(usage)
                self._budget.record_usage(usage, task=task)
                self.last_usage = TokenUsage(
                    input_tokens=usage.input_tokens or 0,
                    output_tokens=usage.output_tokens or 0,
                )
                try:
                    parsed = schema.model_validate_json(content)
                except ValidationError as exc:
                    validation_error = exc
                    can_repair = (
                        self._config.allow_schema_repair and attempt < self._config.max_attempts
                    )
                    if can_repair:
                        repair_instruction = _repair_instruction(schema, exc)
                    raise ProviderError(
                        ProviderErrorCode.SCHEMA_VALIDATION,
                        "provider output failed schema validation",
                        task=task,
                        retryable=can_repair,
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
                    usage=usage,
                    outcome="error",
                    error_code=exc.error_code,
                    prompt_fingerprint=prompt_fingerprint,
                    response_fingerprint=response_fingerprint,
                )
                if not exc.retryable or attempt >= self._config.max_attempts:
                    raise
                await asyncio.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))

        if validation_error is not None:
            raise ProviderError(
                ProviderErrorCode.SCHEMA_VALIDATION,
                "provider output failed schema validation after repair",
                task=task,
            ) from validation_error
        raise ProviderError(
            ProviderErrorCode.UNKNOWN,
            "provider call failed without a result",
            task=task,
        )

    async def _request(
        self,
        *,
        task: str,
        schema: type[BaseModel],
        messages: list[dict[str, object]],
    ) -> dict[str, object]:
        request = {
            "model": self._config.model,
            "messages": messages,
            "max_tokens": self._config.max_output_tokens_per_call,
            "temperature": 0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(schema),
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
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as exc:
            raise ProviderError(
                ProviderErrorCode.CONNECT,
                "failed to connect to Mistral",
                task=task,
                retryable=True,
            ) from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout) as exc:
            raise ProviderError(
                ProviderErrorCode.READ_TIMEOUT,
                "Mistral request timed out after it may have been processed",
                task=task,
                retryable=False,
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        if response.status_code == 401:
            raise ProviderError(
                ProviderErrorCode.AUTHENTICATION,
                "Mistral authentication failed",
                task=task,
                status_code=response.status_code,
            )
        if response.status_code == 403:
            raise ProviderError(
                ProviderErrorCode.PERMISSION,
                "Mistral permission denied",
                task=task,
                status_code=response.status_code,
            )
        if response.status_code == 429:
            raise ProviderError(
                ProviderErrorCode.RATE_LIMITED,
                "Mistral rate limit exceeded",
                task=task,
                retryable=True,
                status_code=response.status_code,
            )
        if 500 <= response.status_code <= 599:
            raise ProviderError(
                ProviderErrorCode.PROVIDER_5XX,
                "Mistral returned a server error",
                task=task,
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ProviderError(
                ProviderErrorCode.INVALID_REQUEST,
                "Mistral rejected the request",
                task=task,
                status_code=response.status_code,
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Mistral returned non-JSON content",
                task=task,
            ) from exc
        if not isinstance(data, dict):
            raise ProviderError(
                ProviderErrorCode.MALFORMED_RESPONSE,
                "Mistral returned an invalid response envelope",
                task=task,
            )
        return data

    def _with_estimated_cost(self, usage: UsageRecord) -> UsageRecord:
        if self._price_table is None:
            return usage
        estimated = self._price_table.estimate(
            model=self._config.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
        )
        return usage.model_copy(update={"estimated_cost_usd": estimated})

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
        latency = max(asyncio.get_running_loop().time() - started, 0.0)
        self.last_latency_ms = round(latency * 1000)
        if not self._config.telemetry_enabled:
            return
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


def _extract_content_and_usage(payload: dict[str, object], *, task: str) -> tuple[str, UsageRecord]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response has no choices",
            task=task,
        )
    first = choices[0]
    if not isinstance(first, dict):
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response choice is invalid",
            task=task,
        )
    message = first.get("message")
    if not isinstance(message, dict):
        raise ProviderError(
            ProviderErrorCode.MALFORMED_RESPONSE,
            "Mistral response message is invalid",
            task=task,
        )
    content = _text_content(message.get("content"), task=task)
    usage_payload = payload.get("usage")
    if not isinstance(usage_payload, dict):
        return content, UsageRecord()
    prompt_tokens = usage_payload.get("prompt_tokens")
    completion_tokens = usage_payload.get("completion_tokens")
    return content, UsageRecord(
        input_tokens=prompt_tokens if isinstance(prompt_tokens, int) else None,
        output_tokens=completion_tokens if isinstance(completion_tokens, int) else None,
    )


def _text_content(value: object, *, task: str) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        chunks: list[str] = []
        for chunk in value:
            if not isinstance(chunk, dict) or chunk.get("type") != "text":
                raise ProviderError(
                    ProviderErrorCode.MALFORMED_RESPONSE,
                    "Mistral structured response contains a non-text content chunk",
                    task=task,
                )
            text = chunk.get("text")
            if not isinstance(text, str):
                raise ProviderError(
                    ProviderErrorCode.MALFORMED_RESPONSE,
                    "Mistral text content chunk is invalid",
                    task=task,
                )
            chunks.append(text)
        return "".join(chunks)
    raise ProviderError(
        ProviderErrorCode.MALFORMED_RESPONSE,
        "Mistral response content is not text",
        task=task,
    )


def _repair_instruction(schema: type[BaseModel], error: ValidationError) -> str:
    errors: list[dict[str, Any]] = []
    for item in error.errors(include_input=False, include_url=False):
        errors.append(
            {
                "location": [str(part) for part in item.get("loc", ())],
                "type": item.get("type"),
                "message": item.get("msg"),
            }
        )
    payload = {
        "instruction": "Return a corrected JSON object only. Do not add prose or markdown.",
        "schema": schema.model_json_schema(),
        "validation_errors": errors,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _schema_name(schema: type[BaseModel]) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in schema.__name__)
    return (normalized or "paperagent_output")[:64]


def _fingerprint(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

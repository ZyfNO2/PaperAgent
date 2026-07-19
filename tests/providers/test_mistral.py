from __future__ import annotations

import json

import httpx
import pytest
from pydantic import BaseModel, ConfigDict, SecretStr

from paperagent.providers.mistral import MistralLLMProvider
from paperagent.providers.runtime import (
    ProviderError,
    ProviderErrorCode,
    ProviderRuntimeConfig,
)
from paperagent.schemas import Message


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


def make_provider(
    handler: httpx.MockTransport,
    **config_overrides: object,
) -> tuple[MistralLLMProvider, httpx.AsyncClient]:
    values: dict[str, object] = {
        "model": "test-model",
        "api_key": SecretStr("test-secret"),
        "max_attempts": 2,
    }
    values.update(config_overrides)
    config = ProviderRuntimeConfig.model_validate(values)
    client = httpx.AsyncClient(transport=handler)
    return MistralLLMProvider(config, client=client), client


@pytest.mark.asyncio
async def test_mistral_returns_strict_structured_output() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["temperature"] == 0
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":"grounded"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    provider, client = make_provider(httpx.MockTransport(handle))
    try:
        result = await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="Return an answer")],
        )
    finally:
        await client.aclose()

    assert result == ExampleOutput(answer="grounded")
    assert len(provider.calls) == 1
    assert provider.calls[0].key.task == "report"
    assert provider.last_usage.input_tokens == 10
    assert provider.last_latency_ms is not None
    assert len(provider.telemetry.records) == 1
    assert provider.telemetry.records[0].usage.input_tokens == 10


@pytest.mark.asyncio
async def test_authentication_failure_is_not_retried() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"message": "invalid key"})

    provider, client = make_provider(httpx.MockTransport(handle))
    try:
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate_structured(
                task="report",
                scenario="live",
                call_index=0,
                fixture_version="v0.1",
                schema=ExampleOutput,
                messages=[Message(role="user", content="Return an answer")],
            )
    finally:
        await client.aclose()

    assert exc_info.value.error_code is ProviderErrorCode.AUTHENTICATION
    assert exc_info.value.code == "LLM_AUTHENTICATION"
    assert calls == 1


@pytest.mark.asyncio
async def test_rate_limit_is_retried_and_counted() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"message": "slow down"})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"ok"}'}}]},
        )

    provider, client = make_provider(httpx.MockTransport(handle))
    try:
        result = await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="Return an answer")],
        )
    finally:
        await client.aclose()

    assert result.answer == "ok"
    assert calls == 2
    assert len(provider.calls) == 1
    assert len(provider.telemetry.records) == 2
    assert provider.telemetry.records[0].error_code is ProviderErrorCode.RATE_LIMITED


@pytest.mark.asyncio
async def test_schema_failure_uses_one_bounded_repair_instruction() -> None:
    requests: list[dict[str, object]] = []

    async def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        if len(requests) == 1:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": '{"wrong":"value"}'}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"answer":"repaired"}'}}]},
        )

    provider, client = make_provider(httpx.MockTransport(handle))
    try:
        result = await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="Return an answer")],
        )
    finally:
        await client.aclose()

    assert result.answer == "repaired"
    assert len(requests) == 2
    repair_message = requests[1]["messages"][-1]["content"]
    assert "corrected JSON object" in repair_message
    assert "validation_errors" in repair_message


@pytest.mark.asyncio
async def test_schema_failure_fails_closed_after_bounded_repair() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"wrong":"value"}'}}]},
        )

    provider, client = make_provider(httpx.MockTransport(handle))
    try:
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate_structured(
                task="report",
                scenario="live",
                call_index=0,
                fixture_version="v0.1",
                schema=ExampleOutput,
                messages=[Message(role="user", content="Return an answer")],
            )
    finally:
        await client.aclose()

    assert exc_info.value.error_code is ProviderErrorCode.SCHEMA_VALIDATION
    assert calls == 2


@pytest.mark.asyncio
async def test_native_schema_disabled_fails_before_network() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json={})

    provider, client = make_provider(httpx.MockTransport(handle), native_json_schema=False)
    try:
        with pytest.raises(ProviderError) as exc_info:
            await provider.generate_structured(
                task="report",
                scenario="live",
                call_index=0,
                fixture_version="v0.1",
                schema=ExampleOutput,
                messages=[Message(role="user", content="Return an answer")],
            )
    finally:
        await client.aclose()

    assert exc_info.value.error_code is ProviderErrorCode.UNSUPPORTED_SCHEMA
    assert calls == 0

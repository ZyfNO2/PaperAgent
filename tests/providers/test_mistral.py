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


def make_provider(handler: httpx.MockTransport) -> MistralLLMProvider:
    config = ProviderRuntimeConfig(
        model="test-model",
        api_key=SecretStr("test-secret"),
        max_attempts=2,
    )
    client = httpx.AsyncClient(transport=handler)
    return MistralLLMProvider(config, client=client)


@pytest.mark.asyncio
async def test_mistral_returns_strict_structured_output() -> None:
    async def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"answer":"grounded"}'}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2},
            },
        )

    provider = make_provider(httpx.MockTransport(handle))
    result = await provider.generate_structured(
        task="report",
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        schema=ExampleOutput,
        messages=[Message(role="user", content="Return an answer")],
    )

    assert result == ExampleOutput(answer="grounded")
    assert len(provider.telemetry.records) == 1
    assert provider.telemetry.records[0].usage.input_tokens == 10


@pytest.mark.asyncio
async def test_authentication_failure_is_not_retried() -> None:
    calls = 0

    async def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"message": "invalid key"})

    provider = make_provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="Return an answer")],
        )

    assert exc_info.value.code is ProviderErrorCode.AUTHENTICATION
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

    provider = make_provider(httpx.MockTransport(handle))
    result = await provider.generate_structured(
        task="report",
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        schema=ExampleOutput,
        messages=[Message(role="user", content="Return an answer")],
    )

    assert result.answer == "ok"
    assert calls == 2
    assert len(provider.telemetry.records) == 2
    assert provider.telemetry.records[0].error_code is ProviderErrorCode.RATE_LIMITED


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

    provider = make_provider(httpx.MockTransport(handle))
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="Return an answer")],
        )

    assert exc_info.value.code is ProviderErrorCode.SCHEMA_VALIDATION
    assert calls == 2

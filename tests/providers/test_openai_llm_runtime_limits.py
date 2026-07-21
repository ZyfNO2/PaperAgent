from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, SecretStr

from paperagent.errors import ProviderError
from paperagent.providers.config import load_provider_config
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.request_rate_limit import AsyncRequestRateLimiter
from paperagent.providers.runtime import LLMProviderName, ProviderRuntimeConfig
from paperagent.providers.runtime_factory import build_llm_provider
from paperagent.schemas import Message


class _Reply(BaseModel):
    status: str


def _response(status_code: int, body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code,
        json=body,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
    )


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    responses: Iterator[httpx.Response],
    captured: dict[str, Any],
) -> None:
    class _FakeAsyncClient:
        def __init__(self, *, timeout: httpx.Timeout) -> None:
            captured["timeout"] = timeout

        async def __aenter__(self) -> _FakeAsyncClient:
            return self

        async def __aexit__(
            self,
            exc_type: object,
            exc: object,
            traceback: object,
        ) -> None:
            del exc_type, exc, traceback

        async def post(
            self,
            url: str,
            *,
            json: dict[str, Any],
            headers: dict[str, str],
        ) -> httpx.Response:
            captured.setdefault("requests", []).append(
                {"url": url, "json": json, "headers": headers}
            )
            return next(responses)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


def _generate(provider: OpenAILLMProvider) -> _Reply:
    return asyncio.run(
        provider.generate_structured(
            task="runtime-hardening-test",
            scenario="unit",
            call_index=1,
            fixture_version="v1",
            schema=_Reply,
            messages=[Message(role="user", content="Return status ok")],
        )
    )


def test_runtime_factory_enforces_token_and_timeout_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter(
        [
            _response(
                200,
                {
                    "choices": [{"message": {"content": '{"status":"ok"}'}}],
                    "usage": {"prompt_tokens": 5, "completion_tokens": 3},
                },
            )
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    config = ProviderRuntimeConfig(
        provider=LLMProviderName.OPENAI,
        model="z-ai/glm-5.2",
        api_key=SecretStr("test-key"),
        base_url="https://example.test/v1",
        connect_timeout_seconds=2,
        read_timeout_seconds=7,
        total_timeout_seconds=11,
        max_attempts=1,
        max_requests_per_minute=40,
        max_output_tokens_per_call=123,
        native_json_schema=True,
    )

    provider = build_llm_provider(config)
    assert isinstance(provider, OpenAILLMProvider)
    assert provider._max_requests_per_minute == 40
    reply = _generate(provider)

    assert reply.status == "ok"
    request = captured["requests"][0]
    assert request["json"]["max_tokens"] == 123
    assert request["json"]["response_format"]["type"] == "json_schema"
    timeout = captured["timeout"]
    assert isinstance(timeout, httpx.Timeout)
    assert timeout.connect == 2
    assert timeout.read == 7


def test_native_schema_can_be_disabled_without_wasting_a_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter(
        [
            _response(
                200,
                {"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            )
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=0,
        max_output_tokens=64,
        native_json_schema=False,
    )

    reply = _generate(provider)

    assert reply.status == "ok"
    assert len(captured["requests"]) == 1
    payload = captured["requests"][0]["json"]
    assert "response_format" not in payload
    assert payload["max_tokens"] == 64
    assert "--- JSON SCHEMA" in payload["messages"][-1]["content"]


def test_response_format_rejection_falls_back_and_preserves_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter(
        [
            _response(
                400,
                {
                    "error": {
                        "type": "invalid_request_error",
                        "message": "response_format json_schema is unsupported",
                    }
                },
            ),
            _response(
                200,
                {"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            ),
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=0,
        max_output_tokens=64,
    )

    reply = _generate(provider)

    assert reply.status == "ok"
    assert len(captured["requests"]) == 2
    assert "response_format" in captured["requests"][0]["json"]
    assert "response_format" not in captured["requests"][1]["json"]
    assert captured["requests"][1]["json"]["max_tokens"] == 64


def test_http_authentication_error_is_typed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    responses = iter([_response(401, {"error": {"message": "invalid key"}})])
    _install_fake_client(monkeypatch, responses, captured)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=0,
    )

    with pytest.raises(ProviderError) as error:
        _generate(provider)

    assert error.value.code == "LLM_AUTHENTICATION"
    assert error.value.retryable is False


def test_config_parses_native_schema_switch() -> None:
    config = load_provider_config(
        environ={
            "PAPERAGENT_LLM_PROVIDER": "openai",
            "PAPERAGENT_LLM_MODEL": "z-ai/glm-5.2",
            "PAPERAGENT_OPENAI_API_KEY": "test-key",
            "PAPERAGENT_LLM_NATIVE_JSON_SCHEMA": "off",
            "PAPERAGENT_LLM_MAX_REQUESTS_PER_MINUTE": "40",
        }
    )

    assert config.native_json_schema is False
    assert config.max_requests_per_minute == 40


def test_retry_after_header_controls_rate_limit_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sleeps: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    responses = iter(
        [
            httpx.Response(
                429,
                json={"error": {"message": "rate limited"}},
                headers={"Retry-After": "17"},
                request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
            ),
            _response(
                200,
                {"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            ),
        ]
    )
    _install_fake_client(monkeypatch, responses, captured)
    provider = OpenAILLMProvider(
        api_key="test-key",
        model="z-ai/glm-5.2",
        base_url="https://example.test/v1",
        max_retries=1,
    )

    reply = _generate(provider)

    assert reply.status == "ok"
    assert sleeps == [17.0]


def test_rate_limit_without_header_uses_long_backoff() -> None:
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
    )

    assert OpenAILLMProvider._http_retry_delay(response, 0) == 15.0
    assert OpenAILLMProvider._http_retry_delay(response, 1) == 30.0
    assert OpenAILLMProvider._http_retry_delay(response, 9) == 60.0


def test_request_rate_limiter_smooths_forty_requests_per_minute() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    async def scenario() -> None:
        limiter = AsyncRequestRateLimiter(40, clock=clock, sleep=sleep)
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()

    asyncio.run(scenario())

    assert sleeps == [1.5, 1.5]

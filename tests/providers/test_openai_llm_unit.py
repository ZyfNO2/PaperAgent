from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from pydantic import BaseModel, ConfigDict

from paperagent.errors import ProviderError, ProviderTimeoutError
from paperagent.providers import openai_llm as module
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.schemas import Message


class ExampleOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str


def _provider(**overrides: Any) -> OpenAILLMProvider:
    values: dict[str, Any] = {
        "api" + "_key": "unit-token",
        "model": "test-model",
        "base_url": "https://example.test/v1/",
        "timeout_seconds": 2.0,
        "max_retries": 1,
    }
    values.update(overrides)
    return OpenAILLMProvider(**values)


def _install_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


def _response(
    content: object,
    *,
    status: int = 200,
    usage: dict[str, int] | None = None,
) -> httpx.Response:
    body: dict[str, object] = {"choices": [{"message": {"content": content}}]}
    if usage is not None:
        body["usage"] = usage
    return httpx.Response(status, json=body)


def test_init_helpers_and_schema_contract() -> None:
    with pytest.raises(ValueError, match="api_key"):
        _provider(**{"api" + "_key": ""})

    provider = _provider()
    assert provider.model_name == "test-model"
    assert provider._base_url == "https://example.test/v1"
    assert provider._messages_to_openai([Message(role="user", content="hello")]) == [
        {"role": "user", "content": "hello"}
    ]
    response_format = provider._build_response_format(ExampleOutput)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "ExampleOutput"
    assert response_format["json_schema"]["strict"] is False


def test_record_usage_handles_valid_missing_and_invalid_json() -> None:
    provider = _provider()
    provider._record_usage(
        httpx.Response(
            200,
            json={"usage": {"prompt_tokens": 7, "completion_tokens": 3}},
        )
    )
    assert provider.last_usage.input_tokens == 7
    assert provider.last_usage.output_tokens == 3

    provider._record_usage(httpx.Response(200, json={}))
    assert provider.last_usage.input_tokens == 0
    assert provider.last_usage.output_tokens == 0

    provider._record_usage(httpx.Response(200, content=b"not-json"))
    assert provider.last_usage.input_tokens == 0
    assert provider.last_usage.output_tokens == 0


@pytest.mark.parametrize(
    ("response", "code"),
    [
        (httpx.Response(200, content=b"not-json"), "LLM_RESPONSE_JSON_INVALID"),
        (httpx.Response(200, json={}), "LLM_RESPONSE_JSON_INVALID"),
        (_response(""), "LLM_RESPONSE_JSON_INVALID"),
        (_response(42), "LLM_RESPONSE_JSON_INVALID"),
        (_response("not-json"), "LLM_RESPONSE_JSON_INVALID"),
        (_response('{"wrong":"field"}'), "LLM_RESPONSE_SCHEMA_INVALID"),
    ],
)
def test_parse_response_fails_closed(response: httpx.Response, code: str) -> None:
    provider = _provider()
    with pytest.raises(ProviderError) as exc_info:
        provider._parse_response(response, ExampleOutput, "task")
    assert exc_info.value.code == code
    assert exc_info.value.retryable is False


def test_parse_response_accepts_plain_and_fenced_json() -> None:
    provider = _provider()
    assert (
        provider._parse_response(_response('{"answer":"plain"}'), ExampleOutput, "task").answer
        == "plain"
    )
    fenced = '```json\n{"answer":"fenced"}\n```'
    assert provider._parse_response(_response(fenced), ExampleOutput, "task").answer == "fenced"


def test_augment_messages_with_schema() -> None:
    assert OpenAILLMProvider._augment_messages_with_schema([], ExampleOutput) == []
    original = [
        Message(role="system", content="system"),
        Message(role="user", content="request"),
    ]
    augmented = OpenAILLMProvider._augment_messages_with_schema(original, ExampleOutput)
    assert original[-1].content == "request"
    assert augmented[-1].content.startswith("request")
    assert "JSON SCHEMA" in augmented[-1].content
    assert '"answer"' in augmented[-1].content


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (httpx.Response(400, content=b"not-json"), False),
        (
            httpx.Response(
                400,
                json={"error": {"message": "response_format unsupported"}},
            ),
            True,
        ),
        (
            httpx.Response(
                400,
                json={"error": {"type": "invalid_request_error"}},
            ),
            True,
        ),
        (
            httpx.Response(
                400,
                json={
                    "error": {
                        "type": "invalid_request_error",
                        "param": "messages",
                    }
                },
            ),
            False,
        ),
    ],
)
def test_response_format_error_detection(
    response: httpx.Response,
    expected: bool,
) -> None:
    assert OpenAILLMProvider._is_response_format_error(response) is expected


@pytest.mark.asyncio
async def test_post_success_records_usage_and_parses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return _response(
            '{"answer":"ok"}',
            usage={"prompt_tokens": 11, "completion_tokens": 4},
        )

    _install_transport(monkeypatch, handle)
    provider = _provider()
    result = await provider.generate_structured(
        task="report",
        scenario="live",
        call_index=0,
        fixture_version="v1",
        schema=ExampleOutput,
        messages=[Message(role="user", content="answer")],
    )

    assert result.answer == "ok"
    assert provider.last_usage.input_tokens == 11
    assert provider.last_usage.output_tokens == 4
    assert provider.last_latency_ms >= 0
    assert requests[0].url == httpx.URL("https://example.test/v1/chat/completions")
    payload = json.loads(requests[0].content)
    assert payload["response_format"]["type"] == "json_schema"


@pytest.mark.asyncio
async def test_timeout_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    _install_transport(monkeypatch, handle)
    provider = _provider()
    with pytest.raises(ProviderTimeoutError) as exc_info:
        await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="answer")],
        )
    assert exc_info.value.code == "PROVIDER_TIMEOUT"


@pytest.mark.asyncio
async def test_rate_limit_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleeps: list[float] = []

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"message": "slow"}})
        return _response('{"answer":"retried"}')

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    _install_transport(monkeypatch, handle)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    provider = _provider()
    result = await provider.generate_structured(
        task="report",
        scenario="live",
        call_index=0,
        fixture_version="v1",
        schema=ExampleOutput,
        messages=[Message(role="user", content="answer")],
    )
    assert result.answer == "retried"
    assert calls == 2
    assert sleeps == [15.0]


@pytest.mark.asyncio
async def test_nonretryable_http_error_is_wrapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    _install_transport(monkeypatch, handle)
    provider = _provider()
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="answer")],
        )
    assert exc_info.value.code == "LLM_AUTHENTICATION"
    assert exc_info.value.retryable is False


@pytest.mark.asyncio
async def test_transport_error_retries_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline", request=request)

    async def fake_sleep(delay: float) -> None:
        assert delay == 15.0

    _install_transport(monkeypatch, handle)
    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    provider = _provider()
    with pytest.raises(ProviderError) as exc_info:
        await provider.generate_structured(
            task="report",
            scenario="live",
            call_index=0,
            fixture_version="v1",
            schema=ExampleOutput,
            messages=[Message(role="user", content="answer")],
        )
    assert calls == 2
    assert exc_info.value.code == "LLM_CONNECT"
    assert exc_info.value.retryable is True


@pytest.mark.asyncio
async def test_unsupported_response_format_uses_plain_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        if len(requests) == 1:
            return httpx.Response(
                400,
                json={"error": {"message": "response_format is not supported"}},
            )
        return _response('```json\n{"answer":"fallback"}\n```')

    _install_transport(monkeypatch, handle)
    provider = _provider()
    result = await provider.generate_structured(
        task="report",
        scenario="live",
        call_index=0,
        fixture_version="v1",
        schema=ExampleOutput,
        messages=[Message(role="user", content="answer")],
    )
    assert result.answer == "fallback"
    assert len(requests) == 2
    assert "response_format" in requests[0]
    assert "response_format" not in requests[1]
    assert "JSON SCHEMA" in requests[1]["messages"][-1]["content"]

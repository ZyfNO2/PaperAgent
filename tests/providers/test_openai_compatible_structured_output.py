from __future__ import annotations

import asyncio
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from paperagent.errors import ProviderError
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.structured_output import validate_structured_response
from paperagent.schemas import Message


class _Reply(BaseModel):
    status: str
    count: int = 1


def _body(content: object) -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _response(body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        200,
        json=body,
        request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
    )


def test_accepts_fenced_json_with_surrounding_prose() -> None:
    reply = validate_structured_response(
        _body("Result follows:\n```json\n{\"status\":\"ok\",\"count\":2}\n```\nDone."),
        _Reply,
    )
    assert reply == _Reply(status="ok", count=2)


def test_accepts_openai_content_block_arrays() -> None:
    reply = validate_structured_response(
        _body(
            [
                {"type": "text", "text": '{"status":"'},
                {"type": "output_text", "text": 'ok","count":3}'},
            ]
        ),
        _Reply,
    )
    assert reply == _Reply(status="ok", count=3)


def test_accepts_tool_call_arguments_when_content_is_empty() -> None:
    body = {
        "choices": [
            {
                "message": {
                    "content": None,
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "return_reply",
                                "arguments": '{"status":"ok","count":4}',
                            },
                        }
                    ],
                }
            }
        ]
    }
    assert validate_structured_response(body, _Reply) == _Reply(status="ok", count=4)


def test_accepts_legacy_choice_text_and_safe_python_literal() -> None:
    body = {"choices": [{"text": "{'status': 'ok', 'count': 5,}"}]}
    assert validate_structured_response(body, _Reply) == _Reply(status="ok", count=5)


def test_uses_later_schema_valid_json_candidate() -> None:
    body = _body(
        'First draft: {"status": 7}. Corrected: {"status":"ok","count":6}'
    )
    assert validate_structured_response(body, _Reply) == _Reply(status="ok", count=6)


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch,
    responses: Iterator[httpx.Response],
    requests: list[dict[str, Any]],
) -> None:
    class _FakeAsyncClient:
        def __init__(self, *, timeout: httpx.Timeout) -> None:
            del timeout

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
            requests.append({"url": url, "json": json, "headers": headers})
            return next(responses)

    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)


def _generate(provider: OpenAILLMProvider) -> _Reply:
    return asyncio.run(
        provider.generate_structured(
            task="compatibility-test",
            scenario="unit",
            call_index=1,
            fixture_version="v1",
            schema=_Reply,
            messages=[Message(role="user", content="Return a reply")],
        )
    )


def test_bounded_schema_repair_is_model_agnostic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    responses = iter(
        [
            _response(_body("I could not format the answer.")),
            _response(_body('{"status":"ok","count":7}')),
        ]
    )
    _install_fake_client(monkeypatch, responses, requests)
    provider = OpenAILLMProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        model="any-openai-compatible-model",
        native_json_schema=False,
        allow_schema_repair=True,
        max_retries=0,
    )

    reply = _generate(provider)

    assert reply == _Reply(status="ok", count=7)
    assert len(requests) == 2
    assert "structured-output repair" in requests[1]["json"]["messages"][0]["content"]
    assert "any-openai-compatible-model" == requests[0]["json"]["model"]


def test_schema_repair_can_be_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[dict[str, Any]] = []
    responses = iter([_response(_body("not json"))])
    _install_fake_client(monkeypatch, responses, requests)
    provider = OpenAILLMProvider(
        api_key="test-key",
        base_url="https://example.test/v1",
        native_json_schema=False,
        allow_schema_repair=False,
        max_retries=0,
    )

    with pytest.raises(ProviderError, match="no parseable structured payload"):
        _generate(provider)
    assert len(requests) == 1

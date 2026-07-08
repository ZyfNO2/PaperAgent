from __future__ import annotations

import httpx

import pytest

from app.services import llm


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or str(payload)

    def json(self):
        return self._payload


def test_deepseek_flash_fallbacks_to_pro_on_invalid_json(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_FLASH_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_PRO_MODEL", "deepseek-pro")
    monkeypatch.setenv("LLM_JSON_RETRY_COUNT", "0")

    calls: list[str] = []

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        calls.append(json["model"])
        if json["model"] == "deepseek-flash":
            return _FakeResponse(
                200,
                {"choices": [{"message": {"content": "{not-json"}}]},
            )
        return _FakeResponse(
            200,
            {"choices": [{"message": {"content": '{"answer":"ok","items":[1]}'}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    result = llm.chat_json("test", profile="topic_understand")

    assert result["answer"] == "ok"
    assert calls == ["deepseek-flash", "deepseek-pro"]


def test_provider_contract_keeps_same_field_set(monkeypatch):
    monkeypatch.setenv("LLM_JSON_RETRY_COUNT", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.setenv("MINIMAX_DISABLED", "false")

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        if "deepseek" in url:
            return _FakeResponse(
                200,
                {"choices": [{"message": {"content": '{"a":1,"b":["x"]}'}}]},
            )
        return _FakeResponse(
            200,
            {"content": [{"type": "text", "text": '{"a":2,"b":["y"]}'}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    deepseek_result = llm.chat_json("test", provider="deepseek", profile="topic_understand")
    minimax_result = llm.chat_json("test", provider="minimax", profile="topic_understand")

    assert set(deepseek_result.keys()) == {"a", "b"}
    assert set(minimax_result.keys()) == {"a", "b"}


def test_missing_provider_key_raises(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(llm.LLMUnavailable):
        llm.chat_json("test", provider="deepseek", profile="topic_understand")


def test_stepfun_reasoning_list_payload_returns_first_response(monkeypatch):
    monkeypatch.setenv("STEPFUN_API_KEY", "test-key")
    monkeypatch.setenv("STEPFUN_BASE_URL", "https://api.stepfun.com/step_plan/v1")
    monkeypatch.setenv("STEPFUN_MODEL", "step-3.7-flash")

    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        calls.append(url)
        return _FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning": [
                                {"type": "text", "text": "thinking..."},
                                {"type": "text", "text": '{"ok":true,"source":"reasoning"}'},
                            ],
                        },
                    },
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    raw = llm._chat_stepfun("repair me")

    assert raw == '{"ok": true, "source": "reasoning"}'
    assert calls == ["https://api.stepfun.com/step_plan/v1/chat/completions"]


def test_opencode_content_array_is_flattened(monkeypatch):
    monkeypatch.setenv("OPENCODE_API_KEY", "test-key")
    monkeypatch.setenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/v1")
    monkeypatch.setenv("OPENCODE_MODEL", "big-pickle")

    def fake_post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        return _FakeResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": [
                                {"type": "text", "text": '{"answer":"ok","items":[1,2]}'},
                            ],
                        },
                    },
                ],
            },
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    raw = llm._chat_opencode("test")

    assert raw == '{"answer":"ok","items":[1,2]}'

"""Tests for the Re1.1 LLM provider router.

SOP §7: profile routing, MiniMax disabled, no leak on error.
These are pure-python tests; no live LLM calls.
"""
from __future__ import annotations

import os
import sys

import pytest

# Make sure the project is importable when pytest runs from repo root.
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import apps.api.app.services.llm_router as router


@pytest.fixture(autouse=True)
def _disable_minimax(monkeypatch) -> None:
    monkeypatch.setenv("MINIMAX_DISABLED", "true")


def test_profile_table_has_required_profiles() -> None:
    stats = router.provider_stats()
    assert "fast_json" in stats
    assert "execution" in stats
    assert "premium_review" in stats
    assert stats["fast_json"]["provider"] == "deepseek"
    assert stats["execution"]["provider"] == "stepfun"
    assert stats["premium_review"]["provider"] == "voapi"


def test_fast_json_default_provider(_disable_minimax, monkeypatch) -> None:
    # FAST_JSON_PRIMARY can be configured; default is StepFun (the live provider).
    monkeypatch.delenv("FAST_JSON_PRIMARY", raising=False)
    spec = router._resolve_spec("fast_json")
    assert spec.provider in ("deepseek", "stepfun", "voapi")
    # If FAST_JSON_PRIMARY is set deepseek, fast_json should resolve to it.
    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    spec2 = router._resolve_spec("fast_json")
    assert spec2.provider == "deepseek"


def test_disabled_minimax_raises(_disable_minimax, monkeypatch) -> None:
    # Inject a minimax profile and confirm it raises.
    router._PROFILE_TABLE["legacy_minimax"] = router.ProviderSpec(
        profile="legacy_minimax", provider="minimax",
    )
    try:
        with pytest.raises(router.MiniMaxDisabledError):
            router._resolve_spec("legacy_minimax")
    finally:
        router._PROFILE_TABLE.pop("legacy_minimax", None)


def test_unknown_profile_raises(_disable_minimax, monkeypatch) -> None:
    with pytest.raises(router.LLMUnavailable):
        router._resolve_spec("does_not_exist")


def test_call_json_routes_to_adapter(_disable_minimax, monkeypatch) -> None:
    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-real-fake")

    import apps.api.app.services.llm as legacy_llm

    called: dict[str, object] = {}

    def fake_deepseek(prompt, *, system, temperature, max_tokens, timeout):  # type: ignore[no-untyped-def]
        called["prompt"] = prompt
        called["system"] = system
        return '{"ok": true, "provider": "deepseek"}'

    monkeypatch.setattr(legacy_llm, "_chat_deepseek", fake_deepseek)

    out = router.call_json("hi", system="SYS", profile="fast_json")
    assert out == {"ok": True, "provider": "deepseek"}
    assert called["system"] == "SYS"


def test_call_json_parses_fenced_json(_disable_minimax, monkeypatch) -> None:
    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-real")
    import apps.api.app.services.llm as legacy_llm

    def fake_deepseek(prompt, **kwargs):  # type: ignore[no-untyped-def]
        return '```json\n{"answer": 42}\n```'

    monkeypatch.setattr(legacy_llm, "_chat_deepseek", fake_deepseek)
    out = router.call_json("q", profile="fast_json")
    assert out == {"answer": 42}


def test_call_json_bad_json_raises(_disable_minimax, monkeypatch) -> None:
    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-real")
    import apps.api.app.services.llm as legacy_llm

    def fake_deepseek(prompt, **kwargs):  # type: ignore[no-untyped-def]
        return "this is not json"

    monkeypatch.setattr(legacy_llm, "_chat_deepseek", fake_deepseek)
    with pytest.raises(router.LLMUnavailable):
        router.call_json("q", profile="fast_json")


def test_call_json_non_dict_raises(_disable_minimax, monkeypatch) -> None:
    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-not-real")
    import apps.api.app.services.llm as legacy_llm

    def fake_deepseek(prompt, **kwargs):  # type: ignore[no-untyped-def]
        return "[1,2,3]"

    monkeypatch.setattr(legacy_llm, "_chat_deepseek", fake_deepseek)
    with pytest.raises(router.LLMUnavailable):
        router.call_json("q", profile="fast_json")


def test_no_leak_when_no_key(_disable_minimax, monkeypatch) -> None:
    """SOP §7: must not print the key on error message text."""
    import apps.api.app.services.llm as legacy_llm

    monkeypatch.setenv("FAST_JSON_PRIMARY", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "key-should-not-leak-fake")

    def fake_deepseek(prompt, **kwargs):  # type: ignore[no-untyped-def]
        # Simulate an upstream error that would otherwise log the key.
        raise legacy_llm.LLMUnavailable(
            "Network error; Authorization: Bearer key-should-not-leak-fake"
        )

    monkeypatch.setattr(legacy_llm, "_chat_deepseek", fake_deepseek)

    with pytest.raises(router.LLMUnavailable) as excinfo:
        router.call_json("q", profile="fast_json")
    # The raised message must not contain the fake key.
    assert "key-should-not-leak" not in str(excinfo.value)

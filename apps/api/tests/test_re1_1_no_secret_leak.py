"""Re1.1 no-secret-leak audit — scan for leaked keys in new code.

SOP §1 / §17: real keys must not appear in Plan/apps/logs; test log must not
print API_KEY, Authorization, Bearer, or base64/token.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# Heuristic: 32-char hex or base64 strings, likely API keys.
_LONG_HEX = re.compile(r"\b[0-9a-f]{32,}\b", re.IGNORECASE)
_LONG_ALPHANUM = re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")


def _scan_file(path: str) -> list[str]:
    """Return a list of findings (strings)."""
    body = open(path, encoding="utf-8", errors="replace").read()
    finds: list[str] = []
    # Find API_KEY-like assignments with literal value.
    if re.search(
        r"""(API_KEY|TOKEN|SECRET)\s*=\s*["'][A-Za-z0-9+/=]{20,}["']""",
        body,
    ):
        # Exclude placeholder patterns.
        for m in re.finditer(
            r"""(API_KEY|TOKEN|SECRET)\s*=\s*["']([A-Za-z0-9+/=]{20,})["']""",
            body,
        ):
            markers = ("placeholder", "PLACEHOLDER", "your_", "YOUR_",
                       "test", "TEST", "sk-test", "REDACTED",
                       "xxxx", "<REDACTED>")
            value = m.group(2)
            if any(marker in value for marker in markers):
                continue
            finds.append(f"hardcoded-key:{m.start()}")
    for m in _LONG_HEX.finditer(body):
        ctx = body[max(0, m.start() - 20):m.end()].lower()
        if any(t in ctx for t in ("api_key", "token=", "authorization", "bearer")):
            finds.append(f"ctx-around-hex:{m.start()}")
    return finds


def test_no_secrets_in_re11_code() -> None:
    """Re1.1 code must not contain hardcoded keys."""
    dirs_to_scan = [
        os.path.join(ROOT, "apps", "api", "app", "services", "agents", "graph"),
        os.path.join(ROOT, "apps", "api", "app", "services", "agents", "prompts"),
    ]
    offenders: list[str] = []
    for d in dirs_to_scan:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not (name.endswith(".py") and "re11" in name):
                continue
            full = os.path.join(d, name)
            if finds := _scan_file(full):
                offenders.append(f"{full}:{finds}")
    assert not offenders, f"potential secret leaks: {offenders}"


def test_env_example_is_placeholder() -> None:
    """SOP §1: .env.example must not include real keys (only placeholders)."""
    p = os.path.join(ROOT, ".env.example")
    if not os.path.exists(p):
        pytest.skip(".env.example missing")
    body = open(p, encoding="utf-8").read()
    placeholders = ("placeholder", "PLACEHOLDER", "changeme", "YOUR_",
                    "<your-", "xxx", "yourapikey")
    for m in re.finditer(r"=\s*([A-Za-z0-9+/_\-]{20,})\s*", body):
        val = m.group(1)
        if not any(marker in val for marker in placeholders):
            pytest.fail(f".env.example has non-placeholder value: {val[:8]}...")


def test_chat_json_does_not_print_key_when_missing(monkeypatch) -> None:
    """SOP §7 / §1: missing-key error must not echo the key."""
    monkeypatch.setenv("MINIMAX_DISABLED", "true")
    monkeypatch.setenv("FAST_JSON_PRIMARY", "stepfun")
    monkeypatch.setenv("STEPFUN_API_KEY", "key-should-not-leak-fake")
    import apps.api.app.services.llm_router as r
    import apps.api.app.services.llm as legacy_llm

    def fake_stepfun(prompt, **kwargs):  # type: ignore[no-untyped-def]
        raise legacy_llm.LLMUnavailable(
            "Authorization: Bearer key-should-not-leak-fake"
        )

    monkeypatch.setattr(legacy_llm, "_chat_stepfun", fake_stepfun)

    with pytest.raises(r.LLMUnavailable) as excinfo:
        r.call_json("ping", profile="fast_json")
    assert "key-should-not-leak" not in str(excinfo.value)
    boom = RuntimeError("Bearer <REDACTED>")

    assert "<REDACTED>" in r._redact(boom)
    assert "Bearer" not in r._redact(boom)

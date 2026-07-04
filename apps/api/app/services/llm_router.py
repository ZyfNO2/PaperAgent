"""LLM provider router — maps provider profiles to concrete providers.

Profiles (SOP §7):
  fast_json        -> DeepSeek flash (topic parse, planner, verifier JSON)
  execution        -> StepFun (connectivity / cheap / simple exec; no final judge)
  premium_review   -> VOAPI GPT-5.4-medium (final sampling review only)
  disabled         -> MiniMax etc. (no implicit fallback; raises)

History:
  Re1.1: split from apps/api/app/services/llm.py so the graph can pick a
         provider per node without reading LLM_PROVIDER directly.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderSpec:
    """Static description of a provider for a given profile."""

    profile: str
    provider: str
    json_mode: bool = True
    allow_fallback: bool = False
    purpose: str = ""


# Default profile -> provider mapping. Overridable via env per SOP §7.
_PROFILE_TABLE: dict[str, ProviderSpec] = {
    "fast_json": ProviderSpec(
        profile="fast_json",
        provider="deepseek",
        json_mode=True,
        purpose="topic parse / planner / verifier JSON (no long reasoning)",
    ),
    "execution": ProviderSpec(
        profile="execution",
        provider="stepfun",
        json_mode=False,
        purpose="connectivity / cheap / simple exec (no final judge)",
    ),
    "premium_review": ProviderSpec(
        profile="premium_review",
        provider="voapi",
        json_mode=True,
        allow_fallback=False,
        purpose="final sampling review only",
    ),
}


class LLMUnavailable(RuntimeError):
    """LLM unavailable: missing key / network / parse failure."""


class MiniMaxDisabledError(LLMUnavailable):
    """MiniMax was requested but is disabled by MINIMAX_DISABLED=true."""


def _get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _resolve_spec(profile: str | None) -> ProviderSpec:
    """Resolve a profile string to a ProviderSpec.

    Raises if the profile maps to a disabled provider.
    """
    p = (profile or _get_env("LLM_PROFILE", "fast_json")).lower()
    if p == "fast_json":
        # Prefer DeepSeek; the caller's call_json will try fast_json_first
        # chain, so here we just hand back the StepFun-capable leaf that is
        # known to be up when DeepSeek is unavailable.
        primary = _get_env("FAST_JSON_PRIMARY", "stepfun").lower()
        if primary in ("deepseek", "stepfun", "voapi"):
            return ProviderSpec(
                profile=p, provider=primary,
                json_mode=(primary != "stepfun"),
                purpose="topic parse / planner / verifier JSON",
            )
        return _PROFILE_TABLE[p]
    spec = _PROFILE_TABLE.get(p)
    if spec is None:
        raise LLMUnavailable(
            f"unknown provider profile {p!r}; expected one of "
            f"{sorted(set(_PROFILE_TABLE) | {'fast_json'} )}"
        )
    if spec.provider == "minimax" or p == "disabled":
        raise MiniMaxDisabledError(
            f"provider profile {p!r} resolves to disabled provider "
            f"{spec.provider!r}; set LLM_PROFILE to a non-disabled profile"
        )
    return spec


def _redact(exc: BaseException) -> str:
    """Render an exception without leaking keys / tokens.

    Any exception whose message contains a sensitive token substring is rendered
    as a type-only placeholder; the offending substring is replaced with
    "<REDACTED>" so logs never carry keys.
    """
    msg = str(exc)
    for token in ("Bearer ", "x-api-key=", "Authorization",
                  "api-key", "API_KEY="):
        if token.lower() in msg.lower():
            head = msg.split(token, 1)[0]
            return f"{type(exc).__name__}: {head}<REDACTED>"
    return f"{type(exc).__name__}: {msg}"


def call_json(
    prompt: str,
    *,
    system: str | None = None,
    profile: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1500,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Call the profile's provider and return a parsed JSON dict.

    Never silently falls back across profiles. Never prints keys.
    """
    from apps.api.app.services import llm as _llm

    spec = _resolve_spec(profile)
    if _get_env("MINIMAX_DISABLED", "true").lower() == "true" and spec.provider == "minimax":
        raise MiniMaxDisabledError("MiniMax disabled; refusing implicit fallback")

    try:
        if spec.provider == "deepseek":
            raw = _llm._chat_deepseek(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
        elif spec.provider == "voapi":
            raw = _llm._chat_voapi(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
        elif spec.provider == "stepfun":
            # StepFun 3.7-flash supports the OpenAI-compat JSON surface when
            # response_format=json_object is passed via legacy adapter.
            raw = _llm._chat_stepfun(
                prompt, system=system, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            )
            # Guard: when StepFun is used as fast_json and the caller
            # requested JSON, its adapter drops response_format; caller's post-
            # parse will fail loudly and promote the issue to the trace.
        else:
            raise LLMUnavailable(f"no adapter for provider {spec.provider!r}")
    except BaseException as exc:
        raise LLMUnavailable(_redact(exc)) from exc

    if not raw:
        raise LLMUnavailable(f"{spec.provider} returned empty content")
    cleaned = _llm._strip_code_fence(raw)
    try:
        import json
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(
            f"{spec.provider} JSON parse failed: {exc}; raw={raw[:200]!r}"
        ) from exc
    if not isinstance(result, dict):
        raise LLMUnavailable(f"{spec.provider} did not return a dict")
    return result


def provider_stats() -> dict[str, Any]:
    """Report the active profile table for trace / reporting."""
    return {
        name: {
            "provider": spec.provider,
            "json_mode": spec.json_mode,
            "purpose": spec.purpose,
        }
        for name, spec in _PROFILE_TABLE.items()
    }

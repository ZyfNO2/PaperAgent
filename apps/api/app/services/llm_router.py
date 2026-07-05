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
from typing import Any, Callable, Literal

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
        provider="stepfun",
        json_mode=True,
        purpose="topic parse / planner / verifier JSON",
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
        if primary in ("deepseek", "stepfun", "voapi", "opencode"):
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


def _extract_json_from_text(text: str) -> list:
    """Pull every top-level JSON object/array out of `text`.

    Reasoner models (e.g. StepFun step-3.7-flash emit a thinking transcript
    and then the JSON payload — often in the same field. We recover by scanning
    for balanced braces/brackets from the text and returning every dict/list
    that was found.
    """
    import json
    import re

    if not text:
        return []
    found: list = []
    for m in list(re.finditer(r"[{[]", text))[::-1]:
        start = m.start()
        opener = text[start]
        closer = "}" if opener == "{" else "]"
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : i + 1])
                        if isinstance(parsed, (dict, list)):
                            found.append(parsed)
                    except json.JSONDecodeError:
                        pass
                    break
    # Backward scan already returns last-found first; put the biggest
    # candidate last so it wins in `next((x for x in ... if ...), None)`.
    return list(reversed(found))


# Public alias used by graph node callers.
extract_json_objects = _extract_json_from_text


def call_json(
    prompt: str,
    *,
    system: str | None = None,
    profile: str | None = None,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    timeout: float = 60.0,
    expected: Literal["dict", "list", "any"] = "any",
    schema_hint: str = "",
) -> Any:
    """Call the profile provider and return parsed JSON.

    3-phase recovery:
      Phase A  direct content parse (strip fences / <think>)
      Phase B  reasoning-field + balanced scan
      Phase C  fallback formatter
    """
    from apps.api.app.services import llm as _llm

    spec = _resolve_spec(profile)
    if _get_env("MINIMAX_DISABLED", "true").lower() == "true" and spec.provider == "minimax":
        raise MiniMaxDisabledError("MiniMax disabled; refusing implicit fallback")

    if max_tokens is None:
        max_tokens = int(_get_env("LLM_THINKING_BUDGET", "6000"))

    repair_stages = []
    try:
        if spec.provider == "deepseek":
            raw = _llm._chat_deepseek(prompt, system=system, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        elif spec.provider == "voapi":
            raw = _llm._chat_voapi(prompt, system=system, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        elif spec.provider == "opencode":
            raw = _llm._chat_opencode(prompt, system=system, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        elif spec.provider == "stepfun":
            raw = _llm._chat_stepfun(prompt, system=system, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        else:
            raise LLMUnavailable(f"no adapter for provider {spec.provider!r}")
    except BaseException as exc:
        raise LLMUnavailable(_redact(exc)) from exc

    if not raw:
        raise LLMUnavailable(f"{spec.provider} returned empty content")

    # Phase A
    direct, ok = _json_repair_parse_direct(raw, expected)
    repair_stages.append("direct_content" if ok else "direct_content_failed")
    if ok:
        return direct

    # Phase B
    from apps.api.app.services.json_repair import parse_reasoning_field, _scan_balanced_json
    value, ok = parse_reasoning_field(raw, expected)
    repair_stages.append("reasoning_scan" if ok else "reasoning_scan_failed")
    if ok:
        return value

    blobs = _scan_balanced_json(_llm._strip_code_fence(raw))
    if expected == "dict":
        blobs = [b for b in blobs if isinstance(b, dict)]
    elif expected == "list":
        blobs = [b for b in blobs if isinstance(b, list)]
    if blobs:
        repair_stages.append("balanced_scan")
        return blobs[-1]

    # Phase C
    value, ok = _fallback_formatter(raw, expected, schema_hint, profile=profile)
    repair_stages.append("fallback_formatter" if ok else "fallback_formatter_failed")
    if ok:
        return value

    raise LLMUnavailable(f"{spec.provider}: JSON unrecoverable (expected={expected}); stages={repair_stages}")
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


def _json_repair_parse_direct(text, expected):
    import json
    import re
    if not text:
        return None, False
    stripped = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", stripped)
    if fence:
        stripped = fence.group(1)
    stripped = re.sub(r"<think>.*?</think>", "", stripped, flags=re.DOTALL | re.IGNORECASE).strip()
    stripped = re.sub(r"<reasoning>.*?</reasoning>", "", stripped, flags=re.DOTALL | re.IGNORECASE).strip()
    if not stripped:
        return None, False
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        return None, False
    if expected == "dict" and not isinstance(value, dict):
        return None, False
    if expected == "list" and not isinstance(value, list):
        return None, False
    return value, True


def _fallback_formatter(raw_text, expected, schema_hint, profile=None):
    """Re-prompt LLM to repair JSON."""
    from apps.api.app.services import llm_router as _r
    prompt = (
        "The following response failed JSON parsing. Re-write so the ENTIRE "
        "output is exactly one valid JSON object.\n"
        f"Required top-level shape: {expected}\n"
        f"{schema_hint}\nRaw to fix:\n---\n"
        + raw_text[:4000] + "\n---\n"
          "Reply ONLY with JSON, no prose, no fences."
    )
    try:
        result = _r.call_json(prompt, profile=profile, max_tokens=4000, timeout=120, expected=expected)
        return result, True
    except Exception as exc:
        logger.warning("call_json fallback_formatter failed: %s", exc)
        return None, False

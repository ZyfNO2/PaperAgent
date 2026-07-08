"""JSON repair layer for LLM responses.

StepFun step-3.7-flash is a reasoning model: it often emits a thinking
transcript and puts the JSON payload inside the `reasoning` field (sometimes
after a `<think>` block) while leaving `content` empty or truncated. This
module centralises the 3-phase recovery described in SOP §6:

  Phase A  parse_direct_content   content already JSON
  Phase B  parse_reasoning_field  strip <think>...</think> and scan `reasoning`
  Phase C  fallback_formatter     re-prompt llm with explicit schema

Every stage emits a `json_repair_stage` marker so the trace records how the
final JSON was obtained. On total failure we raise — we never silently
return an empty list as "success" (SOP §10).

History:
  Re1.2: initial implementation for step-3.7-flash reasoner output.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Expected top-level shapes a caller can require.
Expected = Literal["dict", "list", "any"]


# ---------------------------------------------------------------------------
# Phase A — direct content parse
# ---------------------------------------------------------------------------
def parse_direct_content(text: str, expected: Expected = "any") -> tuple[Any | None, bool]:
    """Return (parsed_value, ok). `ok` is True only when the value is JSON and
    (if `expected` is dict/list) matches the required top-level shape."""
    if not text:
        return None, False
    stripped = text.strip()
    fence_match = re.search(
        r"```(?:json)?\s*(\{[\s\S]*?\}|\[[\s\S]*?\])\s*```", stripped,
    )
    if fence_match:
        stripped = fence_match.group(1)
    stripped = re.sub(
        r"<think>.*?</think>", "", stripped, flags=re.DOTALL | re.IGNORECASE,
    ).strip()
    stripped = re.sub(
        r"<reasoning>.*?</reasoning>", "", stripped, flags=re.DOTALL | re.IGNORECASE,
    ).strip()
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


# ---------------------------------------------------------------------------
# Phase B — reasoning-field recovery
# ---------------------------------------------------------------------------
def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> / <reasoning>...</reasoning> blocks and any
    "Reasoning:" preamble."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<reasoning>.*?</reasoning>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


def _scan_balanced_json(text: str) -> list[Any]:
    """Backwards-balanced scan returning every JSON blob found in `text`."""
    found: list[Any] = []
    if not text:
        return found
    for match in list(re.finditer(r"[{[]", text))[::-1]:
        start = match.start()
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
    return list(reversed(found))


def parse_reasoning_field(
    reasoning: str, expected: Expected = "any",
) -> tuple[Any | None, bool]:
    """Find JSON inside `reasoning`. Prefer the *last* balanced blob so the
    model's final answer wins over examples/transcripts."""
    if not reasoning:
        return None, False
    cleaned = _strip_thinking(reasoning)
    blobs = _scan_balanced_json(cleaned)
    if expected == "dict":
        blobs = [b for b in blobs if isinstance(b, dict)]
    elif expected == "list":
        blobs = [b for b in blobs if isinstance(b, list)]
    if not blobs:
        return None, False
    return blobs[-1], True


# ---------------------------------------------------------------------------
# Phase C — fallback formatter (invokes LLM a second time)
# ---------------------------------------------------------------------------
def fallback_formatter(
    raw_text: str,
    expected: Expected,
    schema_hint: str,
    profile: str | None = "fast_json",
) -> tuple[Any | None, bool]:
    """Re-prompt the LLM with the original raw response plus an instruction to
    reformat as JSON. Uses the same `profile` as the primary call."""
    from apps.api.app.services import llm_router

    prompt = (
        "The following response failed JSON parsing.\n"
        "Rewrite it so the ENTIRE output is a single valid JSON object.\n"
        f"Expected top-level shape: {expected}.\n"
        f"{schema_hint}\n\n"
        "Raw response to fix:\n---\n"
        + raw_text[:4000] + "\n---\n"
          "Reply with ONLY the JSON, no prose, no markdown fences."
    )
    try:
        result = llm_router.call_json(
            prompt, profile=profile, max_tokens=4000, timeout=120,
            expected=expected,
        )
        if expected == "dict" and isinstance(result, dict):
            return result, True
        if expected == "list" and isinstance(result, list):
            return result, True
        if expected == "any":
            return result, True
        return None, False
    except Exception as exc:  # noqa: BLE001
        logger.warning("json_repair fallback_formatter failed: %s", exc)
        return None, False


# ---------------------------------------------------------------------------
# Unified entrypoint
# ---------------------------------------------------------------------------
def repair_json(
    content: str,
    reasoning: str | None,
    *,
    expected: Expected = "dict",
    schema_hint: str = "",
    profile: str | None = "fast_json",
) -> tuple[Any, list[str]]:
    """Return (parsed_value, stages_tried). Raises if all stages fail.
    `stages_tried` lists which phases produced a candidate, e.g.
    ["direct_content", "balanced_scan"].
    """
    from apps.api.app.services.llm_router import LLMUnavailable

    stages: list[str] = []

    # Phase A: direct content parse
    value, ok = parse_direct_content(content, expected)
    stages.append("direct_content" if ok else "direct_content_failed")
    if ok:
        return value, stages

    # Phase B: reasoning field recovery
    value, ok = parse_reasoning_field(reasoning or "", expected)
    stages.append("reasoning_scan" if ok else "reasoning_scan_failed")
    if ok:
        return value, stages

    # Phase B-ext: balanced scan of content (handles partial JSON in content)
    blobs = _scan_balanced_json(_strip_thinking(content))
    if expected == "dict":
        blobs = [b for b in blobs if isinstance(b, dict)]
    elif expected == "list":
        blobs = [b for b in blobs if isinstance(b, list)]
    if blobs:
        stages.append("balanced_scan")
        return blobs[-1], stages

    # Phase C: fallback formatter
    combined = (content or "") + "\n" + (reasoning or "")
    value, ok = fallback_formatter(combined, expected, schema_hint, profile=profile)
    stages.append("fallback_formatter" if ok else "fallback_formatter_failed")
    if ok:
        return value, stages

    raise LLMUnavailable(
        f"json_repair: all stages failed (expected={expected}); stages={stages}"
    )

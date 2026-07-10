"""Capability probe service — test what a provider model can do.

Re6.1 Provider Core. Sends lightweight probe requests to verify:
  - chat: basic text response
  - json_object: structured JSON output
  - json_schema: schema-constrained JSON output
  - reasoning_envelope: reasoning/thinking fields in response
  - streaming: SSE chunk receipt
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from .errors import ProviderError, ProviderErrorType
from .profile import ProbedCapabilities

logger = logging.getLogger(__name__)

# Lightweight probe payloads
_PROBE_CONTENT = "ping"  # minimal — avoids burning tokens


async def probe_model(
    base_url: str,
    api_key: str,
    model: str,
    *,
    protocol: str = "openai_compatible",
) -> ProbedCapabilities:
    """Probe a model's capabilities with lightweight test requests.

    Runs probes in dependency order (chat first; if chat fails, skip rest).
    Individual probe failures set the capability to false and record probe_error.

    Args:
        base_url: Provider base URL.
        api_key: Raw API key.
        model: Model ID to probe.
        protocol: "openai_compatible" or "anthropic_like".

    Returns:
        ProbedCapabilities with boolean results for each capability.
    """
    caps = ProbedCapabilities()
    probe_error_parts: list[str] = []

    # Select adapter
    if protocol == "anthropic_like":
        from .adapters.anthropic_adapter import anthropic_chat as chat_fn
    else:
        from .adapters.openai_adapter import openai_chat as chat_fn

    # ---- 1. Chat ----
    result = await chat_fn(
        base_url, api_key, model,
        messages=[{"role": "user", "content": _PROBE_CONTENT}],
        max_tokens=10,
    )
    if isinstance(result, ProviderError):
        probe_error_parts.append(f"chat:{result.error_type.value}")
        caps.chat = False
    else:
        content = _extract_content(result)
        caps.chat = bool(content)

    if not caps.chat:
        caps.probe_error = "; ".join(probe_error_parts)
        return caps

    # ---- 2. json_object ----
    json_result = await chat_fn(
        base_url, api_key, model,
        messages=[{"role": "user", "content": 'Reply with JSON: {"pong": true}'}],
        max_tokens=50,
        response_format={"type": "json_object"},
    )
    if isinstance(json_result, ProviderError):
        probe_error_parts.append(f"json_object:{json_result.error_type.value}")
        caps.json_object = False
    else:
        content = _extract_content(json_result)
        caps.json_object = _is_valid_json(content)

    # ---- 3. json_schema ----
    test_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "pong",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
                "additionalProperties": False,
            },
        },
    }
    schema_result = await chat_fn(
        base_url, api_key, model,
        messages=[{"role": "user", "content": '{"ok": true}'}],
        max_tokens=50,
        response_format=test_schema,
    )
    if isinstance(schema_result, ProviderError):
        probe_error_parts.append(f"json_schema:{schema_result.error_type.value}")
        caps.json_schema = False
    else:
        content = _extract_content(schema_result)
        if _is_valid_json(content):
            try:
                obj = json.loads(content)
                caps.json_schema = isinstance(obj, dict) and obj.get("ok") is True
            except json.JSONDecodeError:
                caps.json_schema = False
        else:
            caps.json_schema = False

    # ---- 4. reasoning_envelope ----
    if not isinstance(json_result, ProviderError):
        caps.reasoning_envelope = _has_reasoning(json_result)
    # Try a dedicated check with the chat result too
    if not caps.reasoning_envelope and isinstance(result, dict):
        caps.reasoning_envelope = _has_reasoning(result)

    # ---- 5. streaming ----
    stream_result = await chat_fn(
        base_url, api_key, model,
        messages=[{"role": "user", "content": _PROBE_CONTENT}],
        max_tokens=10,
        stream=True,
    )
    caps.streaming = not isinstance(stream_result, ProviderError)

    caps.probed_at = datetime.now(timezone.utc)
    if probe_error_parts:
        caps.probe_error = "; ".join(probe_error_parts)

    return caps


def _extract_content(result: dict[str, Any]) -> str:
    """Extract content string from a normalized chat response."""
    choices = result.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        return msg.get("content") or ""
    return ""


def _is_valid_json(text: str) -> bool:
    """Check if a string is valid JSON."""
    if not text or not text.strip():
        return False
    try:
        json.loads(text.strip())
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _has_reasoning(result: dict[str, Any]) -> bool:
    """Check if a response includes reasoning/thinking fields."""
    if result.get("reasoning"):
        return True
    choices = result.get("choices") or []
    for choice in choices:
        msg = choice.get("message") or {}
        if msg.get("reasoning") or msg.get("thinking"):
            return True
        if choice.get("reasoning") or choice.get("thinking"):
            return True
    return False

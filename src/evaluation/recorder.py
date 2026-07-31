from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from paperagent.telemetry.redaction import redact

MAX_STRING = 2_000
MAX_ITEMS = 25


def summarize(value: Any) -> Any:
    """Redact secrets and bound stored tool/model payloads without hiding errors."""
    safe = redact(value)
    if isinstance(safe, str):
        return safe if len(safe) <= MAX_STRING else safe[:MAX_STRING] + "…[truncated]"
    if isinstance(safe, Mapping):
        return {str(k): summarize(v) for k, v in list(safe.items())[:MAX_ITEMS]}
    if isinstance(safe, Sequence) and not isinstance(safe, str | bytes | bytearray):
        items = [summarize(v) for v in list(safe)[:MAX_ITEMS]]
        if len(safe) > MAX_ITEMS:
            items.append({"truncated_items": len(safe) - MAX_ITEMS})
        return items
    if hasattr(safe, "model_dump"):
        return summarize(safe.model_dump(mode="json"))
    try:
        json.dumps(safe)
    except (TypeError, ValueError):
        return summarize(repr(safe))
    return safe


def canonical_call(tool_name: str, arguments: Mapping[str, Any] | None) -> str:
    return tool_name + ":" + json.dumps(arguments or {}, sort_keys=True, default=str)

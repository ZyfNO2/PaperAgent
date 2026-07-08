"""Shared trace helpers for graph nodes — eliminates 34 copy-pasted defs."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def emit_trace(
    node: str,
    t0: float,
    ins: dict,
    out: dict,
    tools: list,
    prov: str,
    errs: list,
    state_keys: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
        "state_keys": state_keys or [],
    }

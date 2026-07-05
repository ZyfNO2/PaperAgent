"""LangGraph node: intake — bootstraps trace_events + provider_profile.

Pure function, no LLM, no side effects. Idempotent: if `trace_events` is already
non-empty (e.g. a prior node already initialised it) we return an empty patch so
we never clobber history on re-entry.

Output fields: case_id, provider_profile, trace_events, errors.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _emit(node: str, t0: float, ins: dict, out: dict,
          tools: list, prov: str, errs: list) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": _now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": _now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
    }


def _slugify(text: str) -> str:
    """Derive a kebab-case slug from a topic string."""
    s = (text or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


def intake_node(state: ResearchState) -> dict[str, Any]:
    """Initialise intake; returns {} if trace_events already present."""
    t0 = time.time()

    # Idempotency guard: trust existing trace.
    if state.get("trace_events"):
        return {}

    topic = state.get("topic") or ""
    case_id = state.get("case_id") or _slugify(topic)

    trace = _emit("intake", t0,
                  {"topic": topic},
                  {"ok": True},
                  [], "local", [])

    return {
        "case_id": case_id,
        "provider_profile": "fast_json",
        "trace_events": [trace],
        "errors": [],
    }

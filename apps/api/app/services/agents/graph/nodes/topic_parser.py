"""LangGraph node A1 — topic_parser_node.

Parses the topic string into structured `topic_atoms`. Idempotent: if state
already carries a non-empty topic_atoms we return {} (no-op).

Patch fields:
  topic_atoms        required (+ normalized: every list[str], domain is str)
  trace_events       appended
  errors             appended  (only on LLMUnavailable — partial patch persists)
  provider_profile   "fast_json"
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_parser as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable

logger = logging.getLogger(__name__)


# Allowed domain values — single string (see ResearchState docstring & prompt).
_ALLOWED_DOMAINS = frozenset({
    "signal_timeseries", "vision_2d", "vision_3d", "nlp_llm", "remote_sensing",
    "medical_ai", "energy_power", "control_monitoring", "robotics_control",
    "civil_infra", "unknown",
})

# Fallback skeleton — every value list[str] except domain which is str.
_EMPTY_ATOMS: dict[str, Any] = {
    "method": [], "object": [], "task": [], "scenario": [],
    "domain": "unknown",
    "dataset_terms": [], "baseline_terms": [], "avoid_terms": [],
}


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _emit(node: str, t0: float, ins: dict, out: dict,
          tools: list[dict], prov: str, errs: list[dict]) -> dict[str, Any]:
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


def _as_str_list(v: Any) -> list[str]:
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    try:
        return [str(x) for x in v]
    except TypeError:
        return []


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Coerce loose LLM output into the contract shape."""
    out: dict[str, Any] = dict(_EMPTY_ATOMS)
    for key in ("method", "object", "task", "scenario",
                "dataset_terms", "baseline_terms", "avoid_terms"):
        out[key] = _as_str_list(raw.get(key))
    # domain must be one allowed string; reject lists and unknown values.
    dom = raw.get("domain", "unknown")
    if isinstance(dom, list):
        dom = next((str(x).strip().lower() for x in dom if str(x).strip()), "unknown")
    dom = str(dom).strip().lower()
    out["domain"] = dom if dom in _ALLOWED_DOMAINS else "unknown"
    return out


def topic_parser_node(state: ResearchState) -> dict[str, Any]:
    """Parse topic -> topic_atoms. Skips LLM call if atoms already present."""
    topic = state.get("topic") or ""
    existing = state.get("topic_atoms")
    t0 = time.time()

    # Idempotency: a non-empty atom set means we already parsed this case.
    if existing and any(
        existing.get(k) for k in
        ("method", "object", "task", "scenario", "dataset_terms", "baseline_terms")
    ) and isinstance(existing.get("domain"), str):
        trace = _emit("topic_parser", t0,
                      {"topic_len": len(topic)}, {"skipped": True,
                                                   "n_method": len(existing.get("method", []))},
                      [{"tool": "re11_parser.llm", "mode": "skipped"}], "none", [])
        return {"trace_events": list(state.get("trace_events") or []) + [trace]}

    errors_out: list[dict[str, Any]] = []
    atoms: dict[str, Any] = dict(_EMPTY_ATOMS)
    tries = 0

    try:
        built = P.build(topic)
        tries += 1
        raw = call_json(
            built["user"],
            system=built["system"],
            profile="fast_json",
            max_tokens=2500,
            expected="dict",
            schema_hint=(
                'JSON object with keys: method/object/task/scenario/'
                'domain/dataset_terms/baseline_terms/avoid_terms; '
                'domain is a single string.'
            ),
        )
        atoms = _normalize(raw if isinstance(raw, dict) else {})
    except BaseException as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("topic_parser_node LLM call failed (%s); using empty atoms", kind)
        errors_out.append({"node": "topic_parser", "error": kind})

    trace = _emit("topic_parser", t0,
                  {"topic_len": len(topic)},
                  {"n_method": len(atoms.get("method", [])),
                   "n_object": len(atoms.get("object", [])),
                   "domain": atoms.get("domain")},
                  [{"tool": "re11_parser.llm", "attempts": tries}],
                  "fast_json", errors_out)

    return {
        "topic_atoms": atoms,
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors_out,
        "provider_profile": "fast_json",
    }

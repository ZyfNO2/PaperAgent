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
import os
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_parser as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


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


def _contains_negation(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("non-", "without ", "w/o ", "no ", "not "))


def _enforce_literal_topic_guards(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Preserve literal topic signals when the LLM drifts into adjacent terms."""
    out = dict(atoms)
    topic_text = (topic or "").strip()
    lowered = topic_text.lower()

    # If the topic itself is positive-form, drop invented negations.
    if topic_text and not _contains_negation(topic_text):
        for key in ("method", "object", "task", "scenario", "avoid_terms"):
            cleaned = []
            for item in out.get(key) or []:
                text = str(item).strip()
                if text and not _contains_negation(text):
                    cleaned.append(text)
            out[key] = cleaned

    explicit_rag = (
        "retrieval-augmented generation" in lowered
        or "检索增强生成" in topic_text
        or ("检索增强" in topic_text and "生成" in topic_text)
        or re.search(r"\brag\b", lowered) is not None
    )
    if explicit_rag:
        method = list(out.get("method") or [])
        if not any("retrieval-augmented generation" in str(x).lower() for x in method):
            method.insert(0, "retrieval-augmented generation")
        out["method"] = method
        baseline = list(out.get("baseline_terms") or [])
        if not any("retrieval-augmented generation" in str(x).lower() for x in baseline):
            baseline.insert(0, "retrieval-augmented generation")
        out["baseline_terms"] = baseline
        out["avoid_terms"] = [
            x for x in (out.get("avoid_terms") or [])
            if "retrieval" not in str(x).lower() or _contains_negation(str(x))
        ]
        object_terms = list(out.get("object") or [])
        if not any("knowledge base" in str(x).lower() for x in object_terms) and "知识库" in topic_text:
            object_terms.insert(0, "knowledge base")
        out["object"] = object_terms
        if out.get("domain") == "unknown":
            out["domain"] = "nlp_llm"

    if "question answering" in lowered or "问答" in topic_text or re.search(r"\bqa\b", lowered):
        task = list(out.get("task") or [])
        if not any("question answering" in str(x).lower() for x in task):
            task.insert(0, "question answering")
        out["task"] = task
        if out.get("domain") == "unknown":
            out["domain"] = "nlp_llm"

    if "knowledge base" in lowered or "知识库" in topic_text:
        scenario = list(out.get("scenario") or [])
        if not any("knowledge base" in str(x).lower() for x in scenario):
            scenario.insert(0, "knowledge base question answering")
        out["scenario"] = scenario

    if "enterprise" in lowered or "企业" in topic_text:
        scenario = list(out.get("scenario") or [])
        if not any("enterprise" in str(x).lower() for x in scenario):
            scenario.insert(0, "enterprise deployment")
        out["scenario"] = scenario

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
        return {"trace_events": [trace]}

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
            timeout=max(5, _env_int("TOPIC_PARSER_TIMEOUT_S", 60)),
            expected="dict",
            schema_hint=(
                'JSON object with keys: method/object/task/scenario/'
                'domain/dataset_terms/baseline_terms/avoid_terms; '
                'domain is a single string.'
            ),
        )
        atoms = _enforce_literal_topic_guards(
            topic,
            _normalize(raw if isinstance(raw, dict) else {}),
        )
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
        "trace_events": [trace],
        "errors": errors_out,
        "provider_profile": "fast_json",
    }

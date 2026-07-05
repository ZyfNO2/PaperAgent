"""LangGraph node A2 — search_planner_node.

Produces `search_plan` defining broad / focused / repair rounds of tool
calls. Idempotent when state already carries a non-empty search_plan AND no
errors force a repair.

Patch fields:
  search_plan        full replacement on re-plan
  trace_events       appended
  errors             appended  (only on LLMUnavailable)
  provider_profile   "fast_json"
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_planner as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable

logger = logging.getLogger(__name__)


_TOOLS = frozenset({"arxiv", "openalex", "crossref", "web", "github"})
_ROUNDS = frozenset({"broad", "focused", "repair", "seed_expansion"})


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


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _normalize_queries(queries: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(queries, list):
        return out
    for q in queries:
        if not isinstance(q, dict):
            continue
        tool = _as_str(q.get("tool")).lower()
        if tool not in _TOOLS:
            continue
        query = _as_str(q.get("query"))
        if not query:
            continue
        out.append({
            "tool": tool,
            "query": query,
            "why": _as_str(q.get("why")),
            "expected_evidence": _as_str(q.get("expected_evidence")),
            "stop_condition": _as_str(q.get("stop_condition")),
        })
    return out


def _normalize_rounds(rounds: Any) -> list[str]:
    if isinstance(rounds, str):
        rounds = [rounds]
    if not isinstance(rounds, list):
        return ["broad"]
    out = [str(r).strip().lower() for r in rounds if str(r).strip().lower() in _ROUNDS]
    return out or ["broad"]


def _needs_repair(state: ResearchState) -> bool:
    """Heuristic: if topic_parser / verify / dataset_repo / evidence_audit
    reported errors, we should re-plan rather than re-use the old plan."""
    for err in state.get("errors") or []:
        node = (err.get("node") or "").lower()
        if node in ("topic_parser", "verify", "dataset_repo",
                     "evidence_auditor", "retrieve"):
            return True
    return False


def search_planner_node(state: ResearchState) -> dict[str, Any]:
    """Produce search_plan. Skips LLM call when a valid plan already exists."""
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    existing_plan = state.get("search_plan") or {}
    t0 = time.time()

    has_plan = bool(existing_plan.get("queries")) and bool(existing_plan.get("rounds"))
    if has_plan and not _needs_repair(state):
        trace = _emit("search_planner", t0,
                      {"topic_len": len(topic)},
                      {"skipped": True,
                       "n_queries": len(existing_plan.get("queries") or [])},
                      [{"tool": "re11_planner.llm", "mode": "skipped"}],
                      "none", [])
        return {"trace_events": list(state.get("trace_events") or []) + [trace]}

    # Build prior_rounds for follow-up mode — pull the previous plan's queries
    # (and any negative_feedback already stored) so the next round can improve.
    prior_rounds: list[dict[str, Any]] | None = None
    if has_plan:
        prior_rounds = [{
            "queries": existing_plan.get("queries") or [],
            "rounds": existing_plan.get("rounds") or [],
            "negative_feedback": existing_plan.get("negative_feedback") or "",
        }]

    errors_out: list[dict[str, Any]] = []
    plan: dict[str, Any] = {"queries": [], "rounds": ["broad"], "negative_feedback": ""}
    tries = 0

    try:
        built = P.build(topic, atoms, prior_rounds=prior_rounds)
        tries += 1
        raw = call_json(
            built["user"],
            system=built["system"],
            profile="fast_json",
            max_tokens=4000,
            expected="dict",
            schema_hint=(
                '{"queries":[{tool,query,why,expected_evidence,stop_condition}...],'
                '"rounds":["broad"|"focused"|"repair"],'
                '"negative_feedback":str}'
            ),
        )
        if isinstance(raw, dict):
            queries = _normalize_queries(raw.get("queries"))
            plan = {
                "queries": queries,
                "rounds": _normalize_rounds(raw.get("rounds")),
                "negative_feedback": _as_str(raw.get("negative_feedback")),
            }
    except BaseException as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("search_planner_node LLM call failed (%s); using empty plan", kind)
        errors_out.append({"node": "search_planner", "error": kind})

    trace = _emit("search_planner", t0,
                  {"topic_len": len(topic), "has_prior": bool(prior_rounds)},
                  {"n_queries": len(plan.get("queries") or []),
                   "rounds": plan.get("rounds")},
                  [{"tool": "re11_planner.llm", "attempts": tries}],
                  "fast_json", errors_out)

    return {
        "search_plan": plan,
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors_out,
        "provider_profile": "fast_json",
    }

"""LangGraph node A3 — targeted_repair_node.

Targets a SINGLE failure slice (baseline_gap / dataset_gap / repo_gap /
paper_gap / metadata_mismatch / url_repair) and produces a new search_plan
with rounds=["repair"]. Caps total repairs via MAX_REPAIR_ROUNDS.

Inputs from state:
  - baseline_candidates / dataset_candidates / repo_candidates (counts)
  - paper_candidates + verified_papers (for quarantine/quality ratio)
  - evidence_audit (carries repair_rounds counter)
  - errors + rejected_candidate titles
  - search_plan.queries (prior queries the repair must not repeat)

Patch fields:
  search_plan            replacement with a repair-round plan
  evidence_audit         merged (repair_rounds+1, last_repair_type, repair_exhausted)
  repair_exhausted       set True when the round cap is reached
  trace_events           appended
  errors                 appended  (only on LLMUnavailable)
"""
from __future__ import annotations

import logging
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re12_repair as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable

logger = logging.getLogger(__name__)


MAX_REPAIR_ROUNDS = 2
REPAIR_TYPES = [
    "paper_gap_repair",
    "dataset_gap_repair",
    "repo_gap_repair",
    "baseline_gap_repair",
    "metadata_mismatch_repair",
    "url_repair",
]

_TOOLS = frozenset({"arxiv", "openalex", "crossref", "web", "github"})


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
    return "" if v is None else str(v).strip()


def _decide_repair_type(state: ResearchState) -> str:
    """Pick the dominant gap from current evidence counts + quarantine ratio."""
    baseline_n = len(state.get("baseline_candidates") or [])
    dataset_n = len(state.get("dataset_candidates") or [])
    repo_n = len(state.get("repo_candidates") or [])
    verified = len(state.get("verified_papers") or [])
    paper = len(state.get("paper_candidates") or [])

    quota_ratio = (paper - verified) / paper if paper else 0.0
    if baseline_n == 0 and (verified or paper):
        return "baseline_gap_repair"
    if dataset_n == 0 and verified:
        return "dataset_gap_repair"
    if repo_n == 0 and verified:
        return "repo_gap_repair"
    if quota_ratio > 0.4:
        return "paper_gap_repair"
    return "paper_gap_repair"


def _normalize(raw: dict[str, Any], repair_type: str) -> dict[str, Any]:
    queries = []
    if isinstance(raw, dict):
        for q in raw.get("queries") or []:
            if not isinstance(q, dict):
                continue
            tool = _as_str(q.get("tool")).lower()
            query = _as_str(q.get("query"))
            if tool not in _TOOLS or not query:
                continue
            queries.append({
                "tool": tool, "query": query,
                "why": _as_str(q.get("why")),
                "expected_evidence": _as_str(q.get("expected_evidence")),
                "stop_condition": _as_str(q.get("stop_condition")),
            })
    return {
        "queries": queries,
        "rounds": ["repair"],
        "negative_feedback": _as_str(
            raw.get("negative_feedback") if isinstance(raw, dict) else ""
        ) or f"targeted repair for {repair_type}",
    }


def targeted_repair_node(state: ResearchState) -> dict[str, Any]:
    """Produce a repair-round search_plan targeting the dominant evidence gap."""
    t0 = time.time()

    existing_audit = dict(state.get("evidence_audit") or {})
    current_round = int(existing_audit.get("repair_rounds") or 0)

    # Cap check — when exhausted, mark + no-op.
    if current_round >= MAX_REPAIR_ROUNDS:
        exhausted_audit = {
            **existing_audit,
            "repair_exhausted": True,
            "repair_rounds": current_round,
        }
        trace = _emit("targeted_repair", t0,
                      {"current_round": current_round},
                      {"exhausted": True}, [{"tool": "repair.cap_check"}],
                      "local", [])
        return {
            "repair_exhausted": True,
            "evidence_audit": exhausted_audit,
            "trace_events": list(state.get("trace_events") or []) + [trace],
        }

    # Compute gaps
    baseline_n = len(state.get("baseline_candidates") or [])
    dataset_n = len(state.get("dataset_candidates") or [])
    repo_n = len(state.get("repo_candidates") or [])
    gaps = {
        "baseline_n": baseline_n,
        "dataset_n": dataset_n,
        "repo_n": repo_n,
        "verified_papers_n": len(state.get("verified_papers") or []),
        "paper_candidates_n": len(state.get("paper_candidates") or []),
        "repair_round": current_round + 1,
        "max_repair_rounds": MAX_REPAIR_ROUNDS,
    }

    # Rejected titles: paper_candidates that did NOT become verified
    verified_titles = {
        (p.get("title") or p.get("name") or "").strip().lower()
        for p in (state.get("verified_papers") or [])
        if (p.get("title") or p.get("name"))
    }
    rejected_titles = [
        p.get("title") or p.get("name") or ""
        for p in (state.get("paper_candidates") or [])
        if (p.get("title") or p.get("name"))
        and (p.get("title") or p.get("name") or "").strip().lower()
        not in verified_titles
    ]

    # Prior queries the repair MUST NOT repeat
    prior_queries = [
        _as_str(q.get("query"))
        for q in ((state.get("search_plan") or {}).get("queries") or [])
        if _as_str(q.get("query"))
    ]

    repair_type = _decide_repair_type(state)
    topic = state.get("topic") or ""

    errors_out: list[dict[str, Any]] = []
    plan: dict[str, Any] = {"queries": [], "rounds": ["repair"],
                            "negative_feedback": f"targeted repair for {repair_type}"}
    tries = 0
    new_audit = {
        **existing_audit,
        "repair_rounds": current_round + 1,
        "last_repair_type": repair_type,
    }

    try:
        built = P.build(topic, gaps, rejected_titles, prior_queries)
        tries += 1
        raw = call_json(
            built["user"],
            system=built["system"],
            profile="fast_json",
            max_tokens=4000,
            expected="dict",
            schema_hint=(
                '{"queries":[{tool,query,why,expected_evidence,stop_condition}...],'
                '"rounds":["repair"],'
                '"negative_feedback":str}'
            ),
        )
        plan = _normalize(raw if isinstance(raw, dict) else {}, repair_type)
    except BaseException as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("targeted_repair_node LLM call failed (%s); using empty repair plan", kind)
        errors_out.append({"node": "targeted_repair", "error": kind})

    trace = _emit("targeted_repair", t0,
                  {"current_round": current_round, "repair_type": repair_type},
                  {"n_queries": len(plan.get("queries") or []),
                   "rounds": plan.get("rounds")},
                  [{"tool": "re12_repair.llm", "attempts": tries}],
                  "fast_json", errors_out)

    return {
        "search_plan": plan,
        "evidence_audit": new_audit,
        "trace_events": list(state.get("trace_events") or []) + [trace],
        "errors": list(state.get("errors") or []) + errors_out,
        "provider_profile": "fast_json",
    }

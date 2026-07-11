"""LangGraph node A3 — targeted_repair_node (Re3.0: Reflection strategy switch).

Targets a SINGLE failure slice and produces a new search_plan with
rounds=["repair"]. Re3.0 adds strategy switching (synonym/broaden/switch_tool)
inspired by ARS failure_paths F2/F8 and ARC's PIVOT/REFINE.

Re6.1 Fix A: emits explicit `repair_outcome` so the conditional edge can
route empty-repair cases to quality_gate (weak promote) or final
recommendation instead of looping back to paper_retriever for nothing.

Inputs from state:
  - baseline_candidates / dataset_candidates / repo_candidates (counts)
  - paper_candidates + verified_papers (for quarantine/quality ratio)
  - evidence_audit (carries repair_rounds counter)
  - errors + rejected_candidate titles
  - search_plan.queries (prior queries the repair must not repeat)

Patch fields:
  search_plan            replacement with a repair-round plan (includes strategy)
  evidence_audit         merged (repair_rounds+1, last_repair_type, repair_exhausted)
  repair_exhausted       set True when the round cap is reached
  repair_outcome         "queries_ready" | "no_query" | "exhausted"
  repair_no_query_reason human-readable explanation when no_query
  repair_query_ids       deduplicated query identifier list
  trace_events           appended
  errors                 appended  (only on LLMUnavailable)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re12_repair as P
from apps.api.app.services.llm_router import call_json, LLMUnavailable
from ._util import emit_trace as _emit

logger = logging.getLogger(__name__)


MAX_REPAIR_ROUNDS = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))
REPAIR_TYPES = [
    "paper_gap_repair",
    "dataset_gap_repair",
    "repo_gap_repair",
    "baseline_gap_repair",
    "metadata_mismatch_repair",
    "url_repair",
]

_TOOLS = frozenset({"arxiv", "openalex", "crossref", "github", "semantic_scholar", "huggingface", "core", "datacite", "pubmed"})

# Re6.1 Fix A: feature flag for zero-accept weak promotion policy
_ZERO_ACCEPT_WEAK_POLICY = os.environ.get("PAPERAGENT_ZERO_ACCEPT_WEAK_POLICY", "repair")
_WEAK_PROMOTE_MIN = max(1, int(os.environ.get("PAPERAGENT_WEAK_PROMOTE_MIN", "3")))


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _use_unified() -> bool:
    return os.environ.get("TARGETED_REPAIR_USE_UNIFIED_ROUTER", "0") == "1"


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


def _infer_strategy(round_num: int, gaps: dict[str, Any]) -> str:
    """Re3.0: Infer search strategy for this repair round.

    Round 0 → "synonym" (try different keywords)
    Round 1 → "broaden" (remove qualifiers, search broader)
    Failed adapters → "switch_tool"
    """
    failed = gaps.get("failed_adapters") or []
    if failed and round_num > 0:
        return "switch_tool"
    if round_num == 0:
        return "synonym"
    return "broaden"


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


def _dedup_queries(queries: list[dict[str, Any]],
                   prior_queries: list[str] | None = None) -> list[dict[str, Any]]:
    """Deduplicate queries by (tool, query) pair, excluding prior queries.

    A query is dropped if its text (case-insensitive) matches any entry in
    ``prior_queries`` — the LLM is explicitly told not to repeat, so any
    overlap counts as "no new intent".
    """
    prior_normalized = {q.lower().strip() for q in (prior_queries or []) if q.strip()}
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for q in queries:
        text = q.get("query", "").lower().strip()
        if text in prior_normalized:
            continue  # Skip queries that were already tried
        key = (q.get("tool", ""), text)
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
    return out


def targeted_repair_node(state: ResearchState) -> dict[str, Any]:
    """Produce a repair-round search_plan targeting the dominant evidence gap.

    Re6.1 Fix A: emits repair_outcome so the conditional edge routes:
      - queries_ready → paper_retriever (normal)
      - no_query       → quality_gate (weak promote) or final_recommendation
      - exhausted      → quality_gate (let gate decide: promote or block)
    """
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
                      "local", [],
                      state_keys=["repair_exhausted", "evidence_audit",
                                  "trace_events"])
        return {
            "repair_exhausted": True,
            "repair_outcome": "exhausted",
            "repair_no_query_reason": f"repair round cap ({MAX_REPAIR_ROUNDS}) reached",
            "repair_query_ids": [],
            "evidence_audit": exhausted_audit,
            "trace_events": [trace],
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

    # Fix 6 (Re2.3): pass per-adapter status so the LLM knows which adapters failed
    prior_traces = state.get("trace_events") or []
    retrieve_traces = [
        t for t in prior_traces
        if t.get("node") in ("retrieve", "paper_retriever")
    ]
    if retrieve_traces:
        last_summary = retrieve_traces[-1].get("output_summary") or {}
        gaps["per_adapter"] = last_summary.get("per_adapter", {})
        gaps["failed_adapters"] = last_summary.get("failed_adapters", [])

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

    prov = "fast_json"
    try:
        built = P.build(topic, gaps, rejected_titles, prior_queries)
        tries += 1
        if _use_unified():
            from apps.api.app.services.router import call_with_contract
            from apps.api.app.services.router.model_policy import TaskRole
            from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
            register_graph_contracts()
            contract_result = call_with_contract(
                built["user"],
                system=built["system"],
                contract_id="targeted-repair/v1",
                task_role=TaskRole.search_control,
                max_tokens=4000,
                timeout=max(5, _env_int("TARGETED_REPAIR_TIMEOUT_S", 60)),
            )
            prov = "unified_router"
            if contract_result.success and isinstance(contract_result.content, dict):
                raw = contract_result.content
            else:
                logger.warning("targeted_repair unified_router failed: %s", contract_result.error)
                raw = {}
        else:
            raw = call_json(
                built["user"],
                system=built["system"],
                profile="fast_json",
                max_tokens=4000,
                timeout=max(5, _env_int("TARGETED_REPAIR_TIMEOUT_S", 60)),
                expected="dict",
                schema_hint=(
                    '{"queries":[{tool,query,why,expected_evidence,stop_condition}...],'
                    '"rounds":["repair"],'
                    '"negative_feedback":str,'
                    '"strategy":"synonym|broaden|switch_tool"}'
                ),
            )
        plan = _normalize(raw if isinstance(raw, dict) else {}, repair_type)
        # Re3.0: record strategy from LLM or infer from repair type
        if isinstance(raw, dict) and raw.get("strategy"):
            plan["strategy"] = raw["strategy"]
        else:
            plan["strategy"] = _infer_strategy(current_round, gaps)
    except Exception as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("targeted_repair_node LLM call failed (%s); using empty repair plan", kind)
        errors_out.append({"node": "targeted_repair", "error": kind})

    # Re6.1 Fix A: deduplicate + outcome classification
    plan["queries"] = _dedup_queries(plan.get("queries") or [], prior_queries)
    n_queries = len(plan.get("queries") or [])

    # Build query ID list for traceability
    repair_query_ids = [
        f"{q.get('tool', '?')}:{q.get('query', '')[:60]}"
        for q in plan.get("queries") or []
    ]

    if n_queries > 0:
        repair_outcome = "queries_ready"
        repair_no_query_reason = ""
    else:
        repair_outcome = "no_query"
        repair_no_query_reason = (
            "LLM returned 0 valid queries after normalization/dedup; "
            "no new search intent to forward to paper_retriever"
        )

    trace = _emit("targeted_repair", t0,
                  {"current_round": current_round, "repair_type": repair_type},
                  {"n_queries": n_queries,
                   "repair_outcome": repair_outcome,
                   "rounds": plan.get("rounds")},
                  [{"tool": "targeted-repair/v1" if prov == "unified_router" else "re12_repair.llm",
                    "attempts": tries, "mode": prov}],
                  prov, errors_out,
                  state_keys=["search_plan", "evidence_audit",
                              "trace_events", "errors", "provider_profile",
                              "repair_outcome", "repair_no_query_reason",
                              "repair_query_ids"])

    return {
        "search_plan": plan,
        "evidence_audit": new_audit,
        "repair_outcome": repair_outcome,
        "repair_no_query_reason": repair_no_query_reason,
        "repair_query_ids": repair_query_ids,
        "trace_events": [trace],
        "errors": errors_out,
        "provider_profile": prov,
    }

"""LangGraph node A2 - search_planner_node.

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
import os
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_planner as P
from apps.api.app.services.llm_router import LLMUnavailable, call_json
from apps.api.app.services.agents.graph.re80_schema import (
    make_evidence_gap,
    validate_evidence_gap,
)
from ._util import now_iso as _now_iso

logger = logging.getLogger(__name__)


_TOOLS = frozenset({"arxiv", "openalex", "crossref", "github", "semantic_scholar", "huggingface", "core", "datacite", "pubmed"})
_ROUNDS = frozenset({"broad", "focused", "repair", "seed_expansion"})

# Re8.0 WP4: lane → (gap_type, [tools], success_condition, expected_evidence)
# Each Search Lane is bound to an EvidenceGap so the search_agent can record
# evidence_delta and resolve the gap when results arrive.
_LANE_GAP_SPEC: dict[str, tuple[str, tuple[str, ...], str, str]] = {
    "anchor_reference": (
        "existence",
        ("openalex", "crossref"),
        "find 1+ origin or citation-chain paper",
        "anchor / origin papers",
    ),
    "competing_baseline": (
        "competing_method",
        ("arxiv", "semantic_scholar"),
        "find 2+ competing baseline papers",
        "same-task baseline papers",
    ),
    "mechanism_module": (
        "mechanism",
        ("arxiv", "openalex"),
        "find 1+ mechanism or module paper",
        "mechanism / module papers",
    ),
    "resource": (
        "repo",
        ("github", "huggingface"),
        "find 1+ repo or dataset",
        "code repos or datasets",
    ),
    "counter_evidence": (
        "counter_evidence",
        ("arxiv", "openalex"),
        "find 1+ counter-evidence or limitation paper",
        "counter-evidence papers",
    ),
}


def _use_unified() -> bool:
    return os.environ.get("SEARCH_PLANNER_USE_UNIFIED_ROUTER", "0") == "1"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _emit(
    node: str,
    t0: float,
    ins: dict,
    out: dict,
    tools: list[dict],
    prov: str,
    errs: list[dict],
    state_keys: list[str] | None = None,
) -> dict[str, Any]:
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
        "state_keys": state_keys or [],
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
        entry: dict[str, str] = {
            "tool": tool,
            "query": query,
            "why": _as_str(q.get("why")),
            "expected_evidence": _as_str(q.get("expected_evidence")),
            "stop_condition": _as_str(q.get("stop_condition")),
        }
        # Re8.0 WP4: preserve gap-binding fields if present
        gap_id = _as_str(q.get("gap_id"))
        if gap_id:
            entry["gap_id"] = gap_id
            entry["success_condition"] = _as_str(q.get("success_condition"))
            entry["lane_id"] = _as_str(q.get("lane_id"))
        out.append(entry)
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
        if node in ("topic_parser", "verify", "dataset_repo", "evidence_auditor", "retrieve"):
            return True
    return False


def _template_plan(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    """Template-based search plan: builds queries directly from atoms without LLM.

    Used when ``PAPERAGENT_SKIP_SEARCH_PLANNER=true``. Generates a deterministic
    set of OpenAlex / arxiv queries from method/object/task/dataset atoms.
    """
    import re as _re

    cjk = _re.compile(r"[\u4e00-\u9fff]")
    lowered_topic = (topic or "").lower()
    # Keep CJK terms but also extract English keywords for search
    method = [str(k).strip() for k in (atoms.get("method") or []) if k]
    obj = [str(k).strip() for k in (atoms.get("object") or []) if k]
    ds_terms = [str(k).strip() for k in (atoms.get("dataset_terms") or []) if k]
    baseline = [str(k).strip() for k in (atoms.get("baseline_terms") or []) if k]
    domain = str(atoms.get("domain") or "unknown").strip().lower()

    queries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _add(tool: str, query: str, why: str, ev: str, stop: str) -> None:
        q = query.strip()
        key = (tool.lower(), q.lower())
        if not q or key in seen or len(q) < 2:
            return
        seen.add(key)
        queries.append(
            {
                "tool": tool,
                "query": q,
                "why": why,
                "expected_evidence": ev,
                "stop_condition": stop,
            },
        )

    def _compact(term: str) -> str:
        text = " ".join((term or "").split())
        if not text:
            return ""
        parts = [p for p in _re.split(r"[\s,/;:()]+", text) if p]
        return " ".join(parts[:8])

    explicit_rag = (
        "retrieval-augmented generation" in lowered_topic
        or "检索增强生成" in topic
        or ("检索增强" in topic and "生成" in topic)
        or _re.search(r"\brag\b", lowered_topic) is not None
    )
    if explicit_rag:
        _add(
            "openalex",
            "retrieval-augmented generation enterprise knowledge base question answering",
            "explicit rag topic",
            "rag / enterprise qa baseline papers",
            "n>=5",
        )
        _add(
            "arxiv",
            "retrieval-augmented generation knowledge base question answering",
            "explicit rag topic recent papers",
            "recent rag qa papers",
            "n>=5",
        )
        _add(
            "openalex",
            "enterprise knowledge base question answering",
            "explicit enterprise knowledge-base qa topic",
            "enterprise qa papers",
            "n>=5",
        )

    for m in method[:2]:
        for o in obj[:1]:
            _add("openalex", _compact(f"{m} {o}"), "baseline method+object", "baseline papers", "n>=5")
    # Crossref: combined method+object for broader academic coverage
    if method and obj:
        _add("crossref", _compact(f"{method[0]} {obj[0]}"), "crossref method+object", "published papers", "n>=5")
        # Re2.1: S2 as primary search source (high-citation papers)
        _add("semantic_scholar", _compact(f"{method[0]} {obj[0]}"), "s2 method+object", "high-citation papers", "n>=5")
    for d in ds_terms[:2]:
        _add("openalex", _compact(f"{d} dataset benchmark"), "dataset", "dataset papers", "n>=3")
    for b in baseline[:1]:
        _add("openalex", _compact(f"{b} survey review"), "baseline", "survey or baseline papers", "n>=3")
    if method:
        # Compose a combined query: method + object + task for precision
        combined_parts = method[:1] + obj[:1]
        task_terms = [str(k).strip() for k in (atoms.get("task") or []) if k and not cjk.search(str(k))]
        if task_terms:
            combined_parts.append(task_terms[0])
        _add("arxiv", _compact(" ".join(combined_parts)), "broad arxiv (method+object+task)", "recent preprints", "n>=8")
    if domain == "unknown" and baseline:
        _add("openalex", _compact(baseline[0]), "domain unknown baseline fallback", "any baseline papers", "n>=4")
    if domain == "unknown" and obj:
        _add("openalex", _compact(obj[0]), "domain unknown object fallback", "object-specific papers", "n>=4")
    if not queries:
        # Re3.0 Fix 1.5: no "deep learning" fallback; use topic text directly
        # For Chinese topics with no atoms, extract English keywords from topic
        en_terms = _re.findall(r'[A-Za-z][A-Za-z0-9\-]{1,}', topic or "")
        en_terms = [t for t in en_terms if t.lower() not in
                    ("based", "on", "via", "using", "for", "the", "and", "of", "research", "study")]
        if en_terms:
            query = " ".join(en_terms[:3])
            _add("arxiv", query, "topic English keywords", "any relevant papers", "n>=5")
        elif topic:
            # Use topic text directly (may be Chinese, but adapters can handle it)
            _add("arxiv", topic[:100], "fallback topic text", "any relevant papers", "n>=5")

    return {
        "queries": queries[:10],
        "rounds": ["broad", "focused"],
        "negative_feedback": "",
    }


# ── Re8.0 WP4: Evidence Gap driven search plan ─────────────────────────────

def _create_lane_gaps(
    lanes: list[dict[str, Any]],
    seed_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create EvidenceGap objects for lanes that don't have a gap_id yet.

    Returns ``(updated_lanes, new_gaps)``. Lanes that already carry a
    ``gap_id`` are left untouched; lanes with ``gap_id=None`` get a new
    gap created and their ``gap_id`` field populated.
    """
    new_gaps: list[dict[str, Any]] = []
    updated: list[dict[str, Any]] = []
    for idx, lane in enumerate(lanes):
        lane_id = lane.get("lane_id", f"lane_{idx}")
        existing_gid = lane.get("gap_id")
        if existing_gid:
            updated.append(lane)
            continue
        spec = _LANE_GAP_SPEC.get(lane_id)
        if not spec:
            # Unknown lane — skip gap creation, keep lane as-is
            updated.append(lane)
            continue
        gap_type, _tools, success_cond, _ev = spec
        gid = f"gap-{seed_id}-{lane_id}"
        gap = make_evidence_gap(
            gap_id=gid,
            question=f"Search Lane '{lane_id}': {lane.get('description', '')}",
            gap_type=gap_type,
            why_needed=(
                f"WP3 Search Lane for seed '{seed_id}' — "
                f"queries: {lane.get('queries', [])[:2]}"
            ),
            success_condition=success_cond,
            status="open",
        )
        errs = validate_evidence_gap(gap)
        if errs:
            logger.warning("lane gap validation failed for %s: %s", gid, errs)
        new_gaps.append(gap)
        new_lane = dict(lane)
        new_lane["gap_id"] = gid
        updated.append(new_lane)
    return updated, new_gaps


def _seeded_plan(
    lanes: list[dict[str, Any]],
    seed_id: str,
) -> dict[str, Any]:
    """Build a gap-bound search plan from Re8.0 Search Lanes.

    Each lane's queries are expanded into one or more search_plan query
    entries, each carrying ``gap_id``, ``success_condition``, and
    ``lane_id`` so the search_agent can record evidence_delta per gap.
    """
    queries: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for lane in lanes:
        lane_id = lane.get("lane_id", "unknown")
        gap_id = lane.get("gap_id") or f"gap-{seed_id}-{lane_id}"
        spec = _LANE_GAP_SPEC.get(lane_id)
        if not spec:
            continue
        gap_type, lane_tools, success_cond, expected_ev = spec
        for qtext in (lane.get("queries") or []):
            qtext = (qtext or "").strip()
            if not qtext:
                continue
            # Distribute query across the lane's tools (max 2 to keep
            # the plan compact). Each (tool, query) pair is one entry.
            for tool in lane_tools[:2]:
                key = (tool.lower(), qtext.lower())
                if key in seen:
                    continue
                seen.add(key)
                queries.append({
                    "tool": tool,
                    "query": qtext,
                    "why": f"{lane_id}: {lane.get('description', '')[:60]}",
                    "expected_evidence": expected_ev,
                    "stop_condition": "n>=1",
                    "gap_id": gap_id,
                    "success_condition": success_cond,
                    "lane_id": lane_id,
                })
    # Cap at 12 queries to keep the search budget reasonable
    return {
        "queries": queries[:12],
        "rounds": ["broad", "focused"],
        "negative_feedback": "",
        "gap_bound": True,  # flag for search_agent
    }


def search_planner_node(state: ResearchState) -> dict[str, Any]:
    """Produce search_plan. Skips LLM call when a valid plan already exists."""
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    existing_plan = state.get("search_plan") or {}
    t0 = time.time()

    # Re8.0 WP4: seeded_research path — build gap-bound plan from Search Lanes.
    # This takes priority over template/LLM paths when entry_mode is
    # "seeded_research" and search_lanes are present. The plan binds each
    # query to an EvidenceGap so search_agent can record evidence_delta.
    entry_mode = state.get("entry_mode", "topic_only")
    search_lanes: list[dict[str, Any]] = list(state.get("search_lanes") or [])
    if entry_mode == "seeded_research" and search_lanes:
        # Determine seed_id from first seed card (for gap_id namespacing)
        seed_cards = state.get("seed_cards") or []
        seed_id = (seed_cards[0].get("seed_id", "seed") if seed_cards else "seed")
        # Fill in gap_ids on lanes that don't have them yet
        updated_lanes, new_gaps = _create_lane_gaps(search_lanes, seed_id)
        plan = _seeded_plan(updated_lanes, seed_id)
        result: dict[str, Any] = {
            "search_plan": plan,
            "trace_events": [_emit(
                "search_planner",
                t0,
                {"topic_len": len(topic), "mode": "seeded_gap_bound",
                 "entry_mode": entry_mode, "n_lanes": len(search_lanes)},
                {"n_queries": len(plan.get("queries") or []),
                 "rounds": plan.get("rounds"), "gap_bound": True,
                 "n_new_gaps": len(new_gaps)},
                [{"tool": "search_planner.seeded_gap_bound"}],
                "local",
                [],
                state_keys=["search_plan", "search_lanes", "evidence_gaps",
                            "trace_events", "errors", "provider_profile"],
            )],
            "errors": [],
            "provider_profile": "local",
        }
        # Update lanes with gap_ids + emit new gaps so search_agent can
        # track resolution.
        if updated_lanes != search_lanes:
            result["search_lanes"] = updated_lanes
        if new_gaps:
            existing_gaps = list(state.get("evidence_gaps") or [])
            result["evidence_gaps"] = existing_gaps + new_gaps
        return result

    has_plan = bool(existing_plan.get("queries")) and bool(existing_plan.get("rounds"))
    if has_plan and not _needs_repair(state):
        trace = _emit(
            "search_planner",
            t0,
            {"topic_len": len(topic)},
            {"skipped": True, "n_queries": len(existing_plan.get("queries") or [])},
            [{"tool": "re11_planner.llm", "mode": "skipped"}],
            "none",
            [],
            state_keys=["trace_events"],
        )
        return {"trace_events": [trace]}

    # Re5.X: tri-state config — "template" (default), "llm", "experiment"
    _planner_mode = __import__("os").environ.get("PAPERAGENT_SEARCH_PLANNER", "template").lower().strip()
    # Backward compat: PAPERAGENT_SKIP_SEARCH_PLANNER=true → "template"
    _old_skip = __import__("os").environ.get("PAPERAGENT_SKIP_SEARCH_PLANNER", "")
    if _old_skip.lower() == "true" and _planner_mode == "template":
        pass  # default already
    elif _old_skip.lower() == "false":
        _planner_mode = "llm"
    skip_llm = _planner_mode in ("template", "experiment")
    if skip_llm and atoms:
        plan = _template_plan(topic, atoms)
        trace = _emit(
            "search_planner",
            t0,
            {"topic_len": len(topic), "mode": "template"},
            {"n_queries": len(plan.get("queries") or []), "rounds": plan.get("rounds")},
            [{"tool": "search_planner.template"}],
            "local",
            [],
            state_keys=["search_plan", "trace_events", "errors",
                        "provider_profile"],
        )
        return {
            "search_plan": plan,
            "trace_events": [trace],
            "errors": [],
            "provider_profile": "local",
        }

    prior_rounds: list[dict[str, Any]] | None = None
    if has_plan:
        prior_rounds = [
            {
                "queries": existing_plan.get("queries") or [],
                "rounds": existing_plan.get("rounds") or [],
                "negative_feedback": existing_plan.get("negative_feedback") or "",
            },
        ]

    errors_out: list[dict[str, Any]] = []
    plan: dict[str, Any] = {"queries": [], "rounds": ["broad"], "negative_feedback": ""}
    tries = 0
    prov = "fast_json"

    try:
        built = P.build(topic, atoms, prior_rounds=prior_rounds)
        tries += 1
        raw: dict[str, Any] | None = None
        if _use_unified():
            from apps.api.app.services.router import call_with_contract
            from apps.api.app.services.router.model_policy import TaskRole
            from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
            register_graph_contracts()
            contract_result = call_with_contract(
                built["user"],
                system=built["system"],
                contract_id="search-plan/v1",
                task_role=TaskRole.search_control,
                max_tokens=4000,
                timeout=max(5, _env_int("SEARCH_PLANNER_TIMEOUT_S", 60)),
            )
            prov = "unified_router"
            if contract_result.success and isinstance(contract_result.content, dict):
                raw = contract_result.content
            else:
                logger.warning("search_planner unified_router failed: %s", contract_result.error)
        else:
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
    except Exception as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("search_planner_node LLM call failed (%s); using empty plan", kind)
        errors_out.append({"node": "search_planner", "error": kind})

    trace = _emit(
        "search_planner",
        t0,
        {"topic_len": len(topic), "has_prior": bool(prior_rounds)},
        {"n_queries": len(plan.get("queries") or []), "rounds": plan.get("rounds")},
        [{"tool": "re11_planner.llm" if prov == "fast_json" else "search-plan/v1",
          "mode": prov, "attempts": tries}],
        prov,
        errors_out,
        state_keys=["search_plan", "trace_events", "errors",
                    "provider_profile"],
    )

    return {
        "search_plan": plan,
        "trace_events": [trace],
        "errors": errors_out,
        "provider_profile": prov,
    }

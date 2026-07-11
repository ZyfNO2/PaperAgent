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
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from apps.api.app.services.agents.prompts import re11_planner as P
from apps.api.app.services.llm_router import LLMUnavailable, call_json
from ._util import now_iso as _now_iso

logger = logging.getLogger(__name__)


_TOOLS = frozenset({"arxiv", "openalex", "crossref", "github", "semantic_scholar", "huggingface", "core", "datacite", "pubmed"})
_ROUNDS = frozenset({"broad", "focused", "repair", "seed_expansion"})


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
        out.append(
            {
                "tool": tool,
                "query": query,
                "why": _as_str(q.get("why")),
                "expected_evidence": _as_str(q.get("expected_evidence")),
                "stop_condition": _as_str(q.get("stop_condition")),
            },
        )
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


def search_planner_node(state: ResearchState) -> dict[str, Any]:
    """Produce search_plan. Skips LLM call when a valid plan already exists."""
    topic = state.get("topic") or ""
    atoms = state.get("topic_atoms") or {}
    existing_plan = state.get("search_plan") or {}
    t0 = time.time()

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
    except Exception as exc:  # noqa: BLE001
        kind = "LLMUnavailable" if isinstance(exc, LLMUnavailable) else type(exc).__name__
        logger.warning("search_planner_node LLM call failed (%s); using empty plan", kind)
        errors_out.append({"node": "search_planner", "error": kind})

    trace = _emit(
        "search_planner",
        t0,
        {"topic_len": len(topic), "has_prior": bool(prior_rounds)},
        {"n_queries": len(plan.get("queries") or []), "rounds": plan.get("rounds")},
        [{"tool": "re11_planner.llm", "attempts": tries}],
        "fast_json",
        errors_out,
        state_keys=["search_plan", "trace_events", "errors",
                    "provider_profile"],
    )

    return {
        "search_plan": plan,
        "trace_events": [trace],
        "errors": errors_out,
        "provider_profile": "fast_json",
    }

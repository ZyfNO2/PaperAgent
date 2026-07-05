"""LangGraph node: quality_filter — LLM-based paper authenticity filtering.

Sits between paper_retriever and verify. Uses LLM to judge whether each
candidate is a real academic paper (not a glossary/concept/figure entry).
Heuristic regex fallback only when LLM is unavailable.
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

# Heuristic fallback patterns (from Re1.2 pollution data — NOT a domain blacklist)
_NON_PAPER_PATTERNS = [
    r"(?i)term\s*entry",
    r"(?i)core\s*concept",
    r"(?i)input\s*classification",
    r"(?i)terminology\s*entry",
    r"(?i)concept\s*entry",
    r"(?i)term\s*assessment",
    r"(?i)term\s*list",
    r"(?i)term\s*validation",
    r"(?i)input\s*evaluation",
    r"(?i)input\s*technical\s*keywords",
    r"(?i)^figure\s*\d+",
    r"(?i)^table\s*\d+",
    r"(?i)^supplemental\s*information",
]
_COMPILED_PATTERNS = [re.compile(p) for p in _NON_PAPER_PATTERNS]

_BATCH_SIZE = 8


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _heuristic_filter(candidates: list[dict[str, Any]]) -> list[tuple[int, bool, str]]:
    """Fallback when LLM unavailable. Returns [(index, is_paper, reason)]."""
    results: list[tuple[int, bool, str]] = []
    trusted_url = re.compile(r"(arxiv\.org|doi\.org|openalex\.org|semanticscholar\.org)", re.I)
    for i, c in enumerate(candidates):
        title = (c.get("title") or c.get("name") or "").strip()
        if len(title) < 10:
            results.append((i, False, "title too short (<10 chars)"))
            continue
        matched = False
        for pat in _COMPILED_PATTERNS:
            if pat.search(title):
                results.append((i, False, f"matches non-paper pattern: {pat.pattern}"))
                matched = True
                break
        if matched:
            continue
        # Keep —宁可放过, 不可误杀
        url = c.get("url") or ""
        if url and trusted_url.search(url):
            results.append((i, True, "has trusted academic URL"))
        else:
            results.append((i, True, "passed heuristic checks"))
    return results


def _call_llm_batch(candidates: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Call LLM for a batch. Returns list of {index, is_paper, reason} or None on failure."""
    from apps.api.app.services import llm_router
    from apps.api.app.services.agents.prompts import re13_quality_filter as P

    built = P.build_batch(candidates)
    try:
        out = llm_router.call_json(
            built["user"],
            system=built["system"],
            profile="fast_json",
            max_tokens=2000,
            timeout=30,
            expected="list",
            schema_hint='JSON array of objects: [{"index": int, "is_paper": bool, "reason": str}]',
        )
        if isinstance(out, list):
            return [v for v in out if isinstance(v, dict)]
        if isinstance(out, dict):
            # Maybe wrapped
            for key in ("results", "items", "papers"):
                if isinstance(out.get(key), list):
                    return [v for v in out[key] if isinstance(v, dict)]
            return [out]
        return None
    except Exception as exc:
        logger.warning("quality_filter LLM call failed: %s", type(exc).__name__)
        return None


def quality_filter_node(state: ResearchState) -> dict[str, Any]:
    """Filter paper_candidates for real academic papers using LLM."""
    t0 = time.time()
    candidates = list(state.get("paper_candidates") or [])

    trace: dict[str, Any] = {
        "node": "quality_filter",
        "started_at": _now_iso(),
        "input_summary": {"n_candidates": len(candidates)},
        "output_summary": {},
        "tool_calls": [],
        "errors": [],
        "provider": "fast_json",
    }

    if not candidates:
        trace["ended_at"] = _now_iso()
        trace["elapsed_s"] = round(time.time() - t0, 3)
        trace["output_summary"] = {"kept": 0, "dropped": 0}
        return {
            "paper_candidates": [],
            "filter_results": {"total": 0, "kept": 0, "dropped": 0, "dropped_items": []},
            "trace_events": list(state.get("trace_events") or []) + [trace],
        }

    # Batch LLM calls
    batches = [candidates[i:i + _BATCH_SIZE] for i in range(0, len(candidates), _BATCH_SIZE)]
    llm_results: list[dict[str, Any]] = []
    llm_failed = False

    for batch in batches:
        result = _call_llm_batch(batch)
        if result is None:
            llm_failed = True
            break
        llm_results.extend(result)
        trace["tool_calls"].append({"tool": "re13_quality_filter.llm", "batch_size": len(batch)})

    # Build index -> is_paper map
    is_paper_map: dict[int, bool] = {}
    reason_map: dict[int, str] = {}

    if llm_failed or not llm_results:
        # Heuristic fallback
        logger.warning("quality_filter using heuristic fallback (LLM unavailable)")
        trace["tool_calls"].append({"tool": "quality_filter.heuristic_fallback"})
        for idx, is_paper, reason in _heuristic_filter(candidates):
            is_paper_map[idx] = is_paper
            reason_map[idx] = reason
    else:
        for item in llm_results:
            idx = item.get("index")
            if isinstance(idx, int) and 0 <= idx < len(candidates):
                is_paper_map[idx] = bool(item.get("is_paper", True))
                reason_map[idx] = item.get("reason", "")

    # Apply filter
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        if is_paper_map.get(i, True):  # default keep if missing
            kept.append(c)
        else:
            dropped.append({
                "title": (c.get("title") or c.get("name") or "").strip(),
                "reason": reason_map.get(i, "LLM judged as non-paper"),
            })

    # Safety: never drop all candidates
    if not kept and candidates:
        logger.warning("quality_filter dropped ALL candidates — keeping all as safety measure")
        kept = list(candidates)
        dropped = []

    trace["ended_at"] = _now_iso()
    trace["elapsed_s"] = round(time.time() - t0, 3)
    trace["output_summary"] = {"kept": len(kept), "dropped": len(dropped)}
    if llm_failed:
        trace["errors"].append({"phase": "llm_call", "error": "LLMUnavailable", "action": "heuristic_fallback"})

    filter_results = {
        "total": len(candidates),
        "kept": len(kept),
        "dropped": len(dropped),
        "dropped_items": dropped,
    }

    return {
        "paper_candidates": kept,
        "filter_results": filter_results,
        "trace_events": list(state.get("trace_events") or []) + [trace],
    }

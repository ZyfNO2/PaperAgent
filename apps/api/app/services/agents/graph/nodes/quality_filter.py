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
    r"(?i)^figure\s*\d+:?",   # "Figure 3:" or "Figure 3"
    r"(?i)^table\s*\d+:?",    # "Table 2:" or "Table 2"
    r"(?i)^fig\.?\s*\d+:?",   # "Fig. 3:" or "Fig 3"
    r"(?i)^tab\.?\s*\d+:?",   # "Tab. 2:" or "Tab 2"
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


def _pre_filter(candidates: list[dict[str, Any]]) -> list[tuple[int, bool, str]]:
    """Deterministic pre-filter: trusted URLs → keep; non-paper patterns → drop.

    Only candidates that don't match either category go to LLM.
    """
    trusted_url = re.compile(r"(arxiv\.org|doi\.org|openalex\.org|semanticscholar\.org|sem\.scholar\.org)", re.I)
    results: list[tuple[int, bool, str]] = []
    for i, c in enumerate(candidates):
        title = (c.get("title") or c.get("name") or "").strip()
        url = c.get("url") or ""
        source = c.get("source") or ""
        doi = c.get("doi") or ""

        # Check non-paper patterns first
        is_non_paper = False
        for pat in _COMPILED_PATTERNS:
            if pat.search(title):
                results.append((i, False, f"matches non-paper pattern: {pat.pattern}"))
                is_non_paper = True
                break
        if is_non_paper:
            continue

        # Trusted URL → definitely a paper (don't let LLM second-guess)
        if url and trusted_url.search(url):
            results.append((i, True, "has trusted academic URL (arxiv/doi/openalex/s2)"))
            continue
        # DOI present → definitely a paper
        if doi:
            results.append((i, True, "has DOI"))
            continue
        # Source is a known academic source — but Crossref often returns books/course material
        if source and source.lower() in ("arxiv", "openalex", "semantic_scholar"):
            results.append((i, True, f"from academic source: {source}"))
            continue
        # Crossref: keep but flag for LLM check (often returns books, course material, irrelevant)
        if source and source.lower() == "crossref":
            results.append((i, None, "crossref — needs LLM relevance check"))
            continue
        # GitHub: keep as repo, not paper — will be extracted by dataset_repo_extractor
        if source and source.lower() == "github":
            results.append((i, True, "github source (repo)"))
            continue
        # Title too short (but allow github owner/repo format)
        if len(title) < 10 and source != "github":
            results.append((i, False, "title too short (<10 chars)"))
            continue
        if len(title) < 3:
            results.append((i, False, "title too short (<3 chars)"))
            continue

        # Gray area — needs LLM judgement
        results.append((i, None, "needs LLM judgement"))

    return results


def quality_filter_node(state: ResearchState) -> dict[str, Any]:
    """Filter paper_candidates for real academic papers.

    Strategy: deterministic pre-filter first (trusted URL → keep, non-paper
    pattern → drop), LLM only for gray-area candidates. This prevents the LLM
    from misclassifying arxiv papers as GitHub repos (Re1.3 audit issue #1).
    """
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
            "trace_events": [trace],
        }

    # Step 1: deterministic pre-filter
    pre_results = _pre_filter(candidates)
    gray_indices = [i for i, verdict, _ in pre_results if verdict is None]
    n_pre_keep = sum(1 for _, v, _ in pre_results if v is True)
    n_pre_drop = sum(1 for _, v, _ in pre_results if v is False)
    trace["tool_calls"].append({
        "tool": "quality_filter.pre_filter",
        "pre_keep": n_pre_keep,
        "pre_drop": n_pre_drop,
        "gray_area": len(gray_indices),
    })

    # Step 2: LLM only for gray-area candidates
    is_paper_map: dict[int, bool] = {}
    reason_map: dict[int, str] = {}

    for i, verdict, reason in pre_results:
        if verdict is not None:
            is_paper_map[i] = verdict
            reason_map[i] = reason

    if gray_indices:
        gray_candidates = [candidates[i] for i in gray_indices]
        batches = [gray_candidates[j:j + _BATCH_SIZE]
                   for j in range(0, len(gray_candidates), _BATCH_SIZE)]
        llm_failed = False

        for batch_idx, batch in enumerate(batches):
            result = _call_llm_batch(batch)
            if result is None:
                llm_failed = True
                break
            for item in result:
                idx_in_batch = item.get("index")
                if isinstance(idx_in_batch, int) and 0 <= idx_in_batch < len(batch):
                    global_idx = gray_indices[batch_idx * _BATCH_SIZE + idx_in_batch]
                    is_paper_map[global_idx] = bool(item.get("is_paper", True))
                    reason_map[global_idx] = item.get("reason", "LLM judged")
            trace["tool_calls"].append({"tool": "re13_quality_filter.llm", "batch_size": len(batch)})

        if llm_failed:
            logger.warning("quality_filter LLM failed for gray-area — using heuristic fallback")
            trace["tool_calls"].append({"tool": "quality_filter.heuristic_fallback"})
            for idx, is_paper, reason in _heuristic_filter(gray_candidates):
                global_idx = gray_indices[idx]
                is_paper_map[global_idx] = is_paper
                reason_map[global_idx] = reason
    else:
        trace["tool_calls"].append({"tool": "quality_filter.no_llm_needed", "reason": "all candidates resolved by pre-filter"})

    # Apply filter
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for i, c in enumerate(candidates):
        if is_paper_map.get(i, True):
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
    trace["output_summary"] = {
        "kept": len(kept),
        "dropped": len(dropped),
        "pre_filter_keep": n_pre_keep,
        "pre_filter_drop": n_pre_drop,
        "llm_judged": len(gray_indices),
    }

    filter_results = {
        "total": len(candidates),
        "kept": len(kept),
        "dropped": len(dropped),
        "dropped_items": dropped,
    }

    return {
        "paper_candidates": kept,
        "filter_results": filter_results,
        "trace_events": [trace],
    }

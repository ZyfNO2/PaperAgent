"""LangGraph node: citation_expander — auto seed selection + citation network expansion.

Selects top-N verified papers by relevance score as seeds, calls Semantic
Scholar API for references+citations concurrently, identifies surveys/repos.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState

logger = logging.getLogger(__name__)

_S2_CONCURRENCY = 3
_S2_TIMEOUT = 10
_SEED_TOP_N = 5
_REFS_PER_SEED = 15
_CITS_PER_SEED = 15
_MAX_EXPANDED = 150


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _select_seeds(verified_papers: list[dict[str, Any]], topic_atoms: dict[str, Any],
                  top_n: int = _SEED_TOP_N) -> list[dict[str, Any]]:
    """Select top-N verified papers by relevance score as seeds.

    Scoring:
      base = len(hit_keywords ∩ topic_keywords) × 2
      relation baseline/parallel → +3
      has paperId/DOI/arXiv ID → +2 (required, else skip)
      citation_count > 10 → +1
    """
    topic_kw: set[str] = set()
    for v in (topic_atoms.get("method") or []) + (topic_atoms.get("object") or []) + (topic_atoms.get("task") or []):
        topic_kw.add(str(v).lower())

    scored: list[tuple[int, dict[str, Any]]] = []
    for p in verified_papers:
        hit_kw = set(k.lower() for k in (p.get("hit_keywords") or []))
        score = len(hit_kw & topic_kw) * 2
        if p.get("relation_to_topic") in ("baseline", "parallel"):
            score += 3
        has_id = bool(p.get("paper_id") or p.get("doi") or p.get("arxiv_id"))
        if not has_id:
            continue  # cannot query citations without an identifier
        score += 2
        cc = p.get("citation_count") or 0
        if cc > 10:
            score += 1
        scored.append((score, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    seeds = []
    for score, p in scored[:top_n]:
        seed = dict(p)
        seed["seed_selection_reason"] = f"relevance_score={score}"
        seed["relevance_score"] = score
        seeds.append(seed)
    return seeds


async def _expand_one_seed(seed: dict[str, Any], sem: asyncio.Semaphore) -> list[dict[str, Any]]:
    """Fetch references + citations for one seed concurrently."""
    from apps.api.app.services.retrieval.adapters.semantic_scholar_search import (
        semantic_scholar_citations,
        semantic_scholar_references,
    )

    async with sem:
        try:
            refs, cits = await asyncio.gather(
                semantic_scholar_references(
                    paper_id=seed.get("paper_id"),
                    doi=seed.get("doi"),
                    arxiv_id=seed.get("arxiv_id"),
                    top_k=_REFS_PER_SEED,
                ),
                semantic_scholar_citations(
                    paper_id=seed.get("paper_id"),
                    doi=seed.get("doi"),
                    arxiv_id=seed.get("arxiv_id"),
                    top_k=_CITS_PER_SEED,
                ),
            )
        except Exception as exc:
            logger.warning("citation_expander S2 API failed for seed %r: %s",
                           seed.get("title", "??"), type(exc).__name__)
            return []

    expanded: list[dict[str, Any]] = []
    seed_title = (seed.get("title") or "").strip()
    for p in refs + cits:
        p["expanded_from_seed"] = seed_title
        expanded.append(p)
    return expanded


def _dedup(papers: list[dict[str, Any]], existing_titles: set[str]) -> list[dict[str, Any]]:
    """Deduplicate expanded papers by paperId, DOI, then normalized title."""
    seen_pids: set[str] = set()
    seen_dois: set[str] = set()
    seen_titles: set[str] = set()
    out: list[dict[str, Any]] = []

    for p in papers:
        pid = p.get("paper_id")
        doi = p.get("doi")
        title = _normalize_title(p.get("title") or "")

        if pid and pid in seen_pids:
            continue
        if doi and doi in seen_dois:
            continue
        if title and title in seen_titles:
            continue
        if title and title in existing_titles:
            continue

        if pid:
            seen_pids.add(pid)
        if doi:
            seen_dois.add(doi)
        if title:
            seen_titles.add(title)
        out.append(p)

    return out


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def _identify_surveys(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify survey papers using heuristic (title-based) identification."""
    survey_patterns = re.compile(
        r"(?i)(survey|review|tutorial|systematic|benchmark|comprehensive\s+overview|literature\s+review)"
    )
    surveys: list[dict[str, Any]] = []
    for p in papers:
        title = p.get("title") or ""
        if survey_patterns.search(title):
            surveys.append({
                "title": title,
                "paper_id": p.get("paper_id"),
                "doi": p.get("doi"),
                "url": p.get("url"),
                "year": p.get("year"),
                "reason": "title matches survey pattern",
            })
    return surveys


def _extract_repos(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract GitHub repo URLs from paper metadata."""
    repo_patterns = re.compile(
        r"(https?://github\.com/[\w\-]+/[\w\-]+)",
        re.IGNORECASE,
    )
    repos: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in papers:
        for field in ("abstract", "url", "venue"):
            text = p.get(field) or ""
            if not text:
                continue
            for match in repo_patterns.finditer(str(text)):
                url = match.group(1).rstrip(").,;")
                if url not in seen:
                    seen.add(url)
                    repos.append({
                        "url": url,
                        "from_paper": (p.get("title") or "")[:100],
                    })
    return repos


def citation_expander_node(state: ResearchState) -> dict[str, Any]:
    """Auto-select seeds from verified_papers, expand via S2 citations/references."""
    t0 = time.time()

    verified = list(state.get("verified_papers") or [])
    topic_atoms = state.get("topic_atoms") or {}

    trace: dict[str, Any] = {
        "node": "citation_expander",
        "started_at": _now_iso(),
        "input_summary": {"n_verified": len(verified)},
        "output_summary": {},
        "tool_calls": [],
        "errors": [],
        "provider": "semantic_scholar",
    }

    # Select seeds
    seeds = _select_seeds(verified, topic_atoms)
    trace["input_summary"]["n_seeds"] = len(seeds)
    trace["input_summary"]["seed_titles"] = [s.get("title", "")[:60] for s in seeds]

    if not seeds:
        logger.info("citation_expander: no seeds with identifiers found, skipping expansion")
        trace["ended_at"] = _now_iso()
        trace["elapsed_s"] = round(time.time() - t0, 3)
        trace["output_summary"] = {"n_expanded": 0, "reason": "no_seeds_with_ids"}
        return {
            "seed_papers": [],
            "expanded_papers": [],
            "surveys_found": [],
            "repos_found": [],
            "citation_expansion_done": True,
            "trace_events": [trace],
        }

    # Run async expansion
    existing_titles = {_normalize_title(p.get("title") or "") for p in verified}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        sem = asyncio.Semaphore(_S2_CONCURRENCY)
        try:
            results = loop.run_until_complete(
                asyncio.gather(*[_expand_one_seed(s, sem) for s in seeds])
            )
        finally:
            loop.close()

        # Flatten and dedup
        all_expanded: list[dict[str, Any]] = []
        for batch in results:
            all_expanded.extend(batch)

        expanded = _dedup(all_expanded, existing_titles)
        expanded = expanded[:_MAX_EXPANDED]

        # Identify surveys and repos
        surveys = _identify_surveys(expanded)
        repos = _extract_repos(expanded)

        trace["tool_calls"].append({
            "tool": "semantic_scholar.citations+references",
            "n_seeds": len(seeds),
            "n_expanded": len(expanded),
            "concurrent": True,
        })
        trace["output_summary"] = {
            "n_expanded": len(expanded),
            "n_surveys": len(surveys),
            "n_repos": len(repos),
        }

        # Per-seed expansion counts for trace
        trace["per_seed"] = []
        for seed, batch in zip(seeds, results):
            trace["per_seed"].append({
                "seed_title": (seed.get("title") or "")[:60],
                "n_references_plus_citations": len(batch),
                "relevance_score": seed.get("relevance_score", 0),
            })

    except Exception as exc:
        logger.exception("citation_expander failed: %s", exc)
        trace["errors"].append({
            "phase": "s2_api",
            "error": type(exc).__name__,
            "action": "return_empty_expansion",
        })
        trace["output_summary"] = {"n_expanded": 0, "error": type(exc).__name__}
        expanded = []
        surveys = []
        repos = []

    trace["ended_at"] = _now_iso()
    trace["elapsed_s"] = round(time.time() - t0, 3)

    # Build new paper_candidates: verified + expanded for second-round verify
    new_candidates = list(verified) + list(expanded)

    return {
        "seed_papers": seeds,
        "expanded_papers": expanded,
        "surveys_found": surveys,
        "repos_found": repos,
        "citation_expansion_done": True,
        "paper_candidates": new_candidates,
        "trace_events": [trace],
    }

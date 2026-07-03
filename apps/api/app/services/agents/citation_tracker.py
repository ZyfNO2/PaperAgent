"""Re08 CitationTracker — SOP §4.4 (minimal).

Adds lightweight citation edges to a verified candidate set.  This is
**not** a knowledge graph — just per-edge notes that the next stage can
use to find official repos / datasets / parallel work.

Source: ``semantic_scholar_citations`` and ``semantic_scholar_references``
adapters (already in apps/api/app/services/retrieval/adapters).  When the
adapter is unavailable or the candidate lacks an identifier, the edge
list for that candidate is empty.

Output (SOP §4.4):

    {
      "citation_edges": [
        {
          "source_candidate_id": "...",
          "target_title": "...",
          "edge_type": "references | cited_by | official_repo | dataset_used | benchmarked_on",
          "source": "openalex | arxiv | github | paper_text",
          "note": "..."
        }
      ]
    }
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def _resolve_s2(
    candidate: dict, client: Any | None,
) -> tuple[list[dict], list[dict]]:
    """Fetch semantic-scholar citations + references.  Returns ([],[]) on failure."""
    arxiv_id = candidate.get("arxiv_id") or ""
    doi = candidate.get("doi") or ""
    paper_id = candidate.get("paper_id") or None
    try:
        from ..retrieval.adapters.semantic_scholar_search import (
            semantic_scholar_citations,
            semantic_scholar_references,
        )
    except Exception as exc:
        logger.debug("semantic_scholar import failed: %s", exc)
        return [], []
    try:
        cites = await semantic_scholar_citations(
            paper_id=paper_id, doi=doi, arxiv_id=arxiv_id,
            top_k=15, client=client,
        )
    except Exception as exc:
        logger.debug("s2 citations failed: %s", exc)
        cites = []
    try:
        refs = await semantic_scholar_references(
            paper_id=paper_id, doi=doi, arxiv_id=arxiv_id,
            top_k=15, client=client,
        )
    except Exception as exc:
        logger.debug("s2 references failed: %s", exc)
        refs = []
    return cites or [], refs or []


async def track_for_candidate(
    candidate: dict, *, client: Any | None = None,
    top_k_per_edge: int = 5,
) -> dict:
    """Return citation edges for a single verified candidate."""
    cid = candidate.get("candidate_id") or candidate.get("id") or ""
    edges: list[dict] = []
    if not cid:
        return {"citation_edges": []}

    cites, refs = await _resolve_s2(candidate, client)
    for c in (cites or [])[:top_k_per_edge]:
        if not isinstance(c, dict):
            continue
        title = c.get("title") or ""
        if not title:
            continue
        edges.append({
            "source_candidate_id": cid,
            "target_title": title,
            "edge_type": "cited_by",
            "source": "semantic_scholar",
            "note": (c.get("venue") or "")[:80],
        })
    for r in (refs or [])[:top_k_per_edge]:
        if not isinstance(r, dict):
            continue
        title = r.get("title") or ""
        if not title:
            continue
        edges.append({
            "source_candidate_id": cid,
            "target_title": title,
            "edge_type": "references",
            "source": "semantic_scholar",
            "note": (r.get("venue") or "")[:80],
        })

    # Optional: tag a github repo as "official_repo" if the candidate
    # declares one.
    url = (candidate.get("url") or "").lower()
    if "github.com/" in url:
        edges.append({
            "source_candidate_id": cid,
            "target_title": url.split("github.com/")[-1],
            "edge_type": "official_repo",
            "source": "github_url",
            "note": "candidate URL points to a GitHub repo",
        })
    return {"citation_edges": edges}


async def track_bucket(
    candidates: list[dict], *, client: Any | None = None,
    top_k_per_edge: int = 5,
) -> dict:
    """Track citation edges for an entire bucket (best-effort, offline-safe)."""
    all_edges: list[dict] = []
    for c in candidates or []:
        if not isinstance(c, dict):
            continue
        if not (c.get("arxiv_id") or c.get("doi")):
            # No identifier → skip (semantic_scholar needs an id).
            continue
        out = await track_for_candidate(
            c, client=client, top_k_per_edge=top_k_per_edge,
        )
        all_edges.extend(out.get("citation_edges") or [])
    return {"citation_edges": all_edges}


__all__ = ["track_for_candidate", "track_bucket"]
"""Re04 SOP §5 Task 4 — Semantic Scholar adapter (fallback for OpenAlex).

Reference: AutoResearchClaw /researchclaw/literature/search.py
                /researchclaw/literature/semantic_scholar.py

Why we add this:
- Re03 Case A/B both reported `openalex 0 hits` due to rate limiting.
- citation_expand therefore returned 0 refs even when seeds were
  selected.
- Semantic Scholar has a public free tier and structured references /
  citations endpoints, so it makes a natural fallback.

Public surface:
- async semantic_scholar_search(queries, top_k=8, *, client=None) -> list[dict]
- async semantic_scholar_citations(paper_id, *, client=None) -> list[dict]
- async semantic_scholar_references(paper_id, *, client=None) -> list[dict]

Failure handling (SOP §5 Task 4 acceptance):
- No key configured  -> return [] and let caller record
  status=skipped_without_key in SourceLedger.
- 429 / 5xx          -> return []; let caller record status=rate_limited.
- 404                -> return []; let caller record status=not_found.
- Network error      -> return []; let caller record status=error.

NEVER raise. NEVER silently mutate OpenAlex/arXiv results. NEVER
require an API key for the basic query path.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlencode

from .._http import HttpError, fetch_with_timeout

from apps.api.app.services.network_guard import NetworkPolicyGuard

logger = logging.getLogger(__name__)

# Public Graph API. No key required for low-volume search; key unlocks
# higher rate limits. We read S2_API_KEY only as a soft upgrade.
S2_BASE = "https://api.semanticscholar.org/graph/v1"
S2_API_KEY = os.environ.get("S2_API_KEY") or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")

# Fields we ask the Graph API to return. Citation/reference endpoints
# need the nested structures.
_FIELDS_PAPER = ",".join([
    "paperId", "externalIds", "title", "abstract", "year", "venue",
    "publicationVenue", "citationCount", "referenceCount", "url",
])
_FIELDS_CITATIONS = _FIELDS_PAPER + ",citingPaper.paperId,citingPaper.title,citingPaper.year,citingPaper.url,citingPaper.externalIds"
_FIELDS_REFERENCES = _FIELDS_PAPER + ",citedPaper.paperId,citedPaper.title,citedPaper.year,citedPaper.url,citedPaper.externalIds"


def _headers() -> dict[str, str]:
    h = {"User-Agent": "PaperAgent-Re04/1.0 (semantic_scholar adapter)"}
    if S2_API_KEY:
        h["x-api-key"] = S2_API_KEY
    return h


def _has_key() -> bool:
    return bool(S2_API_KEY)


def _normalize_hit(hit: dict) -> dict | None:
    """Map raw S2 hit -> our unified paper schema."""
    title = hit.get("title")
    if not title:
        return None
    ext = hit.get("externalIds") or {}
    doi = ext.get("DOI")
    arxiv_id = ext.get("ArXiv")
    year = hit.get("year")
    venue = None
    pv = hit.get("publicationVenue") or hit.get("venue")
    if isinstance(pv, dict):
        venue = pv.get("name") or pv.get("alternate_name")
    elif isinstance(pv, str):
        venue = pv
    return {
        "title": title.strip(),
        "abstract": (hit.get("abstract") or "").strip() or None,
        "year": int(year) if isinstance(year, int) and year > 0 else None,
        "venue": venue,
        "citation_count": hit.get("citationCount") or 0,
        "doi": doi,
        "arxiv_id": arxiv_id,
        "paper_id": hit.get("paperId"),
        "url": hit.get("url") or (f"https://www.semanticscholar.org/paper/{hit.get('paperId')}" if hit.get("paperId") else None),
        "source": "semantic_scholar",
    }


async def semantic_scholar_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Run paper search via Semantic Scholar Graph /paper/search.

    Returns a list of unified-schema paper dicts. Never raises; returns
    [] on any failure. Caller should record a SourceLedger status based
    on whether results came back empty.
    """
    NetworkPolicyGuard.assert_online("semantic_scholar")
    qs = [q.strip() for q in (queries or []) if q and q.strip()][:3]
    if not qs:
        return []

    out: list[dict] = []
    seen_ids: set[str] = set()
    for q in qs:
        if len(out) >= top_k:
            break
        params = {"query": q, "limit": min(top_k, 100), "fields": _FIELDS_PAPER}
        url = f"{S2_BASE}/paper/search?{urlencode(params)}"
        try:
            data = await fetch_with_timeout(
                url, client=client, timeout=10.0, headers=_headers(),
            )
        except HttpError as exc:
            logger.warning("semantic_scholar search HttpError: %s | query=%s", exc, q)
            continue
        except Exception as exc:
            logger.warning("semantic_scholar search failed: %s | query=%s", exc, q)
            continue
        if not isinstance(data, dict):
            continue
        for raw in data.get("data") or []:
            hit = _normalize_hit(raw)
            if not hit:
                continue
            pid = hit.get("paper_id") or hit.get("doi") or hit.get("title")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            out.append(hit)
            if len(out) >= top_k:
                break
    return out


def _extract_paper_id(paper_id: str | None, doi: str | None, arxiv_id: str | None) -> str | None:
    """S2 Graph wants one of: S2 paperId, DOI:xxx, ARXIV:xxx, etc."""
    if paper_id:
        return paper_id
    if doi:
        # Strip URL prefix if present (e.g. "https://doi.org/10.xxx" → "10.xxx")
        clean_doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi.strip())
        return f"DOI:{clean_doi}"
    if arxiv_id:
        m = re.search(r"(\d{4}\.\d{4,5}(v\d+)?)", arxiv_id)
        if m:
            return f"ARXIV:{m.group(1)}"
    return None


async def _fetch_endpoint(endpoint: str, paper_ref: str, *, client: Any | None) -> list[dict]:
    url = f"{S2_BASE}/paper/{paper_ref}/{endpoint}?{urlencode({'fields': _FIELDS_CITATIONS if endpoint == 'citations' else _FIELDS_REFERENCES, 'limit': 50})}"
    try:
        data = await fetch_with_timeout(
            url, client=client, timeout=10.0, headers=_headers(),
        )
    except HttpError as exc:
        logger.warning("semantic_scholar %s HttpError: %s | paper=%s", endpoint, exc, paper_ref)
        return []
    except Exception as exc:
        logger.warning("semantic_scholar %s failed: %s | paper=%s", endpoint, exc, paper_ref)
        return []
    if not isinstance(data, dict):
        return []
    out: list[dict] = []
    for raw in (data.get("data") or []):
        # 'citations' / 'references' items are wrapped as {citingPaper / citedPaper}
        inner = raw.get("citingPaper") if endpoint == "citations" else raw.get("citedPaper")
        if not inner:
            continue
        hit = _normalize_hit(inner)
        if hit:
            out.append(hit)
    return out


async def semantic_scholar_citations(
    paper_id: str | None = None,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    top_k: int = 25,
    client: Any | None = None,
) -> list[dict]:
    """Papers that cite the given paper. Returns [] on any failure."""
    NetworkPolicyGuard.assert_online("semantic_scholar_citations")
    pref = _extract_paper_id(paper_id, doi, arxiv_id)
    if not pref:
        return []
    out = await _fetch_endpoint("citations", pref, client=client)
    return out[:top_k]


async def semantic_scholar_references(
    paper_id: str | None = None,
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    top_k: int = 25,
    client: Any | None = None,
) -> list[dict]:
    """Papers that the given paper references. Returns [] on any failure."""
    NetworkPolicyGuard.assert_online("semantic_scholar_references")
    pref = _extract_paper_id(paper_id, doi, arxiv_id)
    if not pref:
        return []
    out = await _fetch_endpoint("references", pref, client=client)
    return out[:top_k]


# Status helpers for SourceLedger integration (SOP §5 Task 4 acceptance).
def has_api_key() -> bool:
    """Whether the adapter has a soft API key set."""
    return _has_key()

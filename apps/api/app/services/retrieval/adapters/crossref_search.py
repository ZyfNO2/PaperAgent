"""Crossref paper search adapter.

Crossref is a free, no-key, no-rate-limit scholarly metadata API backed by
publishers.  When OpenAlex is in its paid-budget state, this is the primary
fallback for paper search.  Returns Crossref native dicts; normalizer
maps the common fields to ``RetrievalCandidate``.

Hard rules:
  - No shell execution.
  - Use a descriptive User-Agent (Crossref asks publishers to identify
    themselves; we identify as PaperAgent and include a contact mailto so
    the request lands in the polite pool if one is set up later).
  - Use ``select`` to keep payload small.
"""

from __future__ import annotations

from typing import Any

from .._http import HttpError, fetch_with_timeout
from . import _cache


CROSSREF_API = "https://api.crossref.org/works"


def _author_names(authors: list[dict]) -> list[str]:
    out: list[str] = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        given = (a.get("given") or "").strip()
        family = (a.get("family") or "").strip()
        name = (f"{given} {family}").strip() or a.get("name")
        if name:
            out.append(name)
    return out


async def crossref_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
    mailto: str | None = None,
) -> list[dict]:
    """Search Crossref for academic papers. Returns OpenAlex-shaped dicts."""

    headers = {
        "User-Agent": "PaperAgent/1.0 (mailto:[email protected])",
        "Accept": "application/json",
    }
    results: list[dict] = []

    qs = [q for q in (queries or []) if q and q.strip()][:3]
    for q in qs:
        # Re05 §5.3: cache hit short-circuits the network call.
        cached = _cache.get("crossref", q)
        if cached is not None:
            results.extend(cached[:top_k])
            continue
        params = [
            f"query={q}",
            f"rows={top_k}",
            "select=DOI,title,author,issued,published-print,container-title,abstract,link,URL,type,is-referenced-by-count",
        ]
        if mailto:
            params.append(f"mailto={mailto}")
        url = f"{CROSSREF_API}?{'&'.join(params)}"
        try:
            data = await fetch_with_timeout(url, headers=headers, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, dict):
            continue
        msg = data.get("message") or {}
        q_results: list[dict] = []
        for item in msg.get("items") or []:
            if not isinstance(item, dict):
                continue
            # Flatten title (Crossref returns a list)
            raw_titles = item.get("title") or []
            if isinstance(raw_titles, list) and raw_titles:
                title_str = str(raw_titles[0])
            else:
                title_str = str(raw_titles) if raw_titles else ""
            # Year from issued / published-print
            year: int | None = None
            issued = item.get("issued") or item.get("published-print") or {}
            parts = issued.get("date-parts") if isinstance(issued, dict) else None
            if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
                y = parts[0][0]
                if isinstance(y, int):
                    year = y
                elif isinstance(y, str) and y.isdigit():
                    year = int(y)
            # URL: prefer resource.primary.URL
            url_: str | None = None
            res = item.get("resource") or {}
            primary = res.get("primary") if isinstance(res, dict) else None
            if isinstance(primary, dict):
                url_ = primary.get("URL")
            if not url_:
                url_ = item.get("URL")
            # Container title (venue)
            venue: str | None = None
            container = item.get("container-title") or []
            if isinstance(container, list) and container:
                venue = str(container[0])
            q_results.append({
                "title": title_str,
                "doi": item.get("DOI"),
                "DOI": item.get("DOI"),
                "authors": _author_names(item.get("author") or []),
                "author": item.get("author") or [],
                "venue": venue,
                "container-title": container,
                "abstract": item.get("abstract"),
                "url": url_,
                "URL": url_,
                "year": year,
                "publication_year": year,
                "citation_count": item.get("is-referenced-by-count"),
                "_crossref_type": item.get("type"),
            })
        # Cache successful (non-empty) per-query results.
        _cache.put("crossref", q, q_results)
        results.extend(q_results)
    return results[:top_k]

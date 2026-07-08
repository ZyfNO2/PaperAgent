"""DataCite DOI search adapter — searches datasets registered with DataCite.

Public API, no key required. Returns dataset records with DOI metadata.
429/5xx return [] and never raise.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DATACITE_API = "https://api.datacite.org/dois"


async def datacite_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Search DataCite for datasets. No API key required.

    Returns normalized dicts with title/abstract/year/doi/source='datacite'
    /evidence_type='dataset'. 429/5xx -> return [] (don't raise).
    """
    qs = [q for q in (queries or []) if q and q.strip()][:1]
    if not qs:
        return []
    q = qs[0]

    try:
        import httpx

        params = {
            "query": q,
            "page[size]": min(top_k, 10),
            "page[number]": 1,
        }
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
            resp = await c.get(DATACITE_API, params=params, headers=headers)

        if resp.status_code >= 400:
            logger.info("datacite http %s | q=%s", resp.status_code, q)
            return []

        data = resp.json()
        results: list[dict[str, Any]] = []
        for item in (data.get("data") or [])[:top_k]:
            attrs = item.get("attributes") or {}
            titles = attrs.get("titles") or []
            title = titles[0].get("title", "") if titles else ""
            if not title:
                continue
            descriptions = attrs.get("descriptions") or []
            abstract = descriptions[0].get("description", "") if descriptions else ""
            year_raw = attrs.get("publicationYear")
            doi = attrs.get("doi", "")
            url = attrs.get("url") or (f"https://doi.org/{doi}" if doi else "")
            results.append({
                "title": str(title),
                "abstract": str(abstract)[:500] if abstract else "",
                "year": int(year_raw) if year_raw else None,
                "doi": doi,
                "url": url,
                "source": "datacite",
                "evidence_type": "dataset",
                "source_query": q,
            })
        return results
    except Exception as exc:  # noqa: BLE001
        logger.info("datacite fetch error: %s | q=%s", exc, q)
        return []

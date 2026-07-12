"""CORE.ac.uk v3 paper search adapter (Re05 SOP §5.1).

Public endpoint, no key needed.  When the public endpoint rejects with
401/403, retry once with a smaller ``limit=3`` (graceful degradation).
429/5xx return ``[]`` and never raise.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.api.app.services.network_guard import NetworkPolicyGuard

logger = logging.getLogger(__name__)


CORE_API = "https://api.core.ac.uk/v3/search/works"


async def core_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """CORE.ac.uk v3 search. No key required.

    Returns normalized dicts with title/abstract/year/doi/source='core'
    /evidence_type='paper'.  401/403 → retry with limit=3.  429/5xx
    → return ``[]`` (don't raise).
    """
    NetworkPolicyGuard.assert_online("core")
    qs = [q for q in (queries or []) if q and q.strip()][:1]
    if not qs:
        return []
    q = qs[0]

    out = await _fetch_core(q, top_k, client=client)
    if out.get("status") == "ok":
        return out["results"]

    # 401/403 retry with smaller top_k=3 (key-required endpoint fallback).
    if out.get("status") in (401, 403):
        retry = await _fetch_core(q, 3, client=client)
        if retry.get("status") == "ok":
            return retry["results"]
        # Still failed (probably 429/5xx on retry) → return [].

    # 429/5xx or empty body → graceful return.
    return []


async def _fetch_core(query: str, limit: int, *, client: Any | None = None) -> dict:
    """One CORE fetch attempt. Returns dict with keys:
        status: 'ok' | <int http_status> | 'error'
        results: list[dict]
    """
    from urllib.parse import urlencode

    url = f"{CORE_API}?{urlencode({'q': query, 'limit': limit})}"
    headers = {
        "User-Agent": "PaperAgent/1.0 (mailto:[email protected])",
        "Accept": "application/json",
    }
    timeout = 8.0

    try:
        if client is not None:
            try:
                status, body = await client.request("GET", url, headers=headers)
            except Exception as exc:  # noqa: BLE001
                logger.info("core mock client error: %s | q=%s", exc, query)
                return {"status": "error", "results": []}
            if status >= 400:
                logger.info("core http %s | q=%s", status, query)
                return {"status": int(status), "results": []}
            return _parse_core_body(body, query=query)

        import httpx  # type: ignore

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
            resp = await c.get(url, headers=headers)
        if resp.status_code >= 400:
            logger.info("core http %s | q=%s", resp.status_code, query)
            return {"status": int(resp.status_code), "results": []}
        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.info("core json parse failed: %s | q=%s", exc, query)
            return {"status": "error", "results": []}
        return _parse_core_body(data, query=query)
    except Exception as exc:  # noqa: BLE001  (network/timeout)
        logger.info("core fetch error: %s | q=%s", exc, query)
        return {"status": "error", "results": []}


def _parse_core_body(body: Any, *, query: str) -> dict:
    """Normalize CORE v3 response into list[dict] with unified schema."""
    results: list[dict] = []
    if isinstance(body, dict):
        items = body.get("results") or body.get("hits") or []
    elif isinstance(body, list):
        items = body
    else:
        items = []
    for r in items:
        if not isinstance(r, dict):
            continue
        title = r.get("title") or ""
        if not title:
            continue
        # yearPublished may be string year or null
        year_raw = r.get("yearPublished") or r.get("year") or r.get("publishedDate")
        year: int | None = None
        if isinstance(year_raw, int):
            year = year_raw
        elif isinstance(year_raw, str) and year_raw[:4].isdigit():
            year = int(year_raw[:4])
        abstract = r.get("abstract") or ""
        if abstract and not isinstance(abstract, str):
            abstract = str(abstract)
        doi = r.get("doi")
        url = r.get("url") or r.get("downloadUrl") or (
            f"https://doi.org/{doi}" if doi else None
        )
        results.append({
            "title": str(title),
            "abstract": abstract or "",
            "year": year,
            "doi": doi,
            "url": url,
            "source": "core",
            "evidence_type": "paper",
            "source_query": query,
        })
    return {"status": "ok", "results": results}
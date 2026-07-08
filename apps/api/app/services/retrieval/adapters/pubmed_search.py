"""PubMed E-utilities search adapter.

Free, no API key required (3 req/s without key, 10 req/s with key).
429/5xx → return [] (don't raise).

NOTE: PubMed only indexes medical/life science papers. For non-medical topics
(robotics, civil engineering, etc.) it will return 0 results. This adapter
should only be called for medical/biological/chemical topics — see
search_agent's domain-gated tool selection.
"""
from __future__ import annotations

import logging
from typing import Any

from .._http import HttpError, fetch_with_timeout

logger = logging.getLogger(__name__)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


async def pubmed_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict[str, Any]]:
    """Search PubMed for medical/life science papers.

    Two-step: esearch (get PMIDs) → esummary (get metadata).
    No API key required. 429/5xx → return [].
    """
    qs = [q for q in (queries or []) if q and q.strip()][:2]
    if not qs:
        return []

    all_results: list[dict[str, Any]] = []

    for q in qs:
        try:
            # Step 1: esearch → get PMIDs
            esearch_params = {
                "db": "pubmed",
                "term": q,
                "retmax": str(min(top_k, 10)),
                "retmode": "json",
            }
            try:
                data = await fetch_with_timeout(
                    PUBMED_ESEARCH, params=esearch_params, timeout=10.0,
                )
            except HttpError as exc:
                logger.info("pubmed esearch http %s | q=%s", exc, q[:50])
                continue

            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                continue

            # Step 2: esummary → get paper metadata
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            try:
                sdata = await fetch_with_timeout(
                    PUBMED_ESUMMARY, params=summary_params, timeout=10.0,
                )
            except HttpError as exc:
                logger.info("pubmed esummary http %s | q=%s", exc, q[:50])
                continue

            result = sdata.get("result", {})

            for pmid in id_list:
                item = result.get(pmid, {})
                if not item:
                    continue
                title = item.get("title", "")
                if not title:
                    continue

                authors = [
                    a.get("name", "")
                    for a in item.get("authors", [])
                    if a.get("name")
                ]

                doi = ""
                for aid in item.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                        break

                pubdate = item.get("pubdate", "")
                year = None
                for part in pubdate.split():
                    if part.isdigit() and 1900 < int(part) < 2100:
                        year = int(part)
                        break

                all_results.append({
                    "title": str(title),
                    "abstract": "",
                    "authors": authors[:5],
                    "year": year,
                    "doi": doi,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "pmid": pmid,
                    "source": "pubmed",
                    "evidence_type": "paper",
                    "source_query": q,
                })

        except Exception as exc:
            logger.info("pubmed fetch error: %s | q=%s", type(exc).__name__, q[:50])
            continue

    return all_results[:top_k]

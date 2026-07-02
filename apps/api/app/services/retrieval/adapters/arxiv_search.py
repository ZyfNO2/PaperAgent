"""arXiv Atom 检索 (SOP §8.3)."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from .._http import HttpError, fetch_with_timeout
from . import _cache

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def _strip_ns(tag: str) -> str:
    if tag.startswith(_ATOM_NS):
        return tag[len(_ATOM_NS):]
    if tag.startswith(_ARXIV_NS):
        return tag[len(_ARXIV_NS):]
    return tag


def _text(node: ET.Element | None) -> str | None:
    if node is None:
        return None
    txt = "".join(node.itertext()).strip()
    return txt or None


def _parse_entry(entry: ET.Element) -> dict | None:
    title = _text(entry.find(f"{_ATOM_NS}title"))
    if not title:
        return None
    summary = _text(entry.find(f"{_ATOM_NS}summary"))
    author_nodes = entry.findall(f"{_ATOM_NS}author")
    authors: list[str] = []
    for a in author_nodes:
        n = _text(a.find(f"{_ATOM_NS}name"))
        if n:
            authors.append(n)
    id_text = _text(entry.find(f"{_ATOM_NS}id")) or ""
    arxiv_id: str | None = None
    m = re.search(r"arxiv\.org/abs/([\w.\-]+)", id_text)
    if m:
        arxiv_id = m.group(1)
    published = _text(entry.find(f"{_ATOM_NS}published"))
    year: int | None = None
    if published and len(published) >= 4 and published[:4].isdigit():
        year = int(published[:4])
    return {
        "title": title,
        "abstract": summary,
        "authors": authors,
        "arxiv_id": arxiv_id,
        "url": id_text or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None),
        "published": published,
        "year": year,
    }


def _parse_arxiv_xml(xml_text: str, source_query: str) -> list[dict]:
    """Parse arXiv Atom XML, tag entries with source_query."""
    papers: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("arxiv xml parse failed: %s", exc)
        return papers
    for entry in root.findall(f"{_ATOM_NS}entry"):
        d = _parse_entry(entry)
        if d:
            d["source_query"] = source_query
            papers.append(d)
    return papers


async def arxiv_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """从 arXiv 检索 paper 原始 dict 列表.

    Runs up to 3 queries with URL encoding + relevance sort, dedupes by arxiv_id.
    """
    qs = [q.strip() for q in (queries or []) if q and q.strip()][:3]
    if not qs:
        return []

    # Per-query cap so 3 queries * max_per_query <= top_k comfortably
    max_per_query = max(1, top_k)
    max_total = top_k

    papers: list[dict] = []
    seen_ids: set[str] = set()

    for q in qs:
        if len(papers) >= max_total:
            break
        # Re05 §5.3: cache hit short-circuits the network call.
        cached = _cache.get("arxiv", q)
        if cached is not None:
            for p in cached:
                pid = p.get("arxiv_id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    papers.append(p)
                    if len(papers) >= max_total:
                        break
            continue
        params = {
            "search_query": f"all:{q}",
            "start": 0,
            "max_results": max_per_query,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = f"{ARXIV_API}?{urlencode(params)}"
        try:
            data = await fetch_with_timeout(url, client=client, timeout=10.0)
        except HttpError as exc:
            logger.warning("arxiv fetch failed (HttpError): %s | query=%s", exc, q)
            continue
        except Exception as exc:  # ponytail: catch unexpected so one bad query doesn't kill the loop
            logger.warning("arxiv query failed: %s | query=%s", exc, q)
            continue
        if not isinstance(data, str):
            continue
        parsed = _parse_arxiv_xml(data, source_query=q)
        # Cache successful (non-empty) per-query results.
        _cache.put("arxiv", q, parsed)
        for p in parsed:
            pid = p.get("arxiv_id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                papers.append(p)
                if len(papers) >= max_total:
                    break

    return papers

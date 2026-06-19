"""arXiv Atom 检索 (SOP §8.3)."""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

from .._http import HttpError, fetch_with_timeout


ARXIV_API = "http://export.arxiv.org/api/query"
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


async def arxiv_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """从 arXiv 检索 paper 原始 dict 列表."""

    results: list[dict] = []
    qs = queries[:1] if queries else []
    for q in qs:
        url = f"{ARXIV_API}?search_query=all:{q}&start=0&max_results={top_k}"
        try:
            data = await fetch_with_timeout(url, client=client, timeout=10.0)
        except HttpError:
            raise
        if not isinstance(data, str):
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        for entry in root.findall(f"{_ATOM_NS}entry"):
            d = _parse_entry(entry)
            if d:
                results.append(d)
    return results[:top_k]

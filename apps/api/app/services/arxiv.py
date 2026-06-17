"""arXiv 公开 API 客户端 (无 LLM 依赖).

GET http://export.arxiv.org/api/query?search_query=all:QUERY&max_results=N
返回 Atom XML; 用 stdlib xml.etree 解析.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "TopicPilot-CN-OneTopic-MVP/0.2"


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    year: int
    summary: str
    abs_url: str
    pdf_url: str
    categories: list[str]


def _safe_query(q: str) -> str:
    q = (q or "").strip()
    if len(q) < 3:
        return ""
    return q


def _fetch_xml(client: httpx.Client, url: str, timeout: float) -> bytes | None:
    try:
        r = client.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        return r.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("arxiv fetch failed: %s | url=%s", exc, url)
        return None


def _parse_entries(xml_bytes: bytes) -> list[ArxivPaper]:
    papers: list[ArxivPaper] = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.warning("arxiv parse failed: %s", exc)
        return []
    for entry in root.findall(f"{ARXIV_NS}entry"):
        try:
            arxiv_id_full = (entry.findtext(f"{ARXIV_NS}id") or "").split("/")[-1]
            m = re.match(r"^([a-z\-]+/)?(\d+\.\d+)(v\d+)?$", arxiv_id_full)
            arxiv_id = ((m.group(1) or "") + m.group(2)) if m else arxiv_id_full
            title = (entry.findtext(f"{ARXIV_NS}title") or "").strip()
            summary = (entry.findtext(f"{ARXIV_NS}summary") or "").strip()
            published = entry.findtext(f"{ARXIV_NS}published") or ""
            year = int(published[:4]) if published[:4].isdigit() else 0
            authors = [
                (a.findtext(f"{ARXIV_NS}name") or "").strip()
                for a in entry.findall(f"{ARXIV_NS}author")
            ]
            authors = [a for a in authors if a]
            abs_url = (entry.findtext(f"{ARXIV_NS}id") or "").strip()
            pdf_url = abs_url.replace("/abs/", "/pdf/") + ".pdf" if abs_url else ""
            categories = [
                (c.get("term") or "").strip()
                for c in entry.findall(f"{ARXIV_NS}category")
            ]
            categories = [c for c in categories if c]
            if not title:
                continue
            papers.append(ArxivPaper(
                arxiv_id=arxiv_id or arxiv_id_full,
                title=title,
                authors=authors,
                year=year,
                summary=summary,
                abs_url=abs_url,
                pdf_url=pdf_url,
                categories=categories,
            ))
        except Exception as exc:  # noqa: BLE001
            logger.debug("skip bad entry: %s", exc)
            continue
    return papers


def search_arxiv(
    queries: list[str],
    max_per_query: int = 3,
    max_total: int = 8,
    timeout: float = 10.0,
) -> list[ArxivPaper]:
    """多 query 检索, 去重, 截断到 max_total. 失败返回 []."""

    seen: set[str] = set()
    out: list[ArxivPaper] = []
    clean_queries = [q for q in (_safe_query(qq) for qq in queries) if q]
    if not clean_queries:
        return out

    with httpx.Client(follow_redirects=True) as client:
        for q in clean_queries:
            url = (
                f"{ARXIV_API}?search_query=all:{urllib.parse.quote(q)}"
                f"&start=0&max_results={max_per_query}"
                f"&sortBy=relevance&sortOrder=descending"
            )
            xml_bytes = _fetch_xml(client, url, timeout)
            if not xml_bytes:
                continue
            for paper in _parse_entries(xml_bytes):
                if paper.arxiv_id in seen:
                    continue
                seen.add(paper.arxiv_id)
                out.append(paper)
                if len(out) >= max_total:
                    return out
    return out


def summarize_paper_zh(title: str, summary: str) -> str:
    """无 LLM 的轻量中文摘要 (启发式)."""

    cleaned = (title or "").strip().rstrip(".")
    if cleaned:
        return f"该文研究: {cleaned}."
    return "arXiv 公开论文."

"""Paper metadata resolver (Session 46).

从 PDF 全文启发式抽取 title / abstract / doi / arxiv_id / year,
用 materials/pdf_parser.extract_paper_candidates.
如果 arxiv metadata 已知, 优先用 arxiv 的 (更准确).
"""

from __future__ import annotations

import re
from typing import Any

from ..materials import pdf_parser as mat_pdf


def resolve_from_arxiv_metadata(
    *,
    arxiv_id: str | None,
    arxiv_title: str,
    arxiv_authors: list[str],
    arxiv_year: int | None,
    arxiv_summary: str,
    arxiv_url: str,
) -> dict[str, Any]:
    """arXiv 已知, 直接用 metadata (不依赖 PDF 文本)."""

    return {
        "title": arxiv_title or f"arXiv:{arxiv_id or 'unknown'}",
        "authors": list(arxiv_authors or []),
        "year": arxiv_year,
        "doi": None,
        "arxiv_id": arxiv_id,
        "abstract": arxiv_summary or None,
        "url": arxiv_url or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None),
    }


def resolve_from_pdf_text(text: str, *, arxiv_id: str | None = None) -> dict[str, Any]:
    """从 PDF 全文启发式抽取 (复用 materials/pdf_parser.extract_paper_candidates)."""

    out = mat_pdf.extract_paper_candidates(text or "")
    # year: 从首 2000 字符里找 4 位年份
    year = _extract_year(text[:2000] if text else "")
    return {
        "title": out.get("title") or "untitled",
        "authors": [],
        "year": year,
        "doi": out.get("doi"),
        "arxiv_id": out.get("arxiv_id") or arxiv_id,
        "abstract": out.get("abstract"),
        "url": out.get("url"),
    }


_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _extract_year(text: str) -> int | None:
    if not text:
        return None
    m = _YEAR_RE.search(text)
    if m:
        return int(m.group(0))
    return None


def resolve_combined(
    *,
    arxiv_id: str | None,
    arxiv_title: str,
    arxiv_authors: list[str],
    arxiv_year: int | None,
    arxiv_summary: str,
    arxiv_url: str,
    pdf_text: str | None,
) -> dict[str, Any]:
    """优先 arXiv metadata, 缺字段时用 PDF 启发式补全."""

    base = resolve_from_arxiv_metadata(
        arxiv_id=arxiv_id,
        arxiv_title=arxiv_title,
        arxiv_authors=arxiv_authors,
        arxiv_year=arxiv_year,
        arxiv_summary=arxiv_summary,
        arxiv_url=arxiv_url,
    )
    if not pdf_text:
        return base
    pdf = resolve_from_pdf_text(pdf_text, arxiv_id=arxiv_id)
    # arXiv 已有时, 只补缺
    if not base.get("title") or base["title"].startswith("arXiv:"):
        if pdf.get("title") and pdf["title"] != "untitled":
            base["title"] = pdf["title"]
    if not base.get("doi") and pdf.get("doi"):
        base["doi"] = pdf["doi"]
    if not base.get("abstract") and pdf.get("abstract"):
        base["abstract"] = pdf["abstract"]
    if not base.get("url") and pdf.get("url"):
        base["url"] = pdf["url"]
    if not base.get("year") and pdf.get("year"):
        base["year"] = pdf["year"]
    if not base.get("arxiv_id") and pdf.get("arxiv_id"):
        base["arxiv_id"] = pdf["arxiv_id"]
    return base

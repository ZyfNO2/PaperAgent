"""网页文字 / URL+描述 解析 (SOP §10)."""

from __future__ import annotations

from typing import Any

from .pdf_parser import extract_paper_candidates


def parse_web_text(
    text: str,
    *,
    url: str | None = None,
    user_note: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """解析粘贴的网页正文或 URL + 描述.

    策略:
    - 优先从 text 抽 DOI / arXiv / 标题;
    - url 给定时优先走 paper 路径;
    - 仅 user_note 时退化为 note.
    """

    warnings: list[str] = []
    candidates = extract_paper_candidates(text or "")
    suggested_type = "note"
    confidence = 0.6
    summary_parts: list[str] = []
    if user_note:
        summary_parts.append(user_note.strip())
    if text:
        # 摘要 = 前 800 字
        snippet = (text.strip().splitlines() or [""])
        joined = " ".join(s.strip() for s in snippet[:8] if s.strip())
        summary_parts.append(joined[:800])
    summary = "\n".join(summary_parts).strip() or "网页资料"

    extracted_claims: list[str] = []
    if candidates.get("doi"):
        suggested_type = "paper"
        confidence = 0.8
        extracted_claims.append(f"DOI: {candidates['doi']}")
    elif candidates.get("arxiv_id"):
        suggested_type = "paper"
        confidence = 0.8
        extracted_claims.append(f"arXiv: {candidates['arxiv_id']}")
    elif url and ("github.com" in url.lower() or "gitlab" in url.lower()):
        suggested_type = "repo"
        confidence = 0.6

    if not url and not text.strip() and not user_note:
        warnings.append("网页资料为空")

    return {
        "text": text or "",
        "title": candidates.get("title") or title,
        "summary": summary,
        "suggested_type": suggested_type,
        "extracted_claims": extracted_claims,
        "possible_url": url or candidates.get("url"),
        "possible_doi": candidates.get("doi"),
        "possible_arxiv_id": candidates.get("arxiv_id"),
        "page_refs": [],
        "confidence": confidence,
        "warnings": warnings,
    }


def parse_url_note(
    url: str,
    *,
    user_note: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    """URL + 用户描述, 退化为 paper / repo / note 之一."""

    return parse_web_text("", url=url, user_note=user_note, title=title)


def parse_manual_note(text: str, *, user_note: str | None = None, title: str | None = None) -> dict[str, Any]:
    """导师备注 / 手动文字 (SOP §10.2)."""

    summary = (user_note or text or title or "").strip()
    snippet = (text or "").strip()
    if snippet and len(snippet) > 800:
        snippet = snippet[:800] + "…"
    return {
        "text": text or "",
        "title": title or "导师备注",
        "summary": summary,
        "suggested_type": "note",
        "extracted_claims": [],
        "possible_url": None,
        "possible_doi": None,
        "possible_arxiv_id": None,
        "page_refs": [],
        "confidence": 1.0,  # 用户自写 = 高置信
        "warnings": [],
    }
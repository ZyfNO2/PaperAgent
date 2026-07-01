"""arXiv 下载器 (Session 46).

输入 arXiv ID / URL → 解析 → 拿 metadata (复用 services/arxiv.py) → 下载 PDF bytes.
失败兜底: 返回 None + 占位 metadata, 不挂服务.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

import httpx

from ..arxiv import ArxivPaper, search_arxiv

logger = logging.getLogger(__name__)


ARXIV_PDF_BASE = "https://arxiv.org/pdf"


# ---------- arXiv ID 解析 ---------- #


_ARXIV_ID_RE = re.compile(
    r"(\d{4}\.\d{4,5}(?:v\d+)?)",
    re.IGNORECASE,
)
_ARXIV_OLD_ID_RE = re.compile(
    r"([a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)


def parse_arxiv_id(arxiv_id_or_url: str) -> str | None:
    """从 ID / URL / abs 链接中抽 arXiv ID."""

    if not arxiv_id_or_url:
        return None
    s = arxiv_id_or_url.strip()
    # 旧式 arXiv: cs/0123456, math.GT/0309136
    m = _ARXIV_OLD_ID_RE.search(s)
    if m:
        return m.group(1)
    # 新式 4 位年 + . + 4-5 位
    m = _ARXIV_ID_RE.search(s)
    if m:
        return m.group(1)
    return None


# ---------- 数据结构 ---------- #


@dataclass
class ArxivFetchResult:
    """下载结果, 含失败兜底字段."""

    arxiv_id: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    summary: str = ""
    abs_url: str = ""
    pdf_url: str = ""
    pdf_bytes: bytes | None = None
    parse_status: str = "failed"  # parsed / failed
    error: str | None = None
    categories: list[str] = field(default_factory=list)


# ---------- metadata + PDF 下载 ---------- #


def _lookup_metadata(arxiv_id: str) -> ArxivPaper | None:
    """用 services/arxiv.search_arxiv 查 metadata."""

    try:
        results = search_arxiv([arxiv_id], max_per_query=1, max_total=1, timeout=10.0)
    except Exception as exc:  # noqa: BLE001
        logger.warning("arxiv metadata search failed for %s: %s", arxiv_id, exc)
        return None
    if not results:
        return None
    # 严格匹配 (大小写不敏感)
    for p in results:
        if p.arxiv_id.lower() == arxiv_id.lower():
            return p
    return results[0]  # fallback: 第一个


def _download_pdf(url: str, timeout: float = 30.0) -> bytes | None:
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            r = client.get(url, headers={"User-Agent": "TopicPilot-CN/0.2"})
            r.raise_for_status()
            return r.content
    except Exception as exc:  # noqa: BLE001
        logger.warning("arxiv pdf download failed: %s | url=%s", exc, url)
        return None


def fetch_arxiv(arxiv_id_or_url: str) -> ArxivFetchResult:
    """下载 arXiv 论文: metadata + PDF bytes.

    失败兜底: 返回 ArxivFetchResult(parse_status="failed"), 不抛异常.
    """

    arxiv_id = parse_arxiv_id(arxiv_id_or_url) or arxiv_id_or_url.strip()
    abs_url = f"https://arxiv.org/abs/{arxiv_id}"
    pdf_url = f"{ARXIV_PDF_BASE}/{arxiv_id}.pdf"

    result = ArxivFetchResult(arxiv_id=arxiv_id, abs_url=abs_url, pdf_url=pdf_url)

    # 1. metadata
    paper = _lookup_metadata(arxiv_id)
    if paper:
        result.title = paper.title
        result.authors = list(paper.authors)
        result.year = paper.year or None
        result.summary = paper.summary
        result.abs_url = paper.abs_url or abs_url
        result.pdf_url = paper.pdf_url or pdf_url
        result.categories = list(paper.categories)
    else:
        result.title = f"arXiv:{arxiv_id} (metadata unavailable)"
        result.error = "metadata_lookup_failed"

    # 2. PDF
    pdf_bytes = _download_pdf(result.pdf_url)
    if pdf_bytes and len(pdf_bytes) > 100:
        result.pdf_bytes = pdf_bytes
        result.parse_status = "parsed"
    else:
        result.pdf_bytes = None
        result.parse_status = "failed"
        if not result.error:
            result.error = "pdf_download_failed"

    return result


# ---------- 失败占位 ---------- #


def make_placeholder_result(arxiv_id_or_url: str, reason: str = "lookup_failed") -> ArxivFetchResult:
    """完全失败时, 生成一个只含 arxiv_id 的占位结果 (供 ingest 流程使用)."""

    arxiv_id = parse_arxiv_id(arxiv_id_or_url) or arxiv_id_or_url.strip() or f"unknown_{uuid.uuid4().hex[:6]}"
    return ArxivFetchResult(
        arxiv_id=arxiv_id,
        title=f"arXiv:{arxiv_id} (placeholder)",
        summary="(arXiv API unreachable, placeholder only)",
        abs_url=f"https://arxiv.org/abs/{arxiv_id}",
        pdf_url=f"{ARXIV_PDF_BASE}/{arxiv_id}.pdf",
        pdf_bytes=None,
        parse_status="failed",
        error=reason,
    )

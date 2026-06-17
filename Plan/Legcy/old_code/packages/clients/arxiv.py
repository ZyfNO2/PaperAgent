"""arXiv 公开 API 客户端.

GET http://export.arxiv.org/api/query?search_query=all:QUERY&max_results=N
返回 Atom XML; 用 stdlib xml.etree 解析, 不引入新依赖.

LLM 中文翻译 (可选): `summarize_paper(title, summary) -> {summary_zh, keywords_zh, field}`
LLM 失败 → fallback 到英文 summary 截断版.
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ARXIV_API = "http://export.arxiv.org/api/query"
ARXIV_NS = "{http://www.w3.org/2005/Atom}"


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
    """清洗 + 转义; 拒绝过短."""
    q = (q or "").strip()
    if len(q) < 3:
        return ""
    return q


def _fetch_xml(url: str, timeout: float) -> bytes | None:
    req = urllib.request.Request(url, headers={"User-Agent": "TopicPilot-CN/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
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
            # 形如 "2401.12345v2" 或 "cs-IR-2401.12345v1"; 去掉尾部 v 数字
            import re as _re
            m = _re.match(r"^([a-z\-]+/)?(\d+\.\d+)(v\d+)?$", arxiv_id_full)
            arxiv_id = (m.group(1) or "") + m.group(2) if m else arxiv_id_full
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
    max_total: int = 10,
    timeout: float = 10.0,
) -> list[ArxivPaper]:
    """多 query 检索; 去重; 截断到 max_total. 失败返回 [].

    每个 query 单独打 arXiv, 不做 AND 拼接, 让每个词都返回它最相关的 N 条.
    """
    seen_ids: set[str] = set()
    out: list[ArxivPaper] = []
    for q in queries:
        clean = _safe_query(q)
        if not clean:
            continue
        # sortBy=relevance + sortOrder=descending 让 arXiv 按匹配度排, 不按日期
        url = (
            f"{ARXIV_API}?search_query=all:{urllib.parse.quote(clean)}"
            f"&start=0&max_results={max_per_query}"
            f"&sortBy=relevance&sortOrder=descending"
        )
        xml_bytes = _fetch_xml(url, timeout)
        if not xml_bytes:
            continue
        for paper in _parse_entries(xml_bytes):
            if paper.arxiv_id in seen_ids:
                continue
            seen_ids.add(paper.arxiv_id)
            out.append(paper)
            if len(out) >= max_total:
                return out
    return out


# ---------- 启发式中文摘要 (无 LLM) ----------

_CATEGORY_FIELD: dict[str, str] = {
    "cs.CV": "计算机视觉",
    "cs.LG": "机器学习",
    "cs.AI": "人工智能",
    "cs.CL": "自然语言处理",
    "cs.IR": "信息检索",
    "cs.RO": "机器人",
    "cs.NE": "神经计算",
    "cs.MM": "多媒体",
    "cs.DS": "算法",
    "eess.IV": "图像视频处理",
    "stat.ML": "统计机器学习",
}


def _heuristic_field(cats: list[str]) -> str:
    for c in cats or []:
        if c in _CATEGORY_FIELD:
            return _CATEGORY_FIELD[c]
    return "计算机科学"


def _heuristic_keywords(title: str, summary: str, max_kw: int = 5) -> list[str]:
    import re as _re
    text = (title or "") + " " + (summary or "")
    words = _re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text)
    stop = {
        "the", "and", "for", "with", "from", "this", "that", "have", "has",
        "are", "was", "were", "been", "into", "about", "based", "using",
        "our", "their", "than", "more", "less", "other", "such", "these",
        "show", "demonstrate", "results", "method", "approach", "paper",
    }
    seen: set[str] = set()
    out: list[str] = []
    for w in words:
        wl = w.lower()
        if wl in stop or wl in seen:
            continue
        seen.add(wl)
        out.append(w)
        if len(out) >= max_kw:
            break
    return out


def _heuristic_zh_summary(title: str) -> str:
    cleaned = (title or "").strip().rstrip(".")
    if not cleaned:
        return "arXiv 公开论文."
    return f"该文研究: {cleaned}. 公开论文, 可下载 PDF."


def summarize_paper(title: str, summary: str) -> dict[str, object]:
    """轻量元数据: 中文 1 句 + 中文关键词 + 研究领域 (无 LLM, 启发式)."""
    import re as _re
    m = _re.findall(r"\b([a-z]+\.[A-Z]{2,3})\b", (summary or "")[:300])
    cats = m[:3]
    return {
        "field": _heuristic_field(cats),
        "summary_zh": _heuristic_zh_summary(title),
        "keywords_zh": _heuristic_keywords(title, summary),
    }


@dataclass
class PaperSummary:
    """LLM 翻译后的中文摘要."""

    summary_zh: str         # 中文一句话简介
    keywords_zh: list[str]  # 中文关键词 5 个
    field: str             # 研究领域


_SUMMARIZE_PROMPT = """你是学术翻译助手. 给定 1 篇 arXiv 论文 (英文 title + abstract),
输出严格 JSON:
{{"summary_zh": "中文一句话简介 (50-100 字)", "keywords_zh": ["中文关键词 5 个"], "field": "研究领域 (如 工业质检 / 推荐系统 / 目标检测)"}}

只输出 JSON, 不要解释.

title: {title}
abstract: {summary}
"""


def summarize_paper(title: str, summary: str) -> PaperSummary:
    """LLM 把英文摘要翻译成中文一句话 + 关键词 + 研究领域. 失败 fallback 英文截断."""

    fallback = PaperSummary(
        summary_zh=(summary or "")[:80] + ("..." if summary and len(summary) > 80 else ""),
        keywords_zh=[w for w in (title.split() if title else [])[:5]],
        field="(领域未识别)",
    )
    try:
        from packages.llm import chat_json, LLMUnavailable  # 延迟 import 避免循环
    except ImportError:
        return fallback

    try:
        raw = chat_json(
            [
                {"role": "system", "content": "严格按 schema 输出 JSON."},
                {"role": "user", "content": _SUMMARIZE_PROMPT.format(
                    title=title or "", summary=(summary or "")[:800],
                )},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        if not isinstance(raw, dict):
            return fallback
        sz = str(raw.get("summary_zh", "")).strip()
        kw = raw.get("keywords_zh") or []
        field = str(raw.get("field", "")).strip() or "(领域未识别)"
        if not sz:
            return fallback
        if not isinstance(kw, list):
            kw = []
        return PaperSummary(
            summary_zh=sz[:200],
            keywords_zh=[str(x).strip() for x in kw if x][:5],
            field=field,
        )
    except Exception:  # noqa: BLE001
        return fallback

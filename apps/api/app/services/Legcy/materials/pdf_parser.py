"""PDF 解析 (SOP §8): 优先 pypdf, 无库时降级 skipped.

不依赖外部库, 仅做最小文本抽取与启发式. 真实环境若安装 pypdf / pdfplumber /
PyMuPDF, 会自动启用更精准的解析. 测试可通过 ``pdf_parser.set_default_text(...)``
注入纯文本, 跳过文件读取.
"""

from __future__ import annotations

import io
import os
import re
from typing import Any


# 测试钩子: 允许测试注入 PDF 文本而不必真实读 PDF
_DEFAULT_TEXT: dict[str, str] = {}


def set_default_text(material_id: str, text: str) -> None:
    """测试用: 注入 material_id 对应的解析文本."""

    _DEFAULT_TEXT[material_id] = text


def clear_default_text() -> None:
    _DEFAULT_TEXT.clear()


def _extract_with_pypdf(data: bytes) -> tuple[str, int, list[str]]:
    try:
        import pypdf  # type: ignore
    except ImportError:
        return "", 0, []
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        n = len(reader.pages)
        out: list[str] = []
        for i, p in enumerate(reader.pages):
            try:
                out.append(p.extract_text() or "")
            except Exception:
                out.append("")
        return "\n".join(out), n, [f"p{i+1}" for i in range(n)]
    except Exception:
        return "", 0, []


def _extract_minimal(data: bytes) -> tuple[str, int, list[str]]:
    """无 pypdf 时尝试最弱解析: 在 PDF 字节中找可读文本流.

    不保证稳定, 但能给测试一个 fallback 路径.
    """

    # 找 BT...ET text blocks, 简单抽取括号内文本
    try:
        text = data.decode("latin1", errors="replace")
    except Exception:
        return "", 0, []
    blocks = re.findall(r"BT(.*?)ET", text, flags=re.DOTALL)
    if not blocks:
        return "", 0, []
    chunks: list[str] = []
    for b in blocks:
        for m in re.finditer(r"\((.*?)\)\s*Tj", b, flags=re.DOTALL):
            chunks.append(m.group(1))
    page_refs = [f"p{i+1}" for i in range(len(blocks))]
    return " ".join(chunks), len(blocks), page_refs


def parse_pdf(data: bytes, material_id: str | None = None) -> dict[str, Any]:
    """从 PDF bytes 抽取文本与页码信息.

    返回 dict 字段: ``text / page_count / page_refs / status / confidence / warnings``.
    """

    warnings: list[str] = []
    if material_id and material_id in _DEFAULT_TEXT:
        text = _DEFAULT_TEXT[material_id]
        # 估算页数: 按 \f 或显式 /Page 分隔
        n = text.count("\f") + 1 if text else 1
        page_refs = [f"p{i+1}" for i in range(n)]
        return {
            "text": text,
            "page_count": n,
            "page_refs": page_refs,
            "status": "parsed",
            "confidence": 0.85,
            "warnings": [],
        }

    # 优先 pypdf
    text, page_count, page_refs = _extract_with_pypdf(data)
    if text.strip():
        return {
            "text": text,
            "page_count": page_count,
            "page_refs": page_refs,
            "status": "parsed",
            "confidence": 0.85 if page_count else 0.5,
            "warnings": [],
        }

    # 降级: 极简 BT/ET 解析
    text, page_count, page_refs = _extract_minimal(data)
    if text.strip():
        warnings.append("pypdf 未安装, 走最弱 PDF 文本抽取")
        return {
            "text": text,
            "page_count": max(1, page_count),
            "page_refs": page_refs,
            "status": "parsed",
            "confidence": 0.5,
            "warnings": warnings,
        }

    # 完全无文本 -> skipped (SOP §8.2 降级策略)
    return {
        "text": "",
        "page_count": 0,
        "page_refs": [],
        "status": "skipped",
        "confidence": 0.0,
        "warnings": ["未抽取到 PDF 文本层, 可能是扫描版"],
    }


# ---------- 启发式提取: 标题 / 摘要 / DOI / arXiv ---------- #

_DOI_RE = re.compile(r"10\.\d{4,9}/[^\s,;\"<>]+", re.IGNORECASE)
_ARXIV_RE = re.compile(r"(?:arXiv:?\s*|arxiv\.org/abs/)([\d]{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)
_TITLE_HINT_PATTERNS = [
    re.compile(r"^Title:\s*(.+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^#\s+(.+)$", re.MULTILINE),
]
_ABSTRACT_HINT_PATTERNS = [
    re.compile(r"^Abstract[:\.\s]+(.+?)(?:\n\n|\nIntroduction|\n1\.|\Z)", re.IGNORECASE | re.DOTALL | re.MULTILINE),
]


def _short(text: str, n: int = 800) -> str:
    if len(text) <= n:
        return text
    return text[:n - 1] + "…"


def extract_paper_candidates(text: str) -> dict[str, Any]:
    """从 PDF 文本启发式抽取标题 / 摘要 / DOI / arXiv."""

    if not text:
        return {}

    out: dict[str, Any] = {"title": None, "abstract": None, "doi": None, "arxiv_id": None, "url": None}

    # 标题: 优先 Title: / # 标记; 退化用首段非空行
    for p in _TITLE_HINT_PATTERNS:
        m = p.search(text)
        if m:
            t = m.group(1).strip().strip('"').strip()
            if 5 <= len(t) <= 200:
                out["title"] = t
                break
    if not out["title"]:
        # 取前 5 行非空, 最长的一行做标题候选
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if lines:
            cand = max(lines[:8], key=len)
            if 5 <= len(cand) <= 200:
                out["title"] = cand

    # 摘要: Abstract 段
    for p in _ABSTRACT_HINT_PATTERNS:
        m = p.search(text)
        if m:
            out["abstract"] = _short(m.group(1).strip(), 1200)
            break

    # DOI / arXiv
    m = _DOI_RE.search(text)
    if m:
        doi = m.group(0).rstrip(".,;")
        out["doi"] = doi
        out["url"] = f"https://doi.org/{doi}"
    m = _ARXIV_RE.search(text)
    if m:
        out["arxiv_id"] = m.group(1)
        if not out["url"]:
            out["url"] = f"https://arxiv.org/abs/{out['arxiv_id']}"

    return out


def extract_note_summary(text: str, user_note: str | None, max_len: int = 1200) -> str:
    """生成 note 的 summary: 用户说明 + 前 N 字."""

    head = (text or "").strip().splitlines()[:5]
    excerpt = " ".join(ln.strip() for ln in head if ln.strip())
    excerpt = _short(excerpt, max_len - (len(user_note or "") + 4))
    if user_note:
        return f"{user_note}\n\n{excerpt}".strip()
    return excerpt
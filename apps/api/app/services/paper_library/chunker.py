"""Section-aware chunker (Session 46 §7).

策略 (SOP §7):
- 章节标题粗分 (正则识别 Abstract / 1 Introduction / 2 Related Work 等)
- 每块 600–1000 tokens, overlap 100
- abstract / introduction / method / experiment / conclusion 独立成块
- reference 整块丢弃

token_count 用简单空格分词估算 (不依赖 tokenizer 库).
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from ...schemas_paper_library import PaperChunk, ChunkType

ChunkTypeStr = Literal[
    "title", "abstract", "introduction", "related_work",
    "method", "experiment", "result", "limitation",
    "conclusion", "reference", "unknown",
]


# ---------- 章节识别 ---------- #

# 匹配诸如 "Abstract", "1 Introduction", "2.1 Method", "REFERENCES" 等
_SECTION_PATTERNS: list[tuple[re.Pattern, str, ChunkType]] = [
    # Abstract
    (re.compile(r"^\s*(?:Abstract|ABSTRACT|摘要)\s*[:\.]?\s*$", re.IGNORECASE | re.MULTILINE), "Abstract", "abstract"),
    # 1 Introduction
    (re.compile(r"^\s*\d+\.?\s+(Introduction|INTRODUCTION)\s*$", re.IGNORECASE | re.MULTILINE), "Introduction", "introduction"),
    # 2 Related Work / Background
    (re.compile(r"^\s*\d+\.?\s+(Related\s+Work|Related\s+Works|Background|RELATED\s+WORK|BACKGROUND)\s*$", re.IGNORECASE | re.MULTILINE), "Related Work", "related_work"),
    # 3 Method / Methodology / Approach / Model
    (re.compile(r"^\s*\d+\.?\s+(Method|Methods|Methodology|Approach|Model|Models|PROPOSED\s+METHOD|METHODOLOGY)\s*$", re.IGNORECASE | re.MULTILINE), "Method", "method"),
    # 4 Experiment / Experiments / Experimental Setup / Evaluation
    (re.compile(r"^\s*\d+\.?\s+(Experiment|Experiments|Experimental\s+Setup|Evaluation|Experimental|EXPERIMENTS|EVALUATION)\s*$", re.IGNORECASE | re.MULTILINE), "Experiment", "experiment"),
    # 5 Results / Discussion
    (re.compile(r"^\s*\d+\.?\s+(Results?|Result\s+and\s+Discussion|RESULTS|DISCUSSION)\s*$", re.IGNORECASE | re.MULTILINE), "Result", "result"),
    # 6 Limitation / Limitations
    (re.compile(r"^\s*\d+\.?\s+(Limitations?|LIMITATIONS?)\s*$", re.IGNORECASE | re.MULTILINE), "Limitation", "limitation"),
    # 7 Conclusion / Conclusions / Concluding Remarks
    (re.compile(r"^\s*\d+\.?\s+(Conclusions?|Conclusion\s+and\s+\w+|Concluding\s+Remarks|CONCLUSION)\s*$", re.IGNORECASE | re.MULTILINE), "Conclusion", "conclusion"),
    # References (单独一节, 整块丢弃)
    (re.compile(r"^\s*(References?|REFERENCES?|Bibliography|BIBLIOGRAPHY)\s*$", re.IGNORECASE | re.MULTILINE), "References", "reference"),
]


def _estimate_tokens(text: str) -> int:
    """轻量 token 估算: 单词数 + 中文字数 (不依赖 tokenizer 库).

    英文按空格分词; 中文按字符.
    """

    if not text:
        return 0
    # 拆出英文 token 数
    en_tokens = len(re.findall(r"\b\w+\b", text))
    # 拆出中文字符数 (1 字 ≈ 0.7 token, 这里直接按 1 字 = 1 token 上限估算)
    zh_chars = len(re.findall(r"[一-鿿]", text))
    return en_tokens + zh_chars

def _detect_sections(text: str) -> list[tuple[int, str, ChunkType]]:
    """检测 (offset, section_title, chunk_type) 列表, 按 offset 升序."""

    found: list[tuple[int, str, ChunkType]] = []
    for pat, title, ctype in _SECTION_PATTERNS:
        for m in pat.finditer(text):
            found.append((m.start(), title, ctype))
    found.sort(key=lambda x: x[0])
    return found


def _split_paragraphs(text: str) -> list[str]:
    """按双换行 / 单换行 / 句号粗分段落."""

    # 先按双换行
    parts = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) > 1500:
            # 太长就再按单换行切
            for sub in p.split("\n"):
                sub = sub.strip()
                if sub:
                    out.append(sub)
        else:
            out.append(p)
    return out


def _slice_by_tokens(paragraphs: list[str], chunk_min: int = 600, chunk_max: int = 1000, overlap: int = 100) -> list[str]:
    """把段落组装成 600-1000 token 的块, 块间 overlap ~100 token.

    简单策略: 累积段落直到达到 chunk_min, 切块; 然后从末尾 overlap 重新累积.
    """

    chunks: list[str] = []
    buf: list[str] = []
    buf_tokens = 0
    overlap_buf: list[str] = []
    overlap_tokens = 0

    for p in paragraphs:
        ptoks = _estimate_tokens(p)
        # 单段太长, 独立成块
        if ptoks >= chunk_max:
            if buf:
                chunks.append("\n\n".join(buf))
                buf, buf_tokens = [], 0
            # 单段切两半
            half = max(chunk_min, ptoks // 2)
            mid = len(p) // 2
            chunks.append(p[:mid].strip())
            buf.append(p[mid:].strip())
            buf_tokens = _estimate_tokens("\n\n".join(buf))
            overlap_buf, overlap_tokens = list(buf), buf_tokens
            continue

        # 超过 chunk_max 就切块
        if buf_tokens + ptoks > chunk_max and buf_tokens >= chunk_min:
            chunks.append("\n\n".join(buf))
            # 保留尾部 overlap
            new_buf: list[str] = []
            new_toks = 0
            for q in reversed(buf):
                qt = _estimate_tokens(q)
                if new_toks + qt > overlap:
                    break
                new_buf.insert(0, q)
                new_toks += qt
            buf = new_buf + [p]
            buf_tokens = _estimate_tokens("\n\n".join(buf))
            continue

        buf.append(p)
        buf_tokens += ptoks

        # 达到 chunk_min 且下一段加进来超 chunk_max, 也可切 (防止单段很小的死循环)
        if buf_tokens >= chunk_min and ptoks > 200:
            chunks.append("\n\n".join(buf))
            new_buf = []
            new_toks = 0
            for q in reversed(buf):
                qt = _estimate_tokens(q)
                if new_toks + qt > overlap:
                    break
                new_buf.insert(0, q)
                new_toks += qt
            buf = new_buf
            buf_tokens = new_toks

    if buf:
        chunks.append("\n\n".join(buf))

    return chunks


def _build_chunk(
    *,
    paper_id: str,
    project_id: str,
    section_title: str,
    section_path: list[str],
    chunk_type: ChunkType,
    text: str,
    page_start: int | None = None,
    page_end: int | None = None,
) -> PaperChunk:
    return PaperChunk(
        chunk_id=f"chunk_{uuid.uuid4().hex[:10]}",
        paper_id=paper_id,
        project_id=project_id,
        section_title=section_title,
        section_path=section_path,
        page_start=page_start,
        page_end=page_end,
        text=text,
        token_count=_estimate_tokens(text),
        chunk_type=chunk_type,
    )


def chunk_text(
    text: str,
    *,
    paper_id: str,
    project_id: str,
    title_hint: str | None = None,
) -> list[PaperChunk]:
    """主入口: 全文 → PaperChunk[] (丢弃 references)."""

    if not text or not text.strip():
        return []

    sections = _detect_sections(text)
    chunks: list[PaperChunk] = []

    if not sections:
        # 没有任何已知章节: 整篇当 unknown 切
        return _chunk_unknown(text, paper_id=paper_id, project_id=project_id)

    # 第一个章节之前的部分: 视为 title (封面/题目/作者)
    first_offset = sections[0][0]
    pre = text[:first_offset].strip()
    if pre and _estimate_tokens(pre) >= 30:
        chunks.append(_build_chunk(
            paper_id=paper_id, project_id=project_id,
            section_title="Title",
            section_path=["Title"],
            chunk_type="title",
            text=pre[:2000],
        ))

    for i, (offset, title, ctype) in enumerate(sections):
        end_offset = sections[i + 1][0] if i + 1 < len(sections) else len(text)
        section_text = text[offset:end_offset].strip()
        if not section_text:
            continue
        # 去掉章节标题行
        body = re.sub(rf"^\s*{re.escape(title)}\s*[:\.]?\s*\n?", "", section_text, flags=re.IGNORECASE).strip()
        if not body:
            body = section_text

        if ctype == "reference":
            # 整段丢弃, 不进 chunks
            continue

        paragraphs = _split_paragraphs(body)
        sliced = _slice_by_tokens(paragraphs)
        for s in sliced:
            chunks.append(_build_chunk(
                paper_id=paper_id, project_id=project_id,
                section_title=title,
                section_path=[title],
                chunk_type=ctype,
                text=s,
            ))

    return chunks


def _chunk_unknown(text: str, *, paper_id: str, project_id: str) -> list[PaperChunk]:
    paragraphs = _split_paragraphs(text)
    sliced = _slice_by_tokens(paragraphs)
    return [
        _build_chunk(
            paper_id=paper_id, project_id=project_id,
            section_title="Body",
            section_path=["Body"],
            chunk_type="unknown",
            text=s,
        )
        for s in sliced
    ]

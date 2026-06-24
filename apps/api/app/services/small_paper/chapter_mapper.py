"""Small paper → thesis chapter mapping (Session 49 §5).

按 section_title + chunk_type 把小论文内容映射到 7 个大论文章节:
ch1_intro / ch2_related / ch3_method / ch4_experiment / ch5_conclusion /
appendix / unmapped.
"""

from __future__ import annotations

import logging
from typing import Iterable

from ...schemas_paper_library import PaperChunk
from ...schemas_small_paper import ChapterMapping, ReuseType, ThesisChapter

logger = logging.getLogger(__name__)


# chunk_type → thesis_chapter + 默认 reuse_type
_TYPE_TO_CHAPTER: dict[str, tuple[ThesisChapter, ReuseType, str]] = {
    "title": ("ch1_intro", "summarize", "论文标题作为大论文选题起点"),
    "abstract": ("ch1_intro", "summarize", "摘要扩成大论文引言研究背景"),
    "introduction": ("ch1_intro", "summarize", "引言内容可拆分为研究背景 / 研究问题"),
    "related_work": ("ch2_related", "extend", "相关工作需扩展为更系统的文献综述"),
    "method": ("ch3_method", "direct_reuse", "方法主体可作为大论文核心方法章基础"),
    "experiment": ("ch4_experiment", "direct_reuse", "实验设置可作为大论文实验章基础"),
    "result": ("ch4_experiment", "direct_reuse", "实验结果可作为大论文实验章基础 (需扩展)"),
    "limitation": ("ch5_conclusion", "extend", "局限性可作为大论文结论章延伸"),
    "conclusion": ("ch5_conclusion", "extend", "结论可作为大论文结论章基础"),
    "reference": ("unmapped", "cannot_reuse", "参考文献不直接进大论文, 仅供检索"),
    "unknown": ("unmapped", "cannot_reuse", "未识别章节, 需人工处理"),
}

# section_title 关键词 → thesis_chapter (备选, section_title 比 chunk_type 优先级高)
_TITLE_HINTS: list[tuple[set[str], ThesisChapter, ReuseType, str]] = [
    ({"background", "motivation", "研究背景", "背景"}, "ch1_intro", "summarize", "标题含研究背景"),
    ({"related work", "literature", "相关工作", "研究现状", "国内外研究"}, "ch2_related", "extend", "标题含相关工作"),
    ({"method", "methodology", "approach", "model", "方法", "方法主体"}, "ch3_method", "direct_reuse", "标题含方法"),
    ({"ablation", "消融"}, "ch4_experiment", "direct_reuse", "消融实验直接复用"),
    ({"experiment", "evaluation", "experiment setup", "实验", "实验设置"}, "ch4_experiment", "direct_reuse", "标题含实验"),
    ({"result", "performance", "结果", "实验结果"}, "ch4_experiment", "direct_reuse", "标题含结果"),
    ({"limitation", "局限", "不足"}, "ch5_conclusion", "extend", "标题含局限性"),
    ({"conclusion", "concluding", "结论"}, "ch5_conclusion", "extend", "标题含结论"),
]


def _classify_by_title(section_title: str | None) -> tuple[ThesisChapter, ReuseType, str] | None:
    if not section_title:
        return None
    title_low = section_title.strip().lower()
    for hints, chapter, reuse, note in _TITLE_HINTS:
        for h in hints:
            if h.lower() in title_low:
                return chapter, reuse, note
    return None


def map_chapters(chunks: list[PaperChunk]) -> list[ChapterMapping]:
    """按 chunk 列表生成小论文 → 大论文章节映射.

    去重: 同 (small_paper_section, thesis_chapter) 只保留第一条;
    保留首次出现顺序.
    """

    seen: set[tuple[str, str]] = set()
    out: list[ChapterMapping] = []

    for c in chunks:
        sec_title = c.section_title or "(未命名章节)"

        # 优先级 1: section_title 关键词
        by_title = _classify_by_title(sec_title)
        if by_title:
            chapter, reuse, note = by_title
        else:
            # 优先级 2: chunk_type
            chapter, reuse, note = _TYPE_TO_CHAPTER.get(
                c.chunk_type or "unknown",
                ("unmapped", "cannot_reuse", "未知章节"),
            )

        if chapter == "unmapped":
            continue  # 不计入大论文 (reference / unknown)

        key = (sec_title, chapter)
        if key in seen:
            continue
        seen.add(key)

        out.append(ChapterMapping(
            small_paper_section=sec_title,
            thesis_chapter=chapter,
            reuse_type=reuse,
            note=note,
        ))

    return out


def covered_chapters(mappings: list[ChapterMapping]) -> set[ThesisChapter]:
    """从映射结果取已覆盖的章节集合."""

    return {m.thesis_chapter for m in mappings}


def find_unmapped_sections(chunks: list[PaperChunk]) -> list[str]:
    """列出无法映射的章节标题 (供报告 / 前端展示)."""

    out: list[str] = []
    seen: set[str] = set()
    for c in chunks:
        if (c.chunk_type or "unknown") in ("reference", "unknown"):
            sec = c.section_title or "(未命名章节)"
            if sec not in seen:
                seen.add(sec)
                out.append(sec)
    return out


def filter_mappings_by_chapter(
    mappings: list[ChapterMapping],
    chapter: ThesisChapter,
) -> list[ChapterMapping]:
    return [m for m in mappings if m.thesis_chapter == chapter]


__all__ = [
    "map_chapters",
    "covered_chapters",
    "find_unmapped_sections",
    "filter_mappings_by_chapter",
]

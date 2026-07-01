"""Small paper gap analyzer (Session 49 §5.2).

基于 ChapterMapping + SmallPaperCard.missing_for_thesis 计算大论文缺口.
"""

from __future__ import annotations

import logging
from typing import Iterable

from ...schemas_small_paper import (
    ChapterMapping,
    SmallPaperCard,
    ThesisChapter,
)

logger = logging.getLogger(__name__)


# 大论文 5 章标准 (常用) — 排除 appendix / unmapped
STANDARD_CHAPTERS: tuple[ThesisChapter, ...] = (
    "ch1_intro",
    "ch2_related",
    "ch3_method",
    "ch4_experiment",
    "ch5_conclusion",
)

_CHAPTER_LABEL_ZH: dict[ThesisChapter, str] = {
    "ch1_intro": "第 1 章 研究背景与意义",
    "ch2_related": "第 2 章 国内外研究现状",
    "ch3_method": "第 3 章 研究方法",
    "ch4_experiment": "第 4 章 实验与结果",
    "ch5_conclusion": "第 5 章 结论与展望",
    "appendix": "附录",
    "unmapped": "未映射",
}


def chapter_label(ch: ThesisChapter) -> str:
    return _CHAPTER_LABEL_ZH.get(ch, ch)


def compute_missing_chapters(
    covered: Iterable[ThesisChapter],
    *,
    target: tuple[ThesisChapter, ...] = STANDARD_CHAPTERS,
) -> list[ThesisChapter]:
    """计算 (标准 5 章 - 已覆盖章节) 的缺口, 按标准顺序返回."""

    cov = set(covered)
    return [c for c in target if c not in cov]


def build_gap_analysis(
    card: SmallPaperCard,
    mappings: list[ChapterMapping],
    missing: list[ThesisChapter],
) -> list[str]:
    """生成人类可读的缺口分析 (每条 1-2 句话)."""

    covered = {m.thesis_chapter for m in mappings}
    lines: list[str] = []

    if not missing:
        lines.append("小论文已覆盖 5 章标准结构, 仍需补实验规模 / 工作量 / 工业落地.")
        return lines

    if "ch4_experiment" in missing:
        # 关键缺口: 实验章
        if card.datasets:
            lines.append(
                f"当前小论文可支撑第 3 章, 但第 4 章工作量不足。"
                f"已有数据集 {len(card.datasets)} 个, 建议: 跨数据集泛化 / 工程系统集成 / 数据集扩展 / 轻量化部署 / 失败案例."
            )
        else:
            lines.append(
                "缺少第 4 章实验结果, 建议: 至少补 1 个公开数据集 + 1 个可复现 baseline + 1 个核心指标对比."
            )
    if "ch2_related" in missing:
        lines.append("缺少第 2 章相关工作综述, 建议: 系统检索近 3 年同方向论文 5-10 篇, 形成研究现状矩阵.")
    if "ch1_intro" in missing:
        lines.append("缺少第 1 章研究背景, 建议: 把小论文引言 + 行业背景扩成 2000-3000 字开篇.")
    if "ch3_method" in missing:
        lines.append("缺少第 3 章方法主体, 建议: 详细描述模型架构 / 损失函数 / 训练流程, 配合伪代码 / 流程图.")
    if "ch5_conclusion" in missing:
        lines.append("缺少第 5 章结论, 建议: 总结贡献 + 失败案例 + 边界研究 + 未来工作.")

    # 基于 reusable_chapter_sections 的具体提示
    if card.reusable_chapter_sections:
        lines.append(
            "可复用章节: " + " | ".join(card.reusable_chapter_sections[:3])
        )
    if card.missing_for_thesis:
        lines.append("原论文 missing 提示: " + " | ".join(card.missing_for_thesis[:3]))

    return lines


def suggest_thesis_outline(
    covered: Iterable[ThesisChapter],
    missing: list[ThesisChapter],
) -> list[str]:
    """基于覆盖+缺口, 生成大论文目录建议 (5-7 行)."""

    cov = set(covered)
    outline: list[str] = []

    if "ch1_intro" in cov or "ch1_intro" in missing:
        outline.append("第 1 章 绪论 (研究背景 / 研究问题 / 论文组织)")
    if "ch2_related" in cov or "ch2_related" in missing:
        outline.append("第 2 章 国内外研究现状 (基于小论文相关工作 + 扩展检索)")
    if "ch3_method" in cov or "ch3_method" in missing:
        outline.append("第 3 章 研究方法 (复用小论文方法主体 + 消融 / 改进)")
    if "ch4_experiment" in cov or "ch4_experiment" in missing:
        outline.append("第 4 章 实验与结果 (跨数据集泛化 + 扩展 baseline + 消融)")
    if "ch5_conclusion" in cov or "ch5_conclusion" in missing:
        outline.append("第 5 章 结论与展望 (贡献总结 + 失败案例 + 未来工作)")
    outline.append("参考文献")
    return outline


__all__ = [
    "compute_missing_chapters",
    "build_gap_analysis",
    "suggest_thesis_outline",
    "chapter_label",
    "STANDARD_CHAPTERS",
]

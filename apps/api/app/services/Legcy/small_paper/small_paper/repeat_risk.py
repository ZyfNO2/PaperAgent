"""Repeat risk detector (Session 49 §7).

检测小论文被原样塞进大论文的风险:
- verbatim_copy: 标题 + 摘要 + 方法高度重合 (chunk 数 < 5 且无消融)
- incremental_only: 贡献点仅 1 条, 缺少 2 个以上 baseline
- no_extension: 缺口分析里没找到任何 missing (即 5 章全有) 但实验数 < 3
- method_reuse_only: method_modules 都直接进 ch3 (direct_reuse 占比 > 60%)

每条风险: category / severity / note / related_section.
"""

from __future__ import annotations

import logging

from ...schemas_small_paper import (
    ChapterMapping,
    ExtensionPlan,
    ReuseType,
    RepeatRiskCategory,
    RepeatRiskSeverity,
    RepeatRiskWarning,
    SmallPaperCard,
)

logger = logging.getLogger(__name__)


def detect_repeat_risks(
    card: SmallPaperCard,
    plan: ExtensionPlan,
    mappings: list[ChapterMapping] | None = None,
) -> list[RepeatRiskWarning]:
    """综合 card + plan + mappings 计算风险列表."""

    risks: list[RepeatRiskWarning] = []
    mappings = mappings or []

    # 1) method_reuse_only: direct_reuse 占比 > 60% 且无扩展
    direct = sum(1 for m in mappings if m.reuse_type == "direct_reuse")
    total_chapter_mappings = sum(1 for m in mappings if m.thesis_chapter != "unmapped")
    if total_chapter_mappings > 0 and direct / total_chapter_mappings > 0.6 and not plan.extension_experiments:
        risks.append(RepeatRiskWarning(
            category="method_reuse_only",
            severity="high",
            note=(
                "方法章大量直接复用小论文, 且没有扩展实验。"
                "建议补充消融 / 跨数据集 / 工业部署实验, 体现大论文增量."
            ),
            related_section="ch3_method",
        ))

    # 2) experiment_tables 全 direct_reuse → 提示扩展
    if card.experiment_tables and not plan.extension_experiments:
        risks.append(RepeatRiskWarning(
            category="method_reuse_only",
            severity="medium",
            note=(
                f"实验表格 ({len(card.experiment_tables)} 个) 直接复用, 需新增实验证明扩展性."
            ),
            related_section="ch4_experiment",
        ))

    # 3) incremental_only: 贡献点 < 2 + baselines < 2
    if len(card.contribution_points) < 2 and len(card.baselines) < 2:
        risks.append(RepeatRiskWarning(
            category="incremental_only",
            severity="medium",
            note="贡献点和 baseline 数过少, 大论文容易显得增量不足, 建议补 1-2 个新 baseline 和 1 个新数据集.",
            related_section="ch2_related",
        ))

    # 4) no_extension: plan 里无 extension_experiments 且无 missing (5 章全有但实验弱)
    if not plan.extension_experiments and not plan.missing_chapters:
        risks.append(RepeatRiskWarning(
            category="no_extension",
            severity="medium",
            note="5 章结构齐全但无任何扩展实验, 大论文可能只是小论文加长版, 建议至少加 1 条新实验.",
            related_section="ch4_experiment",
        ))

    # 5) verbatim_copy: 标题中含 'survey / overview / comprehensive' 而非 method 论文, 或 chunk 数极少
    title_low = (card.title or "").lower()
    if any(kw in title_low for kw in ("survey", "overview", "comprehensive review", "综述")):
        risks.append(RepeatRiskWarning(
            category="verbatim_copy",
            severity="low",
            note="小论文为综述类, 大论文需要补原创方法 / 实验, 不能仅做文献综述扩展.",
            related_section="ch3_method",
        ))

    # 6) 贡献点全空: 抽取失败, 也是风险
    if not card.contribution_points:
        risks.append(RepeatRiskWarning(
            category="incremental_only",
            severity="low",
            note="小论文贡献点抽取为空, 抽取置信度低, 建议人工复核后再规划扩展.",
            related_section=None,
        ))

    return risks


__all__ = ["detect_repeat_risks"]

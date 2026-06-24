"""Extension planner (Session 49 §6).

基于缺口生成 ExtensionExperiment + WorkPackageSuggestion.

缺口对应扩展方向 (SOP §6):
  ch4 不足 → 跨数据集泛化 / 工程系统集成 / 轻量化部署
  ch2 不足 → 数据集扩展与分析
  ch5 不足 → 失败案例与边界研究
  通用     → 消融实验 / baseline 扩展
"""

from __future__ import annotations

import logging
from typing import Iterable

from ...schemas_small_paper import (
    ExtensionExperiment,
    ExtensionPlan,
    SmallPaperCard,
    ThesisChapter,
    WorkPackageSuggestion,
)
from .chapter_mapper import covered_chapters
from .gap_analyzer import (
    STANDARD_CHAPTERS,
    build_gap_analysis,
    chapter_label,
    compute_missing_chapters,
    suggest_thesis_outline,
)

logger = logging.getLogger(__name__)


# 缺口 → 扩展实验 (按优先级)
_GAP_TO_EXPERIMENTS: dict[ThesisChapter, list[dict]] = {
    "ch4_experiment": [
        {
            "title": "跨数据集泛化实验",
            "description": "在小论文数据集之外, 至少加 1 个公开数据集 (如 NEU-DET / DeepPCB) 验证方法泛化性",
            "fills": "ch4",
        },
        {
            "title": "工程系统集成",
            "description": "把小论文方法集成到工程系统 (Web / 移动端 / 工业流水线), 给出部署 / 推理性能指标",
            "fills": "ch4/appendix",
        },
        {
            "title": "轻量化部署",
            "description": "通过蒸馏 / 剪枝 / 量化, 在边缘设备 (Jetson / 树莓派) 部署并报告 FPS / 显存",
            "fills": "ch4",
        },
    ],
    "ch2_related": [
        {
            "title": "数据集扩展与对比分析",
            "description": "在相关工作章加入 3-5 个公开数据集的对比矩阵 (规模 / 标注 / 难度)",
            "fills": "ch2",
        },
    ],
    "ch5_conclusion": [
        {
            "title": "失败案例与边界研究",
            "description": "整理 5-10 个失败 case, 分析小论文方法在什么条件下退化 / 失效",
            "fills": "ch5",
        },
    ],
    "ch3_method": [
        {
            "title": "消融实验",
            "description": "对小论文方法每个模块做消融, 验证每个组件的贡献",
            "fills": "ch3/ch4",
        },
    ],
    "ch1_intro": [
        {
            "title": "研究背景扩展",
            "description": "把小论文引言 + 行业背景扩成 2000-3000 字, 加入政策 / 市场 / 用户痛点",
            "fills": "ch1",
        },
    ],
}


def _make_extension_experiment(
    *,
    exp_id: str,
    title: str,
    description: str,
    card: SmallPaperCard,
    fills_chapter: str,
    priority: int,
) -> ExtensionExperiment:
    # 复用 card 里已有的 dataset / baseline 命名, 让扩展实验更可执行
    datasets: list[str] = list(card.datasets[:2])
    if not datasets:
        datasets = ["待补充公开数据集"]
    baselines: list[str] = list(card.baselines[:2])
    if not baselines:
        baselines = ["待补充可复现 baseline"]
    return ExtensionExperiment(
        experiment_id=exp_id,
        title=title,
        description=description,
        datasets=datasets,
        baselines=baselines,
        estimated_effort="medium",
        priority=priority,
        fills_chapter=fills_chapter,
    )


def _make_work_package(
    *,
    wp_id: str,
    title: str,
    goal: str,
    deliverable: str,
    deps: list[str],
    effort: str = "medium",
) -> WorkPackageSuggestion:
    return WorkPackageSuggestion(
        wp_id=wp_id,
        title=title,
        goal=goal,
        deliverable=deliverable,
        estimated_effort=effort,  # type: ignore[arg-type]
        dependencies=deps,
    )


def build_extension_plan(
    card: SmallPaperCard,
    mappings: list,
    *,
    paper_id: str = "",
    project_id: str = "",
    target_chapter_count: int = 5,
) -> ExtensionPlan:
    """综合 card + mapping → ExtensionPlan.

    步骤:
    1. 算 covered / missing
    2. 生成 gap_analysis 文案
    3. 生成 extension_experiments (每缺口 1-3 条, 最多 5 条, 优先级排序)
    4. 生成 second / third work package
    5. 生成 thesis_outline
    6. reuse_risks 留空 (由 repeat_risk.py 填充)
    """

    covered = covered_chapters(mappings)
    target = STANDARD_CHAPTERS[: max(3, min(target_chapter_count, len(STANDARD_CHAPTERS)))]
    missing = compute_missing_chapters(covered, target=target)
    gap = build_gap_analysis(card, mappings, missing)

    # 扩展实验: 按 missing 顺序, 每缺口取该缺口的列表
    experiments: list[ExtensionExperiment] = []
    counter = 1
    priority = 1
    for ch in missing:
        for spec in _GAP_TO_EXPERIMENTS.get(ch, [])[:2]:
            exp = _make_extension_experiment(
                exp_id=f"ext_{counter:02d}",
                title=spec["title"],
                description=spec["description"],
                card=card,
                fills_chapter=spec["fills"],
                priority=priority,
            )
            experiments.append(exp)
            counter += 1
            priority += 1
            if len(experiments) >= 5:
                break
        if len(experiments) >= 5:
            break

    # 兜底: 即使无 missing, 至少给 1 条消融实验
    if not experiments:
        spec = _GAP_TO_EXPERIMENTS["ch3_method"][0]
        experiments.append(_make_extension_experiment(
            exp_id="ext_01",
            title=spec["title"],
            description=spec["description"],
            card=card,
            fills_chapter=spec["fills"],
            priority=1,
        ))

    # 第二 / 第三工作包
    second_wp: WorkPackageSuggestion | None = None
    third_wp: WorkPackageSuggestion | None = None
    if len(experiments) >= 1:
        e1 = experiments[0]
        second_wp = _make_work_package(
            wp_id="WP2",
            title=f"扩展实验: {e1.title}",
            goal=e1.description,
            deliverable=f"实验报告 + 在 {', '.join(e1.datasets)} 上的对比结果",
            deps=["WP1_小论文方法复现"],
            effort="medium" if e1.estimated_effort == "medium" else e1.estimated_effort,
        )
    if len(experiments) >= 2:
        e2 = experiments[1]
        third_wp = _make_work_package(
            wp_id="WP3",
            title=f"扩展实验: {e2.title}",
            goal=e2.description,
            deliverable=f"工程化产物 / 部署脚本 / 性能评估表",
            deps=["WP2"],
            effort="medium",
        )

    outline = suggest_thesis_outline(covered, missing)

    return ExtensionPlan(
        paper_id=paper_id or card.paper_id,
        project_id=project_id or card.project_id,
        covered_chapters=list(covered),
        missing_chapters=missing,
        gap_analysis=gap,
        extension_experiments=experiments,
        second_work_package=second_wp,
        third_work_package=third_wp,
        reuse_risks=[],  # 由 detect_repeat_risks 填充
        thesis_outline=outline,
    )


__all__ = [
    "build_extension_plan",
]

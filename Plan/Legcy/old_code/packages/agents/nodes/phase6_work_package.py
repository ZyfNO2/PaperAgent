"""Phase 06: 工作包定稿 + 实验矩阵 + 论文目录映射。

MVP 设计：
- 优先按 RiskEvaluation.decision 选最终题目（继续 / 收缩 / 转向）
- 按 Phase 02 的 work_package_drafts 拉 2 个 WP 雏形，定稿为 WorkPackageFinal
- 每个 WP 强制绑 1 主实验 + ≥1 补充实验
- 五章式目录映射用纯模板 + ledger 数据填字段
- max_writing_risk 启发式从 risk_score 推
- allow_proceed_to_phase07: rating != D
"""

from __future__ import annotations

from packages.domain import (
    ChapterAnchor,
    EvidenceLedger,
    Experiment,
    ExperimentMatrix,
    ExperimentType,
    PivotCandidate,
    ProjectIntake,
    RiskEvaluation,
    ThesisOutlineChapter,
    TopicSpec,
    WorkPackageDraft,
    WorkPackageFinal,
    WorkPackageKind,
    WorkPackagePlan,
)


# ---------------- 选择最终题目 ---------------- #


def _pick_final_topic(
    intake: ProjectIntake,
    spec: TopicSpec,
    risk_ev: RiskEvaluation,
) -> tuple[str, bool, str, str | None]:
    """返回 (final_topic, from_pivot, rationale, chosen_pivot_id)。"""

    decision = risk_ev.decision
    if decision == "继续":
        return (
            spec.normalized_topic or intake.raw_topic,
            False,
            f"风险评级 {risk_ev.risk_score.overall_rating}，决策继续当前题目",
            None,
        )
    # 收缩 / 转向：选 pivot 列表里的第一个
    if risk_ev.pivot_candidates:
        p = risk_ev.pivot_candidates[0]
        from_pivot = True
        rationale = f"决策 {decision} → 采用 pivot {p.pivot_id}: {p.rationale}"
        return p.new_topic, from_pivot, rationale, p.pivot_id
    # 没 pivot 但决策是收缩 / 转向：fallback 用原题 + 强提示
    return (
        spec.normalized_topic or intake.raw_topic,
        False,
        f"决策 {decision} 但无 Pivot 候选；保持原题，必须先补证据",
        None,
    )


# ---------------- 构造实验 ---------------- #


def _main_experiment(wp: WorkPackageDraft, ledger: EvidenceLedger) -> Experiment:
    """主实验：来自 WP draft + ledger 中绑定的 evidence。"""

    return Experiment(
        experiment_id=f"{wp.wp_id}-MAIN",
        type="主实验",
        purpose=f"回答：{wp.research_question}",
        data_source=wp.data_source or "（需补）",
        baseline_or_control=wp.method_approach or "（需补）",
        metrics=[m.name for m in ledger.metrics[:1]] or ["（需补）"],
        expected_artifact="主结果表",
        wp_binding=wp.wp_id,  # type: ignore[arg-type]
    )


def _supporting_experiments(
    wp: WorkPackageDraft, ledger: EvidenceLedger
) -> list[Experiment]:
    """补充实验：消融 / 对比 / 参数 / 案例。"""

    out: list[Experiment] = []
    # 1) 消融实验
    out.append(
        Experiment(
            experiment_id=f"{wp.wp_id}-ABL",
            type="消融实验",
            purpose="逐模块 remove/keep 验证各组件贡献",
            data_source=wp.data_source,
            baseline_or_control="完整模型",
            metrics=[m.name for m in ledger.metrics[:2]] or ["（需补）"],
            expected_artifact="消融表",
            wp_binding=wp.wp_id,  # type: ignore[arg-type]
        )
    )
    # 2) 对比实验
    if ledger.baselines:
        out.append(
            Experiment(
                experiment_id=f"{wp.wp_id}-CMP",
                type="对比实验",
                purpose="与已有 baseline 做横向对比",
                data_source=wp.data_source,
                baseline_or_control=", ".join(b.name for b in ledger.baselines[:3]),
                metrics=[m.name for m in ledger.metrics[:2]] or ["（需补）"],
                expected_artifact="对比表",
                wp_binding=wp.wp_id,  # type: ignore[arg-type]
            )
        )
    # 3) 参数实验（只要不是证据已经非常贫瘠）
    if len(ledger.datasets) >= 1:
        out.append(
            Experiment(
                experiment_id=f"{wp.wp_id}-PAR",
                type="参数实验",
                purpose="关键超参数 / 阈值的稳定性",
                data_source=wp.data_source,
                baseline_or_control="默认超参数",
                metrics=[m.name for m in ledger.metrics[:1]] or ["（需补）"],
                expected_artifact="参数曲线 / 热力图",
                wp_binding=wp.wp_id,  # type: ignore[arg-type]
            )
        )
    return out


# ---------------- 工作包定稿 ---------------- #


def _kind_for(wp_index: int) -> WorkPackageKind:
    # WP1 → 证据链构建型; WP2 → 风险评分型 (与文档 §4 推荐一致)
    return "证据链构建型" if wp_index == 0 else "风险评分型"


def _chapter_for(wp_index: int) -> ChapterAnchor:
    return "第三章" if wp_index == 0 else "第四章"


def _sections_for(wp_id: str) -> list[str]:
    """工作包占据的论文小节。"""

    if wp_id == "WP1":
        return ["3.1 问题定义", "3.2 总体框架", "3.3 核心模块", "3.4 实验结果", "3.5 本章小结"]
    return ["4.1 问题定义", "4.2 总体框架", "4.3 核心模块", "4.4 实验结果", "4.5 本章小结"]


def _finalize_wp(
    wp: WorkPackageDraft, index: int, ledger: EvidenceLedger
) -> WorkPackageFinal:
    main = _main_experiment(wp, ledger)
    sup = _supporting_experiments(wp, ledger)
    return WorkPackageFinal(
        wp_id=wp.wp_id,  # type: ignore[arg-type]
        kind=_kind_for(index),
        chapter=_chapter_for(index),
        title=wp.title,
        research_question=wp.research_question,
        method_approach=wp.method_approach,
        data_source=wp.data_source,
        baseline_or_control=wp.method_approach,  # MVP: 与 method 同源
        metrics=[m.name for m in ledger.metrics] or ["（需补）"],
        main_experiment=main,
        supporting_experiments=sup,
        chapter_sections=_sections_for(wp.wp_id),
        innovation_binding=(
            f"{wp.title} 的方法改进 → "
            f"绑定 {main.experiment_id}({main.type}) + "
            f"{', '.join(e.experiment_id for e in sup)}"
        ),
    )


# ---------------- 五章式目录 ---------------- #


def _build_thesis_outline(
    spec: TopicSpec, ledger: EvidenceLedger, wps: list[WorkPackageFinal]
) -> list[ThesisOutlineChapter]:
    chapter_titles = {
        "第一章": "绪论",
        "第二章": "相关基础",
        "第三章": wps[0].title if len(wps) >= 1 else "工作包一",
        "第四章": (wps[1].title if len(wps) >= 2 else "工作包二"),
        "第五章": "总结与展望",
    }
    content = {
        "第一章": (
            "选题背景与痛点、本文研究内容、"
            f"组织结构。铺垫原始题目 {spec.raw_topic} 的研究价值。"
        ),
        "第二章": (
            "LangGraph 状态机、RAG、混合检索、结构化输出、风险评估指标，"
            "以及与本文相关的核心算法（"
            f"{', '.join(spec.method_family[:3]) or '相关方法'}）。"
        ),
        "第三章": (
            f"{wps[0].title}：研究问题、方法、实验、对比、消融、案例、章节小结"
            if wps else "（待补）"
        ),
        "第四章": (
            f"{wps[1].title}：研究问题、方法、实验、对比、消融、案例、章节小结"
            if len(wps) >= 2 else "（待补）"
        ),
        "第五章": (
            "总结本文研究内容、贡献边界、局限与未来 3-4 个方向"
        ),
    }
    figs = {
        "第一章": ["图 1-1 选题流程总览", "图 1-2 本文组织结构"],
        "第二章": ["图 2-1 LangGraph 状态机", "图 2-2 混合检索流程"],
        "第三章": (
            ["图 3-1 方法框架", "表 3-1 主结果表", "表 3-2 消融表"]
            if wps else ["（待补）"]
        ),
        "第四章": (
            ["图 4-1 方法框架", "表 4-1 主结果表", "表 4-2 消融表"]
            if len(wps) >= 2 else ["（待补）"]
        ),
        "第五章": ["图 5-1 工作量与风险对应关系"],
    }
    data_sources = {
        "第一章": ["Phase 01 ProjectIntake", "Phase 02 TopicSpec"],
        "第二章": ["Phase 02 TopicSpec.method_family", "综述论文候选"],
        "第三章": (
            [f"Phase 04 PaperEvidence × {len(ledger.papers)}",
             f"Phase 04 BaselineCandidate × {len(ledger.baselines)}"]
            if wps else ["（待补）"]
        ),
        "第四章": (
            [f"Phase 04 DatasetCandidate × {len(ledger.datasets)}",
             f"Phase 05 RiskEvaluation"]
            if len(wps) >= 2 else ["（待补）"]
        ),
        "第五章": ["Phase 06 WorkPackagePlan"],
    }
    out: list[ThesisOutlineChapter] = []
    for ch in ("第一章", "第二章", "第三章", "第四章", "第五章"):
        out.append(
            ThesisOutlineChapter(
                chapter=ch,  # type: ignore[arg-type]
                title=chapter_titles[ch],
                content_summary=content[ch],
                data_sources=data_sources[ch],
                figures_needed=figs[ch],
            )
        )
    return out


# ---------------- 公开入口 ---------------- #


def build_work_package_plan(
    intake: ProjectIntake,
    spec: TopicSpec,
    risk_ev: RiskEvaluation,
    ledger: EvidenceLedger,
) -> WorkPackagePlan:
    final_topic, from_pivot, rationale, _ = _pick_final_topic(intake, spec, risk_ev)

    # WP 数量：heuristic 默认给 2 个；只有 1 个时给 §6 提示
    wps_in = spec.work_package_drafts
    if len(wps_in) == 0:
        wps_in = [
            WorkPackageDraft(
                wp_id="WP1", title="证据链构建（占位）",
                research_question="待补", method_approach="待补",
                data_source="待补", experiment_plan="待补", chapter="第三章",
            ),
            WorkPackageDraft(
                wp_id="WP2", title="风险与工作包生成（占位）",
                research_question="待补", method_approach="待补",
                data_source="待补", experiment_plan="待补", chapter="第四章",
            ),
        ]
    elif len(wps_in) == 1:
        wps_in = list(wps_in) + [
            WorkPackageDraft(
                wp_id="WP2", title=wps_in[0].title + "（扩展）",
                research_question="（第二个工作包需补）",
                method_approach="（待补）",
                data_source="（待补）",
                experiment_plan="（待补）",
                chapter="第四章",
            )
        ]

    final_wps = [
        _finalize_wp(wp, idx, ledger) for idx, wp in enumerate(wps_in[:2])
    ]
    matrices = [
        ExperimentMatrix(
            wp_id=wp.wp_id,  # type: ignore[arg-type]
            main_experiment=wp.main_experiment,
            supporting_experiments=wp.supporting_experiments,
        )
        for wp in final_wps
    ]
    outline = _build_thesis_outline(spec, ledger, final_wps)

    # max_writing_risk 启发式
    if risk_ev.risk_score.overall_rating == "D":
        max_risk = "Pivot 风险大，工作包不成熟，必须先回到 Phase 04 补证据"
    elif from_pivot:
        max_risk = f"已采用 pivot，但 pivot 后题目的 baseline 复现周期可能与时间红线冲突"
    elif len(ledger.datasets) < 2:
        max_risk = "数据集不足，第三章/第四章实验结论可能不稳健"
    elif any(b.reproduce_difficulty == "高" for b in ledger.baselines):
        max_risk = "含高复现难度 baseline，时间红线紧"
    else:
        max_risk = "中等：所有维度评分 ≥ B，写作风险可控"

    allow = risk_ev.risk_score.overall_rating != "D"

    return WorkPackagePlan(
        project_id="",
        risk_evaluation_id="",
        goal_level=intake.goal_level,
        final_topic=final_topic,
        final_topic_from_pivot=from_pivot,
        final_topic_rationale=rationale,
        work_packages=final_wps,
        experiment_matrices=matrices,
        thesis_outline=outline,
        max_writing_risk=max_risk,
        allow_proceed_to_phase07=allow,
    )


def allow_proceed_to_phase07(plan: WorkPackagePlan) -> tuple[bool, str]:
    if not plan.allow_proceed_to_phase07:
        return False, plan.max_writing_risk
    if not plan.work_packages:
        return False, "无工作包"
    for wp in plan.work_packages:
        if not wp.main_experiment or not wp.supporting_experiments:
            return False, f"{wp.wp_id} 缺主实验或补充实验"
    if not plan.thesis_outline or len(plan.thesis_outline) < 5:
        return False, "五章式目录映射缺失"
    return True, "ok"

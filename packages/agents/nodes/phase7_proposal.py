"""Phase 07: 开题报告骨架生成 + 委员会审查。

MVP 设计：
- 10 节开题报告骨架：每节 content 由 Phase 02-06 已有字段拼出
- 创新点：从 WorkPackagePlan.innovation_binding 解析
- 研究现状：从 EvidenceLedger.papers 按 EvidenceScore 排序，挑前 N 篇
- 委员会审查：7 维度 × 规则 verdict（基于 risk 评级 + 字段数）
- 追问清单：固定 6 个开题常见问题
- 修改清单：基于 reviews 中"需修改"维度自动生成
"""

from __future__ import annotations

from packages.domain import (
    CommitteeDiscussionItem,
    CommitteeQuestion,
    CommitteeReview,
    CommitteeReviewItem,
    EvidenceLedger,
    InnovationPoint,
    PROPOSAL_SECTIONS,
    ProjectIntake,
    ProposalDraft,
    ProposalSection,
    ResearchStatusRow,
    RiskEvaluation,
    RiskScore,
    SectionKey,
    WorkPackagePlan,
)
from packages.llm import chat_json, LLMUnavailable


# ---------------- 10 节开题报告 ---------------- #


def _section_background(intake: ProjectIntake, spec_topic: str) -> ProposalSection:
    content = (
        f"本课题面向 {intake.major or '本专业'} 的毕业研究需求，"
        f"聚焦于 {spec_topic}。该题目源于 {intake.goal_level} 目标，"
        f"在毕业论文集的方法论指导下，提出可工程化、可复现的解决方案。"
    )
    return ProposalSection(
        key="研究背景与意义",
        title="1. 研究背景与意义",
        content=content,
        sources=["Phase 01 ProjectIntake", "Phase 02 TopicSpec"],
    )


def _section_status(ledger: EvidenceLedger) -> ProposalSection:
    rows = sorted(ledger.papers, key=lambda p: p.evidence_score, reverse=True)[:5]
    content_lines = [
        f"基于 Phase 04 证据账本，按 evidence_score 排序取前 {len(rows)} 篇代表性论文：",
    ]
    for i, p in enumerate(rows, 1):
        content_lines.append(
            f"  {i}. [{p.year or '?'}] {p.title[:60]} (score={p.evidence_score})"
        )
    if ledger.surveys:
        content_lines.append(
            f"  + {len(ledger.surveys)} 篇综述已纳入国内外研究现状骨架"
        )
    return ProposalSection(
        key="国内外研究现状",
        title="2. 国内外研究现状",
        content="\n".join(content_lines),
        sources=[f"Phase 04 PaperEvidence × {len(ledger.papers)}", "Surveys"],
    )


def _section_problem(plan: WorkPackagePlan) -> ProposalSection:
    problems = [wp.research_question for wp in plan.work_packages]
    content = (
        f"本文围绕以下研究问题展开：\n"
        + "\n".join(f"  ({i+1}) {q}" for i, q in enumerate(problems))
    )
    return ProposalSection(
        key="研究问题与目标",
        title="3. 研究问题与目标",
        content=content,
        sources=[f"Phase 06 WorkPackage × {len(plan.work_packages)}"],
    )


def _section_tech(plan: WorkPackagePlan) -> ProposalSection:
    lines = ["本文采用如下技术路线："]
    for wp in plan.work_packages:
        lines.append(
            f"  [{wp.wp_id} / {wp.chapter}] {wp.kind}: {wp.method_approach}"
        )
    return ProposalSection(
        key="研究内容与技术路线",
        title="4. 研究内容与技术路线",
        content="\n".join(lines),
        sources=["Phase 06 WorkPackageFinal"],
    )


def _section_key(plan: WorkPackagePlan, ledger: EvidenceLedger) -> ProposalSection:
    lines = [
        "拟解决的关键问题：",
        f"  - 题目边界：{plan.final_topic}",
        f"  - 数据可得性：{len(ledger.datasets)} 个数据集候选",
        f"  - baseline 复现：{len(ledger.baselines)} 个候选"
            + (" (含高复现难度)" if any(b.reproduce_difficulty == '高' for b in ledger.baselines) else ""),
    ]
    return ProposalSection(
        key="拟解决关键问题",
        title="5. 拟解决关键问题",
        content="\n".join(lines),
        sources=["Phase 04 EvidenceLedger"],
    )


def _section_innovation(plan: WorkPackagePlan) -> ProposalSection:
    lines = ["预期创新点（绑定问题 + 方法 + 实验）："]
    for wp in plan.work_packages:
        lines.append(f"  - [{wp.wp_id}] {wp.innovation_binding}")
    return ProposalSection(
        key="预期创新点",
        title="6. 预期创新点",
        content="\n".join(lines),
        sources=["Phase 06 WorkPackageFinal.innovation_binding"],
    )


def _section_experiment(plan: WorkPackagePlan, ledger: EvidenceLedger) -> ProposalSection:
    lines = ["实验方案："]
    for mat in plan.experiment_matrices:
        lines.append(f"  [{mat.wp_id}] 主实验 + {len(mat.supporting_experiments)} 补充")
    lines.append(f"\n评价指标：{[m.name for m in ledger.metrics] or ['（待补）']}")
    return ProposalSection(
        key="实验方案与评价指标",
        title="7. 实验方案与评价指标",
        content="\n".join(lines),
        sources=["Phase 04 MetricSet", "Phase 06 ExperimentMatrix"],
    )


def _section_feasibility(plan: WorkPackagePlan, intake: ProjectIntake, ledger: EvidenceLedger) -> ProposalSection:
    inherit = len(intake.inherited_resources)
    student = intake.student_resources
    content = (
        f"数据：{len(ledger.datasets)} 个公开数据集候选；"
        f"baseline：{len(ledger.baselines)} 个候选；"
        f"指标：{len(ledger.metrics)} 套；"
        f"继承资源：{inherit} 项；"
        f"学生算力 {student.compute_resource}，每周 {student.weekly_hours}h。"
        f"预计第一张主结果表时间 {intake.first_result_deadline or '待定'}。"
    )
    return ProposalSection(
        key="可行性分析",
        title="8. 可行性分析",
        content=content,
        sources=["Phase 01 ProjectIntake", "Phase 04 EvidenceLedger"],
    )


def _section_timeline(intake: ProjectIntake) -> ProposalSection:
    fdr = intake.first_result_deadline or "TBD"
    thesis = intake.thesis_deadline or "TBD"
    lines = [
        "  阶段 1 (Phase 01-02)：建档 + 题目拆解",
        "  阶段 2 (Phase 03-04)：检索 + 证据账本",
        "  阶段 3 (Phase 05-06)：风险评分 + 工作包定稿",
        f"  阶段 4 (Phase 07-08)：开题报告 + 材料导出",
        f"  阶段 5：实验与论文写作（截止 {fdr} 首张结果表 / {thesis} 终稿）",
    ]
    return ProposalSection(
        key="进度计划",
        title="9. 进度计划",
        content="\n".join(lines),
        sources=["Phase 01 TimeRedline"],
    )


def _section_risk(risk_ev: RiskEvaluation, plan: WorkPackagePlan) -> ProposalSection:
    lines = [
        f"最高风险维度：{risk_ev.risk_score.max_risk_dimension}",
        f"综合评级：{risk_ev.risk_score.overall_rating} ({risk_ev.risk_score.overall_score:.1f})",
        f"决策：{risk_ev.decision}",
        f"风险预案：{plan.max_writing_risk}",
    ]
    if risk_ev.pivot_candidates:
        lines.append(
            f"已准备 {len(risk_ev.pivot_candidates)} 个 Pivot 候选："
            + "; ".join(p.new_topic[:30] for p in risk_ev.pivot_candidates)
        )
    return ProposalSection(
        key="风险预案",
        title="10. 风险预案",
        content="\n".join(lines),
        sources=["Phase 05 RiskEvaluation", "Phase 06 max_writing_risk"],
    )


# ---------------- 创新点 + 研究现状 ---------------- #


def _build_innovations(plan: WorkPackagePlan, ledger: EvidenceLedger) -> list[InnovationPoint]:
    out: list[InnovationPoint] = []
    for i, wp in enumerate(plan.work_packages, 1):
        m = [m.name for m in ledger.metrics[:3]] or ["（待补）"]
        out.append(
            InnovationPoint(
                innovation_id=f"I{i:02d}",
                problem=wp.research_question,
                method=wp.method_approach,
                verification=f"主实验 {wp.main_experiment.experiment_id} + "
                             f"{len(wp.supporting_experiments)} 补充实验",
                metrics=m,
                risk="中",
            )
        )
    return out


def _build_research_status(ledger: EvidenceLedger) -> list[ResearchStatusRow]:
    """按 method_family 派生研究现状分类。"""

    method_families = set()
    for p in ledger.papers:
        for m in p.method:
            method_families.add(m)
    families = list(method_families)[:4] or ["深度学习", "图神经网络", "推荐系统"]
    rows: list[ResearchStatusRow] = []
    for f in families:
        rows.append(
            ResearchStatusRow(
                category=f,
                representative_work=f"代表方法见 Phase 04 papers 列表（共 {len(ledger.papers)} 篇）",
                gap="在 [具体场景] 上尚无完整 baseline 对比 + 消融研究",
                relation=f"本文 {f} 模块在 {f} 框架内做局部改进",
            )
        )
    return rows


def _build_timeline(intake: ProjectIntake) -> list[dict]:
    fdr = intake.first_result_deadline or "TBD"
    thesis = intake.thesis_deadline or "TBD"
    return [
        {"phase": "Phase 01-02", "deliverable": "建档 + TopicSpec", "due": intake.proposal_deadline or "TBD"},
        {"phase": "Phase 03-04", "deliverable": "检索计划 + 证据账本", "due": "TBD"},
        {"phase": "Phase 05-06", "deliverable": "风险评分 + 工作包定稿", "due": "TBD"},
        {"phase": "Phase 07-08", "deliverable": "开题报告 + 材料导出", "due": fdr},
        {"phase": "实验 + 论文", "deliverable": "主结果表 → 终稿", "due": thesis},
    ]


def _build_risk_plan(risk_ev: RiskEvaluation, plan: WorkPackagePlan) -> list[str]:
    out: list[str] = []
    out.append(f"如 baseline 复现失败 → 切换至 risk_plan 中的低复现难度候选")
    out.append(f"如数据集不到位 → 用 {plan.work_packages[0].data_source} 公开数据子集替代")
    if risk_ev.pivot_candidates:
        out.append(
            "如题目风险长期为 C/D → 启用 pivot 候选："
            + "; ".join(p.new_topic[:30] for p in risk_ev.pivot_candidates[:2])
        )
    out.append(f"最大写作风险: {plan.max_writing_risk}")
    return out


# ---------------- 委员会审查 ---------------- #


def _review_one(
    dimension: str,
    issues: list[str],
    suggestions: list[str],
    ledger: EvidenceLedger,
    risk: RiskScore,
) -> CommitteeReviewItem:
    """根据 issues 数量给 verdict。"""

    n = len(issues)
    if n == 0:
        verdict = "通过"
    elif n <= 2 and risk.overall_rating in ("A", "B"):
        verdict = "有条件通过"
    elif n <= 4:
        verdict = "需修改"
    else:
        verdict = "不通过"
    return CommitteeReviewItem(
        dimension=dimension, verdict=verdict, issues=issues, suggestions=suggestions
    )


def _build_reviews(
    ledger: EvidenceLedger, risk_ev: RiskEvaluation, plan: WorkPackagePlan
) -> list[CommitteeReviewItem]:
    reviews: list[CommitteeReviewItem] = []
    risk_score = risk_ev.risk_score

    # 1) 题目边界
    title_issues: list[str] = []
    if plan.final_topic_from_pivot:
        title_issues.append("题目经过 pivot 决策，需在开题时明确原始题目与新题目的关系")
    if any(t in plan.final_topic for t in ("大模型", "通用", "全自动", "智能")):
        title_issues.append("题目含高风险词，建议进一步限定场景")
    reviews.append(_review_one(
        "题目边界", title_issues,
        ["明确题目边界与可验证承诺", "在 §1.1 强调 1-2 个可衡量指标"],
        ledger, risk_score,
    ))

    # 2) 研究现状
    status_issues: list[str] = []
    if len(ledger.papers) < 5:
        status_issues.append(f"论文仅 {len(ledger.papers)} 篇，建议补检索")
    if not ledger.surveys:
        status_issues.append("无综述，需自建分类体系")
    reviews.append(_review_one(
        "研究现状", status_issues,
        ["按方法类别组织论文", "对每类给出'不足'与'本文切入点'"],
        ledger, risk_score,
    ))

    # 3) 创新点
    innov_issues: list[str] = []
    for wp in plan.work_packages:
        if not wp.innovation_binding:
            innov_issues.append(f"{wp.wp_id} 创新点未绑定实验")
    reviews.append(_review_one(
        "创新点", innov_issues,
        ["按 §2.2 模板：针对 X 问题 / 设计 Y / 通过 Z 验证"],
        ledger, risk_score,
    ))

    # 4) 数据与 baseline
    data_issues: list[str] = []
    if len(ledger.datasets) < 2:
        data_issues.append(f"数据集仅 {len(ledger.datasets)} 个")
    if len(ledger.baselines) < 2:
        data_issues.append(f"baseline 仅 {len(ledger.baselines)} 个")
    if not ledger.metrics:
        data_issues.append("无评价指标")
    reviews.append(_review_one(
        "数据与 baseline", data_issues,
        ["至少 2 数据集 + 2 baseline", "每个 baseline 注明复现难度"],
        ledger, risk_score,
    ))

    # 5) 实验方案
    exp_issues: list[str] = []
    for wp in plan.work_packages:
        if not wp.main_experiment or not wp.supporting_experiments:
            exp_issues.append(f"{wp.wp_id} 缺主实验或补充实验")
    reviews.append(_review_one(
        "实验方案", exp_issues,
        ["每个 WP 必含 1 主 + ≥1 补充", "消融/对比/参数三类至少各 1"],
        ledger, risk_score,
    ))

    # 6) 工作量
    wl_issues: list[str] = []
    if len(plan.work_packages) < 2:
        wl_issues.append("只有 1 个工作包，第三章/第四章支撑不足")
    reviews.append(_review_one(
        "工作量", wl_issues,
        ["保持 2 个工作包，第三章 + 第四章各 1"],
        ledger, risk_score,
    ))

    # 7) 风险预案
    rp_issues: list[str] = []
    if not risk_ev.pivot_candidates and risk_score.overall_rating in ("C", "D"):
        rp_issues.append("风险评级 C/D 但无 pivot 候选")
    if "高" in plan.max_writing_risk:
        rp_issues.append("max_writing_risk 含'高'，需明确 fallback 路径")
    reviews.append(_review_one(
        "风险预案", rp_issues,
        ["明确 baseline 失败 / 数据不到位 / 时间红线冲突的 fallback"],
        ledger, risk_score,
    ))

    return reviews


def _build_questions(
    risk_ev: RiskEvaluation, plan: WorkPackagePlan, ledger: EvidenceLedger
) -> list[CommitteeQuestion]:
    return [
        CommitteeQuestion(
            question="这个题目为什么值得做？",
            suggested_answer=(
                f"题目的 {risk_ev.risk_score.overall_rating} 评级 + "
                f"{len(ledger.papers)} 篇相关论文 + {len(ledger.baselines)} 个 baseline"
                " 共同支撑其研究价值"
            ),
            evidence_source="Phase 04 EvidenceLedger + Phase 05 RiskEvaluation",
        ),
        CommitteeQuestion(
            question="现有方法有什么不足？",
            suggested_answer=(
                f"在 {plan.work_packages[0].data_source} 任务上，"
                "现有方法缺乏端到端 pipeline 整合与可复现实验对比"
            ),
            evidence_source="Phase 04 surveys / papers 分类",
        ),
        CommitteeQuestion(
            question="你的创新点在哪里？",
            suggested_answer=(
                f"见开题报告 §6 创新点：{len(plan.work_packages)} 个 WP 各对应 1 个创新点"
            ),
            evidence_source="Phase 06 innovation_binding",
        ),
        CommitteeQuestion(
            question="你的数据和 baseline 从哪里来？",
            suggested_answer=(
                f"数据：{len(ledger.datasets)} 个候选；baseline：{len(ledger.baselines)} 个候选；"
                "来源详见 Phase 04 EvidenceLedger.source 字段"
            ),
            evidence_source="Phase 04 EvidenceLedger",
        ),
        CommitteeQuestion(
            question="实验怎么证明有效？",
            suggested_answer=(
                f"每个 WP 配 1 主 + ≥{1} 补充实验（消融/对比/参数），"
                f"评价指标 {[m.name for m in ledger.metrics[:3]] or ['（待补）']}"
            ),
            evidence_source="Phase 06 ExperimentMatrix + Phase 04 MetricSet",
        ),
        CommitteeQuestion(
            question="做不出来怎么办？",
            suggested_answer=(
                f"风险预案 §10：{len(risk_ev.pivot_candidates)} 个 pivot 候选 + "
                "baseline 失败时切换低复现难度候选"
            ),
            evidence_source="Phase 05 PivotCandidate + Phase 07 §10",
        ),
    ]


def _build_revision_checklist(
    reviews: list[CommitteeReviewItem]
) -> list[dict]:
    out: list[dict] = []
    for r in reviews:
        if r.verdict in ("需修改", "不通过"):
            for issue in r.issues:
                out.append({
                    "priority": "P0" if r.verdict == "不通过" else "P1",
                    "item": f"{r.dimension}: {issue}",
                    "reason": f"verdict={r.verdict}",
                    "deadline": "下次开题前",
                })
    return out


# ---------------- 公开入口 ---------------- #


def build_proposal_draft(
    intake: ProjectIntake,
    spec_topic: str,
    ledger: EvidenceLedger,
    plan: WorkPackagePlan,
    risk_ev: RiskEvaluation,
) -> ProposalDraft:
    sections: list[ProposalSection] = [
        _section_background(intake, spec_topic),
        _section_status(ledger),
        _section_problem(plan),
        _section_tech(plan),
        _section_key(plan, ledger),
        _section_innovation(plan),
        _section_experiment(plan, ledger),
        _section_feasibility(plan, intake, ledger),
        _section_timeline(intake),
        _section_risk(risk_ev, plan),
    ]
    return ProposalDraft(
        project_id="",
        work_package_plan_id="",
        goal_level=intake.goal_level,
        final_topic=plan.final_topic,
        proposal_sections=sections,
        research_status=_build_research_status(ledger),
        innovation_points=_build_innovations(plan, ledger),
        timeline=_build_timeline(intake),
        risk_plan=_build_risk_plan(risk_ev, plan),
    )


def build_committee_review(
    ledger: EvidenceLedger, risk_ev: RiskEvaluation, plan: WorkPackagePlan
) -> CommitteeReview:
    reviews = _build_reviews(ledger, risk_ev, plan)
    questions = _build_questions(risk_ev, plan, ledger)
    checklist = _build_revision_checklist(reviews)
    discussion = _build_committee_discussion_llm(risk_ev, plan, ledger)

    # 总体 verdict
    verdicts = [r.verdict for r in reviews]
    if "不通过" in verdicts:
        overall = "不通过"
    elif "需修改" in verdicts:
        overall = "需修改"
    elif "有条件通过" in verdicts:
        overall = "有条件通过"
    else:
        overall = "通过"

    # 提案成熟度
    rating = risk_ev.risk_score.overall_rating
    # proposal_maturity 比 risk 评级松一点（B -> B, C -> C, D -> C）
    if rating == "A":
        maturity = "A"
    elif rating == "B":
        maturity = "B"
    elif rating == "C":
        maturity = "C"
    else:  # D
        maturity = "C"

    allow = overall in ("通过", "有条件通过") and rating != "D"

    return CommitteeReview(
        project_id="",
        proposal_draft_id="",
        reviews=reviews,
        questions=questions,
        revision_checklist=checklist,
        discussion=discussion,
        overall_verdict=overall,  # type: ignore[arg-type]
        proposal_maturity=maturity,  # type: ignore[arg-type]
        allow_proceed_to_phase08=allow,
    )


def allow_proceed_to_phase08(review: CommitteeReview) -> tuple[bool, str]:
    if not review.allow_proceed_to_phase08:
        return False, f"verdict={review.overall_verdict}, maturity={review.proposal_maturity}"
    if len(review.reviews) < 7:
        return False, f"审查维度 < 7 (当前 {len(review.reviews)})"
    return True, "ok"


# ----------------- 3 角色 LLM 对话 (开题版) ----------------- #

_DISCUSSION_PROFILES: list[dict] = [
    {
        "role": "supporter",
        "stance": "支持",
        "focus": ["工作包可行性", "Baseline 成熟度", "数据可获得"],
        "system": (
            "你是开题委员会的'支持型'教授. 语气务实, 不浮夸. "
            "请站在'这个题目硕士生能毕业'的角度, 给出 100-180 字中文评语, "
            "指出 1-2 个最有把握的支撑点 (如: baseline 有开源 / 数据公开 / 工作包有先例)."
        ),
    },
    {
        "role": "skeptic",
        "stance": "质疑",
        "focus": ["评价指标", "创新性", "工作包是否串行"],
        "system": (
            "你是开题委员会的'质疑型'教授. 语气直接, 不挖苦. "
            "请站在'这个题目风险在哪里'的角度, 给出 100-180 字中文评语, "
            "指出 1-2 个最不放心的环节 (如: 创新点难以验证 / 工作包相互依赖). "
            "问题要具体, 不要泛泛而谈."
        ),
    },
    {
        "role": "pragmatist",
        "stance": "折中",
        "focus": ["工程实现", "算力", "毕业周期"],
        "system": (
            "你是开题委员会的'工程型'教授. 语气平衡, 不空想. "
            "请站在'这个方案落地要付出多少'的角度, 给出 100-180 字中文评语, "
            "指出 1-2 个工程 / 时间 / 算力上的现实约束, 给出可操作的调整建议."
        ),
    },
]


def _build_committee_discussion_llm(
    risk_ev: RiskEvaluation, plan: WorkPackagePlan, ledger: EvidenceLedger
) -> list[CommitteeDiscussionItem]:
    """3 角色各 1 段评语, LLM 失败时回退规则模板.

    评语只用于前端展示对话气泡; 不进入 reviews 维度评分.
    """
    context = (
        f"题目: {plan.final_topic}\n"
        f"目标档位: {plan.goal_level}\n"
        f"工作包数: {len(plan.work_packages)} (thesis_outline={len(plan.thesis_outline)} 章)\n"
        f"风险评级: {risk_ev.risk_score.overall_rating} ({risk_ev.risk_score.overall_score})\n"
        f"决策: {risk_ev.decision}\n"
        f"证据: papers={len(ledger.papers)} datasets={len(ledger.datasets)} "
        f"baselines={len(ledger.baselines)}\n"
    )
    out: list[CommitteeDiscussionItem] = []
    for prof in _DISCUSSION_PROFILES:
        try:
            raw = chat_json(
                [
                    {"role": "system", "content": prof["system"]},
                    {"role": "user", "content": (
                        context + "\n请直接输出 JSON: "
                        "{\"comment\": \"你的评语 (100-180 字)\"}"
                    )},
                ],
                temperature=0.5,
                max_tokens=600,
            )
            comment = str(raw.get("comment", "")).strip()
            if len(comment) < 20:
                raise ValueError("comment too short")
            out.append(CommitteeDiscussionItem(
                role=prof["role"],  # type: ignore[arg-type]
                stance=prof["stance"],
                comment=comment,
                focus=list(prof["focus"]),
            ))
        except (LLMUnavailable, ValueError, KeyError):
            out.append(CommitteeDiscussionItem(
                role=prof["role"],  # type: ignore[arg-type]
                stance=prof["stance"],
                comment=_fallback_comment(prof["role"], risk_ev, plan, ledger),
                focus=list(prof["focus"]),
            ))
    return out


def _fallback_comment(
    role: str, risk_ev: RiskEvaluation, plan: WorkPackagePlan, ledger: EvidenceLedger
) -> str:
    """LLM 不可用时的规则评语 (开题版语气)."""
    rating = risk_ev.risk_score.overall_rating
    n_papers = len(ledger.papers)
    n_wp = len(plan.work_packages)
    if role == "supporter":
        if n_papers >= 5:
            return (
                f"支持方面: 检索到 {n_papers} 篇相关论文, 其中 {n_wp} 个工作包有公开 baseline 和数据集可参考, "
                f"整体风险评级 {rating}, 属于硕士可毕业范围. 建议在开题报告 '研究现状' 一节里重点展示 2-3 篇最相关的."
            )
        return "支持方面: 工作包设计有梯度, 可以分阶段交付. 建议补充 1-2 篇目标领域综述."
    if role == "skeptic":
        if rating in ("C", "D"):
            return (
                f"质疑方面: 风险评级 {rating}, 创新点需要进一步具体化, "
                f"否则答辩时容易被问 '和 X 论文相比具体改了什么'. 建议在 '研究内容' 写 1-2 句可证伪的假设."
            )
        return (
            "质疑方面: 两个工作包之间的边界要明确, "
            "如果 WP1 数据 / baseline 出问题, WP2 是否仍能继续? "
            "建议在 '风险预案' 写明 fallback 路径."
        )
    # pragmatist
    return (
        f"工程方面: 评估 GPU 显存 / 训练时长, "
        f"如果只有 1 张 3060, 推荐论文级 batch size 并减少对比 baseline 数量. "
        f"把 '实验方案' 的时间表按周拆, 每周 1 个可验证产物."
    )

"""8 个 async helper: 给 SSE 端点用. 接受 emit sink, 业务完成后 emit result.

每个函数签名: async def xxx_async(project_id, session, *args, emit) -> None
emit(name, detail, **meta) -> None  把事件推到 SSE queue
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.evidence_ledger_repository import EvidenceLedgerRepository
from app.db.repository import ProjectRepository
from app.db.risk_repository import RiskEvaluationRepository
from app.db.search_plan_repository import SearchPlanRepository
from app.db.topic_spec_repository import TopicSpecRepository
from app.db.work_package_repository import WorkPackagePlanRepository
from packages.agents.nodes.phase2_decompose import decompose
from packages.agents.nodes.phase3_search_plan import build_search_plan
from packages.agents.nodes.phase4_evidence import build_evidence_ledger
from packages.agents.nodes.phase5_risk import build_risk_evaluation
from packages.agents.nodes.phase6_work_package import build_work_package_plan
from packages.agents.nodes.phase7_proposal import (
    build_committee_review,
    build_proposal_draft,
)
from packages.agents.nodes.phase8_final_package import build_final_package
from packages.agents.nodes.phase2_decompose import allow_proceed_to_phase03
from packages.agents.nodes.phase3_search_plan import allow_proceed_to_phase04
from packages.agents.nodes.phase5_risk import allow_proceed_to_phase06
from packages.agents.nodes.phase6_work_package import allow_proceed_to_phase07
from packages.domain import ProjectIntake


# ---------- Phase 02 ----------


async def decompose_async(
    project_id: int, session: AsyncSession, prefer: str,
    emit: Callable[..., None],
) -> None:
    proj_repo = ProjectRepository(session)
    proj = await proj_repo.get_by_id(project_id)
    if proj is None:
        emit("error", f"project_id {project_id} 不存在")
        return
    intake = ProjectIntake.model_validate(proj.payload)
    spec = decompose(intake, prefer=prefer, trace_sink=emit)
    spec.project_id = str(project_id)
    spec_repo = TopicSpecRepository(session)
    row = await spec_repo.upsert(spec)
    allow, _ = allow_proceed_to_phase03(spec)
    emit("result", "题目拆解完成", meta={
        "id": row.id,
        "decomposition_rating": spec.decomposition_rating,
        "allow_proceed_to_phase03": allow,
    })


# ---------- Phase 03 ----------


async def search_plan_async(
    project_id: int, session: AsyncSession,
    emit: Callable[..., None],
) -> None:
    emit("step", "📝 抽取英文关键词 + 构建 7 层检索")
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        emit("error", f"project_id {project_id} 没有 TopicSpec")
        return
    allow_p3, _ = allow_proceed_to_phase03(spec)
    if not allow_p3:
        emit("error", "TopicSpec 评级不允许进入 Phase 03")
        return
    plan = build_search_plan(spec)
    plan.project_id = str(project_id)
    plan_repo = SearchPlanRepository(session)
    row = await plan_repo.upsert(plan)
    allow_p4, _ = allow_proceed_to_phase04(plan)
    emit("step", "评分", rating=plan.maturity_rating, layer_count=len(plan.query_layers))
    emit("result", "检索计划完成", meta={
        "id": row.id,
        "maturity_rating": plan.maturity_rating,
        "allow_proceed_to_phase04": allow_p4,
    })


# ---------- Phase 04 ----------


async def evidence_async(
    project_id: int, session: AsyncSession, prefer: str,
    emit: Callable[..., None],
) -> None:
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        emit("error", f"project_id {project_id} 没有 TopicSpec")
        return
    plan_repo = SearchPlanRepository(session)
    plan = await plan_repo.get_by_project_id(str(project_id))
    if plan is None:
        emit("error", f"project_id {project_id} 没有 SearchQueryPlan")
        return
    ledger = build_evidence_ledger(spec, plan, prefer=prefer, trace_sink=emit)
    ledger.project_id = str(project_id)
    led_repo = EvidenceLedgerRepository(session)
    row = await led_repo.upsert(ledger)
    arxiv_hits = sum(1 for p in ledger.papers if p.source == "arXiv")
    emit("result", "证据账本完成", meta={
        "id": row.id,
        "evidence_rating": ledger.evidence_rating,
        "paper_count": len(ledger.papers),
        "arxiv_papers": arxiv_hits,
        "dataset_count": len(ledger.datasets),
        "baseline_count": len(ledger.baselines),
    })


# ---------- Phase 05 ----------


async def risk_async(
    project_id: int, session: AsyncSession, prefer: str,
    emit: Callable[..., None],
) -> None:
    proj_repo = ProjectRepository(session)
    proj = await proj_repo.get_by_id(project_id)
    if proj is None:
        emit("error", f"project_id {project_id} 不存在")
        return
    intake = ProjectIntake.model_validate(proj.payload)
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        emit("error", f"project_id {project_id} 没有 TopicSpec")
        return
    plan_repo = SearchPlanRepository(session)
    plan = await plan_repo.get_by_project_id(str(project_id))
    if plan is None:
        emit("error", f"project_id {project_id} 没有 SearchQueryPlan")
        return
    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        emit("error", f"project_id {project_id} 没有 EvidenceLedger")
        return
    emit("step", "📊 六维风险评分")
    emit("step", "🤖 调 M3 生成 Pivot 候选 (LLM)", max_tokens=2000)
    import time as _t
    t0 = _t.time()
    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer=prefer)
    emit("step", "✅ Pivot 完成", duration_ms=int((_t.time() - t0) * 1000),
         overall_rating=ev.risk_score.overall_rating,
         pivot_count=len(ev.pivot_candidates))
    risk_repo = RiskEvaluationRepository(session)
    row = await risk_repo.upsert(ev)
    allow, _ = allow_proceed_to_phase06(ev)
    emit("result", "风险评估完成", meta={
        "id": row.id,
        "overall_rating": ev.risk_score.overall_rating,
        "overall_score": ev.risk_score.overall_score,
        "decision": ev.decision,
        "max_risk_dimension": ev.risk_score.max_risk_dimension,
        "pivot_count": len(ev.pivot_candidates),
        "allow_proceed_to_phase06": allow,
    })


# ---------- Phase 06 ----------


async def work_package_async(
    project_id: int, session: AsyncSession,
    emit: Callable[..., None],
) -> None:
    risk_repo = RiskEvaluationRepository(session)
    risk_ev = await risk_repo.get_by_project_id(str(project_id))
    if risk_ev is None:
        emit("error", f"project_id {project_id} 没有 RiskEvaluation")
        return
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        emit("error", f"project_id {project_id} 没有 TopicSpec")
        return
    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        emit("error", f"project_id {project_id} 没有 EvidenceLedger")
        return
    proj_repo = ProjectRepository(session)
    project = await proj_repo.get_by_id(project_id)
    if project is None:
        emit("error", f"project_id {project_id} 不存在")
        return
    intake = ProjectIntake.model_validate(project.payload)
    emit("step", "📦 定稿最终题目 + 拼装 2-3 工作包")
    plan = build_work_package_plan(intake, spec, risk_ev, ledger)
    plan.project_id = str(project_id)
    repo = WorkPackagePlanRepository(session)
    row = await repo.upsert(plan)
    allow, _ = allow_proceed_to_phase07(plan)
    n_experiments = sum(1 + len(wp.supporting_experiments) for wp in plan.work_packages)
    emit("step", "评分", wp_count=len(plan.work_packages), experiment_count=n_experiments)
    emit("result", "工作包完成", meta={
        "id": row.id,
        "final_topic": plan.final_topic,
        "from_pivot": plan.final_topic_from_pivot,
        "work_package_count": len(plan.work_packages),
        "experiment_count": n_experiments,
        "allow_proceed_to_phase07": allow,
    })


# ---------- Phase 07 proposal ----------


async def proposal_async(
    project_id: int, session: AsyncSession,
    emit: Callable[..., None],
) -> None:
    from app.db.work_package_repository import WorkPackagePlanRepository
    proj_repo = ProjectRepository(session)
    proj = await proj_repo.get_by_id(project_id)
    if proj is None:
        emit("error", f"project_id {project_id} 不存在")
        return
    intake = ProjectIntake.model_validate(proj.payload)
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        emit("error", f"project_id {project_id} 没有 TopicSpec")
        return
    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        emit("error", f"project_id {project_id} 没有 EvidenceLedger")
        return
    risk_repo = RiskEvaluationRepository(session)
    risk_ev = await risk_repo.get_by_project_id(str(project_id))
    if risk_ev is None:
        emit("error", f"project_id {project_id} 没有 RiskEvaluation")
        return
    wp_repo = WorkPackagePlanRepository(session)
    wp_plan = await wp_repo.get_by_project_id(str(project_id))
    if wp_plan is None:
        emit("error", f"project_id {project_id} 没有 WorkPackagePlan")
        return
    emit("step", "📝 拼装 10 节开题报告骨架")
    draft = build_proposal_draft(intake, spec, ledger, wp_plan, risk_ev)
    draft.project_id = str(project_id)
    from app.db.proposal_repository import ProposalDraftRepository
    draft_repo = ProposalDraftRepository(session)
    row = await draft_repo.upsert(draft)
    emit("step", "评分", section_count=len(draft.proposal_sections), innovation_count=len(draft.innovation_points))
    emit("result", "开题报告完成", meta={
        "id": row.id,
        "section_count": len(draft.proposal_sections),
        "innovation_count": len(draft.innovation_points),
    })


# ---------- Phase 07 committee ----------


async def committee_async(
    project_id: int, session: AsyncSession,
    emit: Callable[..., None],
) -> None:
    from app.db.proposal_repository import ProposalDraftRepository
    from app.db.work_package_repository import WorkPackagePlanRepository
    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        emit("error", f"project_id {project_id} 没有 EvidenceLedger")
        return
    risk_repo = RiskEvaluationRepository(session)
    risk_ev = await risk_repo.get_by_project_id(str(project_id))
    if risk_ev is None:
        emit("error", f"project_id {project_id} 没有 RiskEvaluation")
        return
    wp_repo = WorkPackagePlanRepository(session)
    wp_plan = await wp_repo.get_by_project_id(str(project_id))
    if wp_plan is None:
        emit("error", f"project_id {project_id} 没有 WorkPackagePlan")
        return
    emit("step", "📋 7 维度规则审查")
    emit("step", "🤖 调 M3 × 3 角色 (supporter / skeptic / pragmatist)")
    import time as _t
    t0 = _t.time()
    review = build_committee_review(ledger, risk_ev, wp_plan)
    elapsed = int((_t.time() - t0) * 1000)
    review.project_id = str(project_id)
    from app.db.proposal_repository import CommitteeReviewRepository
    review_repo = CommitteeReviewRepository(session)
    row = await review_repo.upsert(review)
    emit("step", "✅ 3 角色完成", duration_ms=elapsed, discussion_count=len(review.discussion))
    emit("result", "委员会审查完成", meta={
        "id": row.id,
        "overall_verdict": review.overall_verdict,
        "proposal_maturity": review.proposal_maturity,
        "review_count": len(review.reviews),
        "question_count": len(review.questions),
        "discussion_count": len(review.discussion),
        "allow_proceed_to_phase08": review.allow_proceed_to_phase08,
    })


# ---------- Phase 08 ----------


async def final_package_async(
    project_id: int, session: AsyncSession,
    emit: Callable[..., None],
) -> None:
    from app.db.proposal_repository import (
        CommitteeReviewRepository, ProposalDraftRepository,
    )
    from app.db.work_package_repository import WorkPackagePlanRepository
    from app.db.evidence_ledger_repository import EvidenceLedgerRepository
    from app.db.risk_repository import RiskEvaluationRepository
    from app.db.final_package_repository import FinalPackageRepository
    draft_repo = ProposalDraftRepository(session)
    draft = await draft_repo.get_by_project_id(str(project_id))
    if draft is None:
        emit("error", f"project_id {project_id} 没有 ProposalDraft")
        return
    wp_repo = WorkPackagePlanRepository(session)
    wp_plan = await wp_repo.get_by_project_id(str(project_id))
    if wp_plan is None:
        emit("error", f"project_id {project_id} 没有 WorkPackagePlan")
        return
    review_repo = CommitteeReviewRepository(session)
    review = await review_repo.get_by_project_id(str(project_id))
    if review is None:
        emit("error", f"project_id {project_id} 没有 CommitteeReview")
        return
    risk_repo = RiskEvaluationRepository(session)
    risk_ev = await risk_repo.get_by_project_id(str(project_id))
    if risk_ev is None:
        emit("error", f"project_id {project_id} 没有 RiskEvaluation")
        return
    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        emit("error", f"project_id {project_id} 没有 EvidenceLedger")
        return
    emit("step", "📦 渲染 Markdown (10 节 + 创新点 + 答辩问答)")
    pkg = build_final_package(draft, wp_plan, review, risk_ev, ledger)
    pkg.project_id = str(project_id)
    fp_repo = FinalPackageRepository(session)
    row = await fp_repo.upsert(pkg)
    emit("step", "✅ 3 维验收", backend=pkg.backend_verification, ui=pkg.ui_verification,
         playwright=pkg.playwright_verification)
    emit("result", "最终材料完成", meta={
        "id": row.id,
        "ready_for_thesis": pkg.ready_for_thesis,
        "backend_verification": pkg.backend_verification,
        "ui_verification": pkg.ui_verification,
        "playwright_verification": pkg.playwright_verification,
        "proposal_markdown_chars": len(pkg.proposal_markdown),
    })

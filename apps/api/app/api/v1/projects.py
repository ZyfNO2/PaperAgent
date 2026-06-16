"""Projects API — Phase 01 三个端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    CreateProjectRequest,
    EvidenceLedgerRequest,
    EvidenceLedgerResponse,
    IntakeValidationResponse,
    ProjectResponse,
    RiskEvaluationRequest,
    RiskEvaluationResponse,
    SearchPlanResponse,
    TopicDecomposeRequest,
    TopicSpecResponse,
)
from app.db.database import get_session
from app.db.evidence_ledger_repository import EvidenceLedgerRepository
from app.db.repository import ProjectRepository
from app.db.risk_repository import RiskEvaluationRepository
from app.db.search_plan_repository import SearchPlanRepository
from app.db.topic_spec_repository import TopicSpecRepository
from packages.agents.nodes.phase2_decompose import (
    allow_proceed_to_phase03,
    decompose,
)
from packages.agents.nodes.phase3_search_plan import (
    allow_proceed_to_phase04,
    build_search_plan,
)
from packages.agents.nodes.phase4_evidence import build_evidence_ledger
from packages.agents.nodes.phase5_risk import (
    allow_proceed_to_phase06,
    build_risk_evaluation,
)
from packages.domain import (
    ProjectIntake,
    SearchQueryPlan,
    TopicSpec,
    ValidationOutcome,
    compute_intake_rating,
    derive_missing_fields,
    validate_intake,
)


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="建档：接收 ProjectIntake，落地并计算 intake_rating",
)
async def create_project(
    body: CreateProjectRequest,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    repo = ProjectRepository(session)
    if await repo.get_by_case_id(body.intake.case_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"case_id {body.intake.case_id!r} 已存在",
        )

    intake_for_check = body.intake_for_validation()
    missing = derive_missing_fields(intake_for_check)
    rating = compute_intake_rating(intake_for_check, missing)
    final_intake = intake_for_check.model_copy(
        update={"intake_rating": rating, "missing_fields": missing}
    )

    project = await repo.create(final_intake)
    return ProjectResponse(
        id=project.id, case_id=project.case_id, payload=final_intake
    )


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="按数据库 id 取项目建档",
)
async def get_project(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> ProjectResponse:
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 不存在",
        )
    return ProjectResponse(
        id=project.id,
        case_id=project.case_id,
        payload=ProjectIntake.model_validate(project.payload),
    )


@router.post(
    "/{project_id}/intake/validate",
    response_model=IntakeValidationResponse,
    summary="重新跑 IntakeValidationNode；返回 outcome/rating/missing",
)
async def validate_intake_endpoint(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> IntakeValidationResponse:
    repo = ProjectRepository(session)
    project = await repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 不存在",
        )

    payload = ProjectIntake.model_validate(project.payload)
    outcome, rating, missing = validate_intake(payload)

    # 把最新 missing/rating 写回库（rating 可能因补问后改变）
    new_payload = payload.model_copy(
        update={"intake_rating": rating, "missing_fields": missing}
    )
    await repo.update_payload(project, new_payload)

    return IntakeValidationResponse(
        outcome=outcome,
        intake_rating=rating,
        missing_fields=missing,
        allow_proceed_to_phase02=outcome == ValidationOutcome.OK,
    )


@router.post(
    "/{project_id}/topic/decompose",
    response_model=TopicSpecResponse,
    summary="Phase 02: 调 LLM 拆解题目，生成 TopicSpec",
)
async def decompose_topic(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    body: TopicDecomposeRequest = TopicDecomposeRequest(),
) -> TopicSpecResponse:
    prefer = body.prefer

    proj_repo = ProjectRepository(session)
    project = await proj_repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 不存在",
        )

    payload = ProjectIntake.model_validate(project.payload)

    # 交接校验：必须 Phase 01 通过
    outcome, _, _ = validate_intake(payload)
    if outcome != ValidationOutcome.OK:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Phase 01 状态为 {outcome.value}，禁止进入 Phase 02。"
                " 请先补问后 POST /api/v1/projects/{id}/intake/validate"
            ),
        )

    spec = decompose(payload, prefer=prefer)
    spec.project_id = str(project_id)

    spec_repo = TopicSpecRepository(session)
    row = await spec_repo.upsert(spec)

    allow, _ = allow_proceed_to_phase03(spec)
    return TopicSpecResponse(
        id=row.id,
        project_id=row.project_id,
        case_id=row.case_id,
        payload=row.payload,
        decomposition_rating=spec.decomposition_rating,
        allow_proceed_to_phase03=allow,
    )


@router.get(
    "/{project_id}/topic/spec",
    response_model=TopicSpecResponse,
    summary="取已落库的 TopicSpec",
)
async def get_topic_spec(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> TopicSpecResponse:
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 TopicSpec，请先调 decompose",
        )
    allow, _ = allow_proceed_to_phase03(spec)
    return TopicSpecResponse(
        id=0,
        project_id=spec.project_id,
        case_id=spec.source_intake_case_id,
        payload=spec.model_dump(mode="json"),
        decomposition_rating=spec.decomposition_rating,
        allow_proceed_to_phase03=allow,
    )


# -------- Phase 03 -------- #


@router.post(
    "/{project_id}/search/plan",
    response_model=SearchPlanResponse,
    summary="Phase 03: 从 TopicSpec 推 SearchQueryPlan",
)
async def build_search_plan_endpoint(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> SearchPlanResponse:
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 TopicSpec，请先调 decompose",
        )

    allow_p3, _ = allow_proceed_to_phase03(spec)
    if not allow_p3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="TopicSpec 评级不允许进入 Phase 03",
        )

    plan = build_search_plan(spec)
    plan.project_id = str(project_id)
    spec_repo2 = TopicSpecRepository(session)  # 不重复用，复用即可
    plan_repo = SearchPlanRepository(session)
    row = await plan_repo.upsert(plan)

    allow_p4, _ = allow_proceed_to_phase04(plan)
    return SearchPlanResponse(
        id=row.id,
        project_id=row.project_id,
        case_id=spec.source_intake_case_id,
        payload=row.payload,
        maturity_rating=plan.maturity_rating,
        allow_proceed_to_phase04=allow_p4,
    )


@router.get(
    "/{project_id}/search/plan",
    response_model=SearchPlanResponse,
    summary="取已落库的 SearchQueryPlan",
)
async def get_search_plan(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> SearchPlanResponse:
    repo = SearchPlanRepository(session)
    plan = await repo.get_by_project_id(str(project_id))
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 SearchQueryPlan，请先调 plan",
        )
    allow_p4, _ = allow_proceed_to_phase04(plan)
    return SearchPlanResponse(
        id=0,
        project_id=plan.project_id,
        case_id="",
        payload=plan.model_dump(mode="json"),
        maturity_rating=plan.maturity_rating,
        allow_proceed_to_phase04=allow_p4,
    )


# -------- Phase 04 -------- #


@router.post(
    "/{project_id}/evidence/build",
    response_model=EvidenceLedgerResponse,
    summary="Phase 04: 调 LLM 生成证据账本（论文/数据集/baseline/指标/模板）",
)
async def build_evidence_endpoint(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    body: EvidenceLedgerRequest = EvidenceLedgerRequest(),
) -> EvidenceLedgerResponse:
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 TopicSpec",
        )

    plan_repo = SearchPlanRepository(session)
    plan = await plan_repo.get_by_project_id(str(project_id))
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project_id {project_id} 没有 SearchQueryPlan，请先调 plan",
        )

    ledger = build_evidence_ledger(spec, plan, prefer=body.prefer)
    ledger.project_id = str(project_id)

    led_repo = EvidenceLedgerRepository(session)
    row = await led_repo.upsert(ledger)

    return EvidenceLedgerResponse(
        id=row.id,
        project_id=row.project_id,
        case_id=spec.source_intake_case_id,
        payload=row.payload,
        evidence_rating=ledger.evidence_rating,
        risk_flags=ledger.risk_flags,
        paper_count=len(ledger.papers),
        dataset_count=len(ledger.datasets),
        baseline_count=len(ledger.baselines),
        metric_count=len(ledger.metrics),
    )


@router.get(
    "/{project_id}/evidence/ledger",
    response_model=EvidenceLedgerResponse,
    summary="取已落库的 EvidenceLedger",
)
async def get_evidence_ledger(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> EvidenceLedgerResponse:
    repo = EvidenceLedgerRepository(session)
    ledger = await repo.get_by_project_id(str(project_id))
    if ledger is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 EvidenceLedger",
        )
    return EvidenceLedgerResponse(
        id=0,
        project_id=ledger.project_id,
        case_id="",
        payload=ledger.model_dump(mode="json"),
        evidence_rating=ledger.evidence_rating,
        risk_flags=ledger.risk_flags,
        paper_count=len(ledger.papers),
        dataset_count=len(ledger.datasets),
        baseline_count=len(ledger.baselines),
        metric_count=len(ledger.metrics),
    )


# -------- Phase 05 -------- #


@router.post(
    "/{project_id}/risk/evaluate",
    response_model=RiskEvaluationResponse,
    summary="Phase 05: 六维风险评分 + Pivot 候选",
)
async def evaluate_risk_endpoint(
    project_id: int,
    session: AsyncSession = Depends(get_session),
    body: RiskEvaluationRequest = RiskEvaluationRequest(),
) -> RiskEvaluationResponse:
    spec_repo = TopicSpecRepository(session)
    spec = await spec_repo.get_by_project_id(str(project_id))
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 TopicSpec",
        )

    plan_repo = SearchPlanRepository(session)
    plan = await plan_repo.get_by_project_id(str(project_id))
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project_id {project_id} 没有 SearchQueryPlan",
        )

    led_repo = EvidenceLedgerRepository(session)
    ledger = await led_repo.get_by_project_id(str(project_id))
    if ledger is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"project_id {project_id} 没有 EvidenceLedger",
        )

    proj_repo = ProjectRepository(session)
    project = await proj_repo.get_by_id(project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 不存在",
        )
    intake = ProjectIntake.model_validate(project.payload)

    ev = build_risk_evaluation(intake, spec, plan, ledger, prefer=body.prefer)
    ev.project_id = str(project_id)

    repo = RiskEvaluationRepository(session)
    row = await repo.upsert(ev)

    allow, _ = allow_proceed_to_phase06(ev)
    return RiskEvaluationResponse(
        id=row.id,
        project_id=row.project_id,
        case_id=spec.source_intake_case_id,
        payload=row.payload,
        overall_rating=ev.risk_score.overall_rating,
        overall_score=ev.risk_score.overall_score,
        decision=ev.decision,
        max_risk_dimension=ev.risk_score.max_risk_dimension,
        pivot_count=len(ev.pivot_candidates),
        allow_proceed_to_phase06=allow,
    )


@router.get(
    "/{project_id}/risk/evaluation",
    response_model=RiskEvaluationResponse,
    summary="取已落库的 RiskEvaluation",
)
async def get_risk_evaluation(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> RiskEvaluationResponse:
    repo = RiskEvaluationRepository(session)
    ev = await repo.get_by_project_id(str(project_id))
    if ev is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"project_id {project_id} 没有 RiskEvaluation",
        )
    allow, _ = allow_proceed_to_phase06(ev)
    return RiskEvaluationResponse(
        id=0,
        project_id=ev.project_id,
        case_id="",
        payload=ev.model_dump(mode="json"),
        overall_rating=ev.risk_score.overall_rating,
        overall_score=ev.risk_score.overall_score,
        decision=ev.decision,
        max_risk_dimension=ev.risk_score.max_risk_dimension,
        pivot_count=len(ev.pivot_candidates),
        allow_proceed_to_phase06=allow,
    )

"""Projects API — Phase 01 三个端点。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    CreateProjectRequest,
    IntakeValidationResponse,
    ProjectResponse,
)
from app.db.database import get_session
from app.db.repository import ProjectRepository
from packages.domain import (
    ProjectIntake,
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

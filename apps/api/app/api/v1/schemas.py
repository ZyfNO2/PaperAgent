"""Schemas for the projects API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from packages.domain import IntakeRating, MissingField, ProjectIntake, ValidationOutcome


class CreateProjectRequest(BaseModel):
    """POST /api/v1/projects 的请求体。

    ``intake_rating`` 由校验流程计算，不接受调用方直接传入，避免越权。
    """

    model_config = ConfigDict(extra="forbid")

    intake: ProjectIntake = Field(
        description="ProjectIntake 对象；intake_rating 字段将被服务端覆盖",
    )

    def intake_for_validation(self) -> ProjectIntake:
        """构造一个 intake_rating 必填占位（服务端随后覆盖）。"""

        return self.intake.model_copy(update={"intake_rating": "A"})


class ProjectResponse(BaseModel):
    id: int
    case_id: str
    payload: ProjectIntake


class IntakeValidationResponse(BaseModel):
    outcome: ValidationOutcome
    intake_rating: IntakeRating
    missing_fields: list[MissingField]
    allow_proceed_to_phase02: bool = Field(
        description="仅在 outcome=OK 时为 True；NEED_CLARIFICATION 与 BLOCKED 都为 False",
    )

"""Schemas for the projects API."""

from __future__ import annotations

from typing import Literal

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


class TopicDecomposeRequest(BaseModel):
    """POST /api/v1/projects/{id}/topic/decompose 的请求体。"""

    model_config = ConfigDict(extra="forbid")

    prefer: Literal["auto", "llm", "heuristic"] = Field(
        default="auto",
        description="auto=LLM 优先，失败 fallback heuristic；llm=强制 LLM；heuristic=强制规则",
    )


class TopicSpecResponse(BaseModel):
    id: int
    project_id: str
    case_id: str
    payload: dict
    decomposition_rating: str
    allow_proceed_to_phase03: bool


class SearchPlanResponse(BaseModel):
    id: int
    project_id: str
    case_id: str
    payload: dict
    maturity_rating: str
    allow_proceed_to_phase04: bool


class EvidenceLedgerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefer: Literal["auto", "llm", "heuristic"] = "auto"


class EvidenceLedgerResponse(BaseModel):
    id: int
    project_id: str
    case_id: str
    payload: dict
    evidence_rating: str
    risk_flags: list[str]
    paper_count: int
    dataset_count: int
    baseline_count: int
    metric_count: int


class RiskEvaluationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prefer: Literal["auto", "llm", "heuristic"] = "auto"


class RiskEvaluationResponse(BaseModel):
    id: int
    project_id: str
    case_id: str
    payload: dict
    overall_rating: str
    overall_score: float
    decision: str
    max_risk_dimension: str
    pivot_count: int
    allow_proceed_to_phase06: bool


class WorkPackagePlanResponse(BaseModel):
    id: int
    project_id: str
    case_id: str
    payload: dict
    final_topic: str
    from_pivot: bool
    work_package_count: int
    experiment_count: int
    allow_proceed_to_phase07: bool

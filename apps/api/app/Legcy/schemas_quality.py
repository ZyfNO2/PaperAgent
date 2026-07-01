"""Session 12: 报告质量检查与低门槛委员会复核 schema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .schemas import EvidenceRef


QualityResult = Literal["通过", "有条件通过", "需修改", "不建议"]
RiskLevel = Literal["低", "中", "高"]


class ReportQualityCheck(BaseModel):
    """8 维中一维的检查结果."""

    model_config = ConfigDict(extra="forbid")

    dimension: str
    result: QualityResult
    score: float = Field(ge=0, le=100)
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class DefenseQuestion(BaseModel):
    """答辩问题."""

    model_config = ConfigDict(extra="forbid")

    question: str
    risk_level: RiskLevel
    suggested_answer: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)


class ReportQualityReview(BaseModel):
    """整体质量评审结果."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    verdict: QualityResult
    score: float = Field(ge=0, le=100)
    checks: list[ReportQualityCheck] = Field(default_factory=list)
    revision_checklist: list[str] = Field(default_factory=list)
    defense_questions: list[DefenseQuestion] = Field(default_factory=list)
    reviewed_at: str


class ReportReviewRequest(BaseModel):
    """POST /report/review 请求体."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["light", "full"] = "light"
    use_llm: bool = False
    include_trace: bool = True


class ReportReviewSummary(BaseModel):
    """GET /report/review 缩略响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    verdict: QualityResult
    score: float
    dimension_count: int
    passing_count: int
    failing_dimensions: list[str] = Field(default_factory=list)
    reviewed_at: str
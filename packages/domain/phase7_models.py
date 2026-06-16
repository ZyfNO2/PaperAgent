"""Phase 07 domain models: ProposalDraft / CommitteeReview / Section.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_07_开题报告生成与委员会审查.md §2-§4
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


PROPOSAL_SECTIONS = [
    "研究背景与意义",
    "国内外研究现状",
    "研究问题与目标",
    "研究内容与技术路线",
    "拟解决关键问题",
    "预期创新点",
    "实验方案与评价指标",
    "可行性分析",
    "进度计划",
    "风险预案",
]


SectionKey = Literal[
    "研究背景与意义",
    "国内外研究现状",
    "研究问题与目标",
    "研究内容与技术路线",
    "拟解决关键问题",
    "预期创新点",
    "实验方案与评价指标",
    "可行性分析",
    "进度计划",
    "风险预案",
]


class ProposalSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: SectionKey
    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    sources: list[str] = Field(default_factory=list, description="内容来源（章节 / evidence / risk 等）")


class InnovationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    innovation_id: str
    problem: str = Field(min_length=1)
    method: str = Field(min_length=1)
    verification: str = Field(min_length=1)
    metrics: list[str] = Field(default_factory=list)
    risk: str = "中"


class ResearchStatusRow(BaseModel):
    """研究现状表中的一行（类别 / 代表工作 / 不足 / 与本文关系）。"""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1)
    representative_work: str = Field(min_length=1)
    gap: str = Field(min_length=1)
    relation: str = Field(min_length=1)


class ProposalDraft(BaseModel):
    """Phase 07 产物：开题报告骨架（10 节）。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    work_package_plan_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    final_topic: str = Field(min_length=1)
    proposal_sections: list[ProposalSection] = Field(min_length=10)
    research_status: list[ResearchStatusRow] = Field(default_factory=list)
    innovation_points: list[InnovationPoint] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    risk_plan: list[str] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class CommitteeReviewItem(BaseModel):
    """单维度审查意见。"""

    model_config = ConfigDict(extra="forbid")

    dimension: str = Field(min_length=1)
    verdict: Literal["通过", "有条件通过", "需修改", "不通过"]
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class CommitteeQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    suggested_answer: str = Field(min_length=1)
    evidence_source: str | None = None


class CommitteeReview(BaseModel):
    """Phase 07 产物：委员会审查意见。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    proposal_draft_id: str = Field(default="")

    reviews: list[CommitteeReviewItem] = Field(min_length=1)
    questions: list[CommitteeQuestion] = Field(default_factory=list)
    revision_checklist: list[dict] = Field(default_factory=list)

    overall_verdict: Literal["通过", "有条件通过", "需修改", "不通过"]
    proposal_maturity: Literal["A", "B", "C", "D"]
    allow_proceed_to_phase08: bool = False

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

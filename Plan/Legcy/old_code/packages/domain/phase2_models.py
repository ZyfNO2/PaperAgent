"""Phase 02 domain models: TopicSpec / RiskTerm / ThesisMapping / WorkPackageDraft.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_02_题目拆解与论文结构映射.md §3.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


DecompositionRating = Literal["A", "B", "C", "D"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskTerm(BaseModel):
    """高风险词条目（Phase 02 §3.1 + §4 Step 3）。"""

    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, description="原题中的高风险词，如'智能/通用/大模型'")
    risk: str = Field(min_length=1, description="可能引发的风险点")
    verifiable_definition: str = Field(
        min_length=1, description="如何改写成可被实验验证的措辞"
    )
    handling: Literal["保留并定义", "改写", "删除", "需补证据"] = "改写"


class ThesisMapping(BaseModel):
    """五章式论文结构预映射。"""

    model_config = ConfigDict(extra="forbid")

    chapter_1_intro: str = Field(min_length=1, description="第一章绪论可写内容")
    chapter_2_basics: str = Field(min_length=1, description="第二章相关基础可写内容")
    chapter_3_wp1: str = Field(min_length=1, description="第三章 工作包一")
    chapter_4_wp2: str = Field(min_length=1, description="第四章 工作包二")
    chapter_5_summary: str = Field(min_length=1, description="第五章总结与展望")


class WorkPackageDraft(BaseModel):
    """工作包雏形（每个 WP 必须落到一个章节）。"""

    model_config = ConfigDict(extra="forbid")

    wp_id: str = Field(min_length=1, description="如 WP1 / WP2")
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    method_approach: str = Field(min_length=1)
    data_source: str = Field(min_length=1)
    experiment_plan: str = Field(min_length=1)
    chapter: Literal["第三章", "第四章"]
    evidence_required: list[str] = Field(default_factory=list)


class TopicSpec(BaseModel):
    """LangGraph Phase 02 子图的产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(
        default="",
        description="ProjectIntake.id（数据库主键）。新建 spec 时由 router 在入库前填入。",
    )
    source_intake_case_id: str = Field(min_length=1)
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]
    first_result_deadline: str | None = None
    raw_topic: str = Field(min_length=1)
    normalized_topic: str = Field(min_length=1)

    research_object: str | None = None
    application_scenario: str | None = None
    task_type: list[str] = Field(default_factory=list)
    data_modality: list[str] = Field(default_factory=list)
    method_family: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    evaluation_metrics: list[str] = Field(default_factory=list)
    engineering_constraints: list[str] = Field(default_factory=list)

    risk_terms: list[RiskTerm] = Field(default_factory=list)
    thesis_mapping: ThesisMapping
    work_package_drafts: list[WorkPackageDraft] = Field(min_length=1)

    carried_constraints: list[str] = Field(default_factory=list)
    decomposition_rating: DecompositionRating = "A"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

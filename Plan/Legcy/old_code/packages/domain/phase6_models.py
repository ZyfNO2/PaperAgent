"""Phase 06 domain models: Experiment / ExperimentMatrix / WorkPackageFinal / WorkPackagePlan.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_06_工作包定稿与实验矩阵.md §3 / §4
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


ExperimentType = Literal["主实验", "对比实验", "消融实验", "参数实验", "案例分析", "端到端测试", "效率评估"]
ChapterAnchor = Literal["第一章", "第二章", "第三章", "第四章", "第五章"]
WorkPackageKind = Literal[
    "证据链构建型", "风险评分型", "Pivot 决策型",
    "系统实现型", "对比分析型", "模板生成型",
]


class Experiment(BaseModel):
    """实验矩阵中的一项。"""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str = Field(min_length=1)
    type: ExperimentType
    purpose: str = Field(min_length=1)
    data_source: str = Field(min_length=1)
    baseline_or_control: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    expected_artifact: str = Field(min_length=1, description="预期图表 / 表格")
    wp_binding: Literal["WP1", "WP2"]


class ExperimentMatrix(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wp_id: Literal["WP1", "WP2"]
    main_experiment: Experiment
    supporting_experiments: list[Experiment] = Field(default_factory=list)


class ThesisOutlineChapter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chapter: ChapterAnchor
    title: str = Field(min_length=1)
    content_summary: str = Field(min_length=1)
    data_sources: list[str] = Field(default_factory=list)
    figures_needed: list[str] = Field(default_factory=list)


class WorkPackageFinal(BaseModel):
    """工作包定稿。"""

    model_config = ConfigDict(extra="forbid")

    wp_id: Literal["WP1", "WP2"]
    kind: WorkPackageKind
    chapter: ChapterAnchor
    title: str = Field(min_length=1)
    research_question: str = Field(min_length=1)
    method_approach: str = Field(min_length=1)
    data_source: str = Field(min_length=1)
    baseline_or_control: str = Field(min_length=1)
    metrics: list[str] = Field(min_length=1)
    main_experiment: Experiment
    supporting_experiments: list[Experiment] = Field(min_length=1)
    chapter_sections: list[str] = Field(min_length=1, description="该 WP 占据的小节列表")
    innovation_binding: str = Field(min_length=1, description="创新点 → 哪个实验绑定")


class WorkPackagePlan(BaseModel):
    """Phase 06 产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    risk_evaluation_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    final_topic: str = Field(min_length=1)
    final_topic_from_pivot: bool = False
    final_topic_rationale: str = Field(min_length=1)

    work_packages: list[WorkPackageFinal] = Field(min_length=1)
    experiment_matrices: list[ExperimentMatrix] = Field(min_length=1)
    thesis_outline: list[ThesisOutlineChapter] = Field(min_length=5)

    max_writing_risk: str = Field(min_length=1)
    allow_proceed_to_phase07: bool = True

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

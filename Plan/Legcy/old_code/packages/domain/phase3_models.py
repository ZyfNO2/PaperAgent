"""Phase 03 domain models: SearchQueryPlan / QueryLayer / SourceTarget / probes.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_03_方向成熟度与检索计划.md §2.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class QueryLayer(BaseModel):
    """L0-L6 检索层（§3）。"""

    model_config = ConfigDict(extra="forbid")

    layer: Literal["L0", "L1", "L2", "L3", "L4", "L5", "L6"]
    title: str
    purpose: str
    queries: list[str] = Field(min_length=1)
    target_sources: list[str] = Field(default_factory=list)


class SourceTarget(BaseModel):
    """检索源路由（§2.3）。"""

    model_config = ConfigDict(extra="forbid")

    evidence_type: Literal[
        "英文论文", "代码/baseline", "数据集",
        "中文学位论文", "技术模板", "综述",
    ]
    primary_sources: list[str]
    fallback_sources: list[str] = Field(default_factory=list)
    notes: str | None = None


class WorkPackageQuery(BaseModel):
    """每个 WP 绑定的检索词（§4 + §8）。"""

    model_config = ConfigDict(extra="forbid")

    wp_id: str
    required_evidence: list[str]
    query_groups: list[str] = Field(min_length=2, description="≥ 2 组检索词")
    priority_sources: list[str] = Field(default_factory=list)


class MaturityProbe(BaseModel):
    """方向成熟度预判（§4.1 + §9）。"""

    model_config = ConfigDict(extra="forbid")

    has_survey: bool = False
    has_benchmark: bool = False
    has_public_dataset: bool = False
    has_open_code: bool = False
    has_thesis_template: bool = False
    expected_paper_density: Literal["高", "中", "低", "未知"] = "未知"
    notes: list[str] = Field(default_factory=list)


class BaselineProbe(BaseModel):
    """Baseline 入口预判（§4.2）。"""

    model_config = ConfigDict(extra="forbid")

    candidate_baselines: list[str] = Field(default_factory=list)
    expected_datasets: list[str] = Field(default_factory=list)
    expected_metrics: list[str] = Field(default_factory=list)


class ThesisTemplateProbe(BaseModel):
    """学位论文与实验模板（§4.4）。"""

    model_config = ConfigDict(extra="forbid")

    template_queries_zh: list[str] = Field(default_factory=list)
    ablation_templates: list[str] = Field(default_factory=list)
    comparison_templates: list[str] = Field(default_factory=list)


class SearchQueryPlan(BaseModel):
    """Phase 03 产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    topic_spec_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]
    carried_constraints: list[str] = Field(default_factory=list)

    query_layers: list[QueryLayer] = Field(min_length=3)
    source_targets: list[SourceTarget] = Field(min_length=1)
    work_package_queries: list[WorkPackageQuery] = Field(min_length=1)
    maturity_probe: MaturityProbe = Field(default_factory=MaturityProbe)
    baseline_probe: BaselineProbe = Field(default_factory=BaselineProbe)
    thesis_template_probe: ThesisTemplateProbe = Field(default_factory=ThesisTemplateProbe)

    risk_flags: list[str] = Field(default_factory=list)
    maturity_rating: Literal["A", "B", "C", "D"] = "A"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

"""Phase 04 domain models: PaperEvidence / BaselineCandidate / DatasetCandidate / EvidenceLedger.

对齐 Plan/TopicPilot-CN_SOP_Phases/Phase_04_证据采集与Baseline账本.md §3.1
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


SourceTag = Literal[
    "OpenAlex", "Semantic Scholar", "arXiv", "Crossref", "DBLP",
    "GitHub", "Papers with Code", "Hugging Face",
    "CNKI", "Wanfang", "学校仓储", "模板复用",
    "LLM-generated-candidate", "无法追溯",
]


class PaperEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1, description="如 P001 / P002")
    title: str = Field(min_length=1)
    year: int | None = None
    source: SourceTag
    url: str | None = None
    abstract: str | None = None
    task: list[str] = Field(default_factory=list)
    method: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    baseline_mentions: list[str] = Field(default_factory=list)
    reusable_value: str = Field(min_length=1, description="可借鉴点")
    evidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    wp_binding: list[str] = Field(default_factory=list, description="绑定的 WP1/WP2")


class DatasetCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    task: list[str] = Field(default_factory=list)
    modality: list[str] = Field(default_factory=list)
    scale: str | None = None
    license: str | None = None
    download: str | None = None
    fit_to_topic: Literal["高", "中", "低", "未知"] = "中"
    wp_binding: list[str] = Field(default_factory=list)


class BaselineCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    paper_title: str | None = None
    repository_url: str | None = None
    has_readme: bool = False
    has_env_file: bool = False
    has_training_script: bool = False
    has_eval_script: bool = False
    has_pretrained_weight: bool = False
    license: str | None = None
    reproduce_difficulty: Literal["低", "中", "高", "未知"] = "中"
    fit_to_student_resources: Literal["适合", "勉强", "不适合", "未知"] = "未知"
    wp_binding: list[str] = Field(default_factory=list)


class MetricSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    task: str = Field(min_length=1)
    reproducible: bool = True
    source: str | None = None


class ExperimentTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1)
    type: Literal["对比实验", "消融实验", "参数实验", "案例分析"]
    source_paper: str | None = None
    note: str = Field(min_length=1)


class ThesisTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    toc_outline: list[str] = Field(default_factory=list)
    method_chapter_structure: list[str] = Field(default_factory=list)
    note: str | None = None


class EvidenceLedger(BaseModel):
    """Phase 04 产物。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    project_id: str = Field(default="")
    query_plan_id: str = Field(default="")
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]

    papers: list[PaperEvidence] = Field(default_factory=list)
    surveys: list[PaperEvidence] = Field(default_factory=list)
    datasets: list[DatasetCandidate] = Field(default_factory=list)
    baselines: list[BaselineCandidate] = Field(default_factory=list)
    metrics: list[MetricSet] = Field(default_factory=list)
    experiment_templates: list[ExperimentTemplate] = Field(default_factory=list)
    thesis_templates: list[ThesisTemplate] = Field(default_factory=list)

    risk_flags: list[str] = Field(default_factory=list)
    evidence_rating: Literal["A", "B", "C", "D"] = "A"

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

"""Session 62: Schemas for GraduationDirection planning endpoint.

Ponytail: keep schemas tiny; no nested complex models beyond what frontend renders.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskLevel = Literal["low", "medium", "high"]


class GraduationDirectionRequest(BaseModel):
    """POST /api/v1/projects/{project_id}/graduation-direction/plan 请求体."""

    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, description="原始题目 (用于启发式匹配与 fallback)")
    use_last_retrieval: bool = Field(
        default=True,
        description="是否复用 S61 最近一次 retrieval run 的候选",
    )
    use_local_rag: bool = Field(
        default=True,
        description="是否复用 S60 本地 RAG 命中片段作为方向证据",
    )
    max_directions: int = Field(
        default=3,
        ge=2,
        le=3,
        description="生成方向数量上限 (2-3)",
    )


class BaselineRecommendation(BaseModel):
    """M4 输出: 推荐 baseline."""

    model_config = ConfigDict(extra="forbid")

    name: str
    rationale: str
    required_data: str
    reproducibility: Literal["low", "medium", "high"]
    estimated_compute: str
    risks: list[str] = Field(default_factory=list)


class ExtensionModule(BaseModel):
    """M5 输出: 可加模块."""

    model_config = ConfigDict(extra="forbid")

    name: str
    attach_to: str
    problem_solved: str
    ablation_plan: str
    effort: Literal["S", "M", "L"]
    risks: list[str] = Field(default_factory=list)


class EvidenceBundleRef(BaseModel):
    """EvidenceBundle 单条引用 (轻量)."""

    model_config = ConfigDict(extra="forbid")

    ref_type: Literal["paper", "dataset", "repo", "rag_chunk"]
    ref_id: str
    title: str
    url: str | None = None
    quote: str | None = None


class EvidenceBundle(BaseModel):
    """M3 输出: 方向绑定证据 (来自 S61 retrieval + S60 local RAG + ledger)."""

    model_config = ConfigDict(extra="forbid")

    papers: list[EvidenceBundleRef] = Field(default_factory=list)
    datasets: list[EvidenceBundleRef] = Field(default_factory=list)
    repos: list[EvidenceBundleRef] = Field(default_factory=list)
    rag_refs: list[EvidenceBundleRef] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class ScoringBreakdownItem(BaseModel):
    """开发者窗口: 单维度评分."""

    model_config = ConfigDict(extra="forbid")

    key: str
    label: str
    score: float
    weight: float
    note: str = ""


class GraduationDirection(BaseModel):
    """M1+M2+M3+M4+M5: 单个方向."""

    model_config = ConfigDict(extra="forbid")

    direction_id: str
    title: str
    research_object: str
    task: str
    method_route: str
    why_graduation_friendly: list[str] = Field(default_factory=list)
    fallback_route: str = ""
    score: float = 0.0
    risk_level: RiskLevel = "medium"
    evidence_bundle: EvidenceBundle = Field(default_factory=EvidenceBundle)
    recommended_baselines: list[BaselineRecommendation] = Field(default_factory=list)
    extension_modules: list[ExtensionModule] = Field(default_factory=list)
    scoring_breakdown: list[ScoringBreakdownItem] = Field(default_factory=list)


class DirectionDecisionReport(BaseModel):
    """M6 输出: 整张决策报告."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    topic: str
    recommended_direction_id: str
    directions: list[GraduationDirection]
    stop_reason: str
    generated_at: str
    evidence_sources: dict[str, int] = Field(
        default_factory=dict,
        description="开发者窗口: 各来源计数 (retrieval_run / local_rag / ledger)",
    )
    warnings: list[str] = Field(default_factory=list)
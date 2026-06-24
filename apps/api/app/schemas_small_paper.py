"""Small Paper Expansion schemas (Session 49: Track B 闭环).

设计文档 B (Plan/design/PaperAgent_B_用户画像与流程重构建议_保毕业_已有小论文.md)
§9-§12 + 文档 C §15、§16 — single small paper → thesis extension.

Track B 路径:
  上传小论文 PDF → 抽贡献 (LLM + heuristic fallback) → 映射章节 →
  缺口分析 → 扩展实验规划 → 重复风险提示 → paper_extension 报告.

数据模型:
- SmallPaperCard: 一篇小论文的结构化摘要.
- ChapterMapping: 小论文章节 → 大论文章节映射.
- ExtensionPlan: 大论文扩展规划 (含 ExtensionExperiment + WorkPackageSuggestion).
- ExtensionExperiment: 单条扩展实验建议.
- WorkPackageSuggestion: 第二/第三工作包 (复用 OneTopic WorkPackage 字段).
- RepeatRiskWarning: 重复风险提示.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------- 枚举 ---------- #

PublicationStatus = Literal["draft", "submitted", "accepted", "published", "unknown"]

ThesisChapter = Literal[
    "ch1_intro",
    "ch2_related",
    "ch3_method",
    "ch4_experiment",
    "ch5_conclusion",
    "appendix",
    "unmapped",
]

ReuseType = Literal["direct_reuse", "extend", "summarize", "cannot_reuse"]

ExtractionMode = Literal["llm", "heuristic"]

EffortLevel = Literal["low", "medium", "high"]

RepeatRiskCategory = Literal[
    "verbatim_copy",
    "incremental_only",
    "no_extension",
    "method_reuse_only",
]

RepeatRiskSeverity = Literal["low", "medium", "high"]


# ---------- 核心模型 ---------- #


class SmallPaperCard(BaseModel):
    """小论文结构化摘要 — Track B 的入口数据.

    由 contribution_extractor 从小论文 chunk 抽取 (LLM 优先, 失败回 heuristic).
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    project_id: str
    title: str
    publication_status: PublicationStatus = "unknown"
    venue: str | None = None
    contribution_points: list[str] = Field(default_factory=list)
    method_modules: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    experiment_tables: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    reusable_chapter_sections: list[str] = Field(default_factory=list)
    missing_for_thesis: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list, description="关联的 chunk evidence_id")
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_mode: ExtractionMode = "heuristic"


class ChapterMapping(BaseModel):
    """小论文某节内容 → 大论文章节映射."""

    model_config = ConfigDict(extra="forbid")

    small_paper_section: str
    thesis_chapter: ThesisChapter
    reuse_type: ReuseType
    note: str = ""


class ExtensionExperiment(BaseModel):
    """单条扩展实验建议 — 补大论文哪个章节."""

    model_config = ConfigDict(extra="forbid")

    experiment_id: str
    title: str
    description: str
    datasets: list[str] = Field(default_factory=list)
    baselines: list[str] = Field(default_factory=list)
    estimated_effort: EffortLevel = "medium"
    priority: int = Field(default=3, ge=1, le=5, description="1=最高优先")
    fills_chapter: str = Field(default="", description="补哪个章节, 例 ch4 / ch3/ch4 / appendix")


class WorkPackageSuggestion(BaseModel):
    """第二/第三工作包 — 大论文规划用 (复用 OneTopic 字段)."""

    model_config = ConfigDict(extra="forbid")

    wp_id: str
    title: str
    goal: str
    deliverable: str
    estimated_effort: EffortLevel = "medium"
    dependencies: list[str] = Field(default_factory=list)


class ExtensionPlan(BaseModel):
    """大论文扩展规划 — 章节覆盖 / 缺口 / 实验 / 工作包."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    project_id: str
    covered_chapters: list[ThesisChapter] = Field(default_factory=list)
    missing_chapters: list[ThesisChapter] = Field(default_factory=list)
    gap_analysis: list[str] = Field(default_factory=list)
    extension_experiments: list[ExtensionExperiment] = Field(default_factory=list)
    second_work_package: WorkPackageSuggestion | None = None
    third_work_package: WorkPackageSuggestion | None = None
    reuse_risks: list[str] = Field(default_factory=list)
    thesis_outline: list[str] = Field(default_factory=list)


class RepeatRiskWarning(BaseModel):
    """重复 / 增量不足 / 简单复用的风险提示."""

    model_config = ConfigDict(extra="forbid")

    category: RepeatRiskCategory
    severity: RepeatRiskSeverity
    note: str
    related_section: str | None = None


# ---------- API 请求 / 响应 ---------- #


class SmallPaperExtractRequest(BaseModel):
    """POST /paper-library/small-paper/extract 请求体."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1)
    prefer: Literal["auto", "llm", "heuristic"] = Field(
        default="auto",
        description="auto=LLM 失败 fallback heuristic; heuristic=纯规则; llm=强制 LLM",
    )


class SmallPaperExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    card: SmallPaperCard
    extraction_mode: ExtractionMode
    extraction_confidence: float


class SmallPaperExtensionPlanRequest(BaseModel):
    """POST /paper-library/small-paper/extension-plan 请求体."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1)
    target_chapter_count: int = Field(default=5, ge=3, le=8)
    prefer: Literal["auto", "heuristic"] = Field(default="auto")


class SmallPaperExtensionPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    plan: ExtensionPlan


class SmallPaperRepeatRisksRequest(BaseModel):
    """POST /paper-library/small-paper/repeat-risks 请求体."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str = Field(min_length=1)


class SmallPaperRepeatRisksResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paper_id: str
    risks: list[RepeatRiskWarning]
    risk_count: int

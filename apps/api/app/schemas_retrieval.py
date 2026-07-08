"""Session 14: 多源检索增强 schema.

多源检索的输入输出模型, 独立于 evidence / final_package 的数据契约,
以 ``RetrievalCandidate`` 为统一形态, 经 import 后才转成 ``EvidenceItem``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SearchSource = Literal[
    "openalex",
    "semantic_scholar",
    "arxiv",
    "github",
    "huggingface",
    "kaggle",
    "core",
    "datacite",
    "crossref",
    "pubmed",
    "manual_fallback",
]

CandidateType = Literal["paper", "dataset", "repo", "project_page", "note"]
RetrievalStatus = Literal["running", "completed", "partial", "failed"]


# ---------- 候选 ---------- #


class RetrievalCandidate(BaseModel):
    """来自任一来源的归一化候选 (SOP §6.3)."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    project_id: str
    candidate_type: CandidateType
    source: SearchSource
    title: str
    url: str | None = None
    year: int | None = None
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    repo_full_name: str | None = None
    dataset_slug: str | None = None
    license: str | None = None
    stars: int | None = None
    citation_count: int | None = None
    updated_at: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    retrieval_score: float = 0.0
    quality_hints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_duplicate: bool = False
    duplicate_of: str | None = None
    already_in_ledger: bool = False
    raw: dict = Field(default_factory=dict)


# ---------- 查询计划 / 检索请求 ---------- #


class QueryPlanLayer(BaseModel):
    """查询计划中的一层."""

    model_config = ConfigDict(extra="forbid")

    layer: str
    queries: list[str] = Field(default_factory=list)


class QueryPlan(BaseModel):
    """从题目生成的 paper / dataset / repo 查询计划 (SOP §7)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    raw_topic: str
    paper_queries: list[QueryPlanLayer] = Field(default_factory=list)
    dataset_queries: list[QueryPlanLayer] = Field(default_factory=list)
    repo_queries: list[QueryPlanLayer] = Field(default_factory=list)


class RetrievalSearchRequest(BaseModel):
    """POST /retrieval/search 请求体 (SOP §13.1)."""

    model_config = ConfigDict(extra="forbid")

    scope: list[CandidateType] = Field(default_factory=lambda: ["paper", "dataset", "repo"])
    sources: list[SearchSource] = Field(
        default_factory=lambda: ["openalex", "arxiv", "github", "huggingface"]
    )
    top_k_per_source: int = Field(default=8, ge=1, le=20)
    include_existing: bool = False
    auto_import: bool = False
    auto_verify: bool = False
    extra_keywords: list[str] = Field(default_factory=list)


# ---------- 检索运行 ---------- #


class SourceResult(BaseModel):
    """单个 source 的执行结果摘要."""

    model_config = ConfigDict(extra="forbid")

    source: SearchSource
    status: RetrievalStatus
    candidate_count: int = 0
    error: str | None = None
    duration_ms: int = 0


class RetrievalRun(BaseModel):
    """一次检索运行的完整结果 (SOP §6.4 + S61 + S64)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    project_id: str
    query_plan: QueryPlan
    sources: list[SearchSource]
    source_results: list[SourceResult] = Field(default_factory=list)
    started_at: str
    finished_at: str | None = None
    status: RetrievalStatus = "running"
    total_candidates: int = 0
    imported_count: int = 0
    errors: list[str] = Field(default_factory=list)
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    # S61: 增强检索产物, 默认 None/0 不破坏旧调用
    gap_report: dict | None = Field(default=None)
    retry_round: int = Field(default=0)
    # S64: 候选清洗 + WebSearch 兜底 + 角色分类 + 模块矩阵
    clean_summary: dict | None = Field(default=None)
    web_datasets: list[dict] = Field(default_factory=list)
    literature_roles: list[dict] = Field(default_factory=list)
    module_matrix: dict | None = Field(default=None)


class RetrievalSummaryResponse(BaseModel):
    """GET /retrieval/summary 响应 (SOP §13.2)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    last_run_id: str | None = None
    last_run_at: str | None = None
    source_success: dict[str, int] = Field(default_factory=dict)
    source_failure: dict[str, int] = Field(default_factory=dict)
    paper_candidates: int = 0
    dataset_candidates: int = 0
    repo_candidates: int = 0
    duplicate_candidates: int = 0
    imported_candidates: int = 0
    last_errors: list[str] = Field(default_factory=list)
    total_runs: int = 0


# ---------- 导入 ---------- #


class RetrievalImportRequest(BaseModel):
    """POST /retrieval/import 请求体 (SOP §13.3)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    candidate_ids: list[str] = Field(default_factory=list)
    workspace_lane: Literal["system_found", "user_preferred"] = "system_found"
    auto_verify: bool = False


class RetrievalImportResponse(BaseModel):
    """POST /retrieval/import 响应."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    imported: int = 0
    skipped_duplicates: int = 0
    skipped_rejected: int = 0
    evidence_ids: list[str] = Field(default_factory=list)
    skipped_evidence_ids: list[str] = Field(default_factory=list)
    message: str = ""

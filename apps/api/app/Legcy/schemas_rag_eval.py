"""Session 34: RAG 面试级检索评估与 Hybrid/Rerank schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Retrieval Candidate (extends S14 RetrievalCandidate for RAG pipeline)
# ---------------------------------------------------------------------------


class RetrievalCandidate(BaseModel):
    """RAG pipeline 统一候选形态，含 sparse/dense/fused/rerank 多层评分."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    project_id: str
    kind: Literal["paper", "dataset", "repo"]
    title: str
    url: str | None = None
    source: str
    query_id: str
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

    # RAG pipeline scores
    sparse_score: float = Field(default=0.0, ge=0.0, le=1.0)
    dense_score: float = Field(default=0.0, ge=0.0, le=1.0)
    fused_score: float = Field(default=0.0, ge=0.0, le=1.0)
    rerank_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Metadata for explainability
    matched_keywords: list[str] = Field(default_factory=list)
    evidence_potential: Literal["high", "medium", "low"] = "medium"
    url_verified: bool = False
    url_verified_at: str | None = None
    rerank_reasons: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RAG Pipeline Config
# ---------------------------------------------------------------------------


class RagPipelineConfig(BaseModel):
    """RAG Pipeline 配置（可在面试中展示为可配置的超参数）."""

    model_config = ConfigDict(extra="forbid")

    # Retrieval
    top_k_sparse: int = Field(default=20, ge=1, le=100)
    top_k_dense: int = Field(default=20, ge=1, le=100)
    top_k_fused: int = Field(default=30, ge=1, le=100)
    top_k_final: int = Field(default=10, ge=1, le=50)

    # RRF Fusion
    rrf_k: int = Field(default=60, ge=1, le=200)

    # Rerank weights
    w_keyword_match: float = Field(default=0.35, ge=0.0, le=1.0)
    w_url_verified: float = Field(default=0.20, ge=0.0, le=1.0)
    w_reproducibility: float = Field(default=0.25, ge=0.0, le=1.0)
    w_type_coverage: float = Field(default=0.10, ge=0.0, le=1.0)
    w_recency: float = Field(default=0.10, ge=0.0, le=1.0)

    # Thresholds
    min_keyword_overlap: float = Field(default=0.3, ge=0.0, le=1.0)
    min_rerank_score: float = Field(default=0.1, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# RAG Evaluation Report
# ---------------------------------------------------------------------------


class FailureCase(BaseModel):
    """评估中发现的失败案例."""

    model_config = ConfigDict(extra="forbid")

    case_type: Literal["no_dataset", "no_repo", "url_unverified", "low_relevance", "type_imbalance"]
    description: str
    affected_candidates: list[str] = Field(default_factory=list)


class RagEvalReport(BaseModel):
    """RAG 评估报告，用于面试展示和自动化回归."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    run_id: str

    # Recall metrics
    recall_at_5: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_10: float = Field(default=0.0, ge=0.0, le=1.0)
    recall_at_20: float = Field(default=0.0, ge=0.0, le=1.0)

    # Ranking metrics
    mrr: float = Field(default=0.0, ge=0.0, le=1.0)

    # Citation / evidence metrics
    citation_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_precision: float = Field(default=0.0, ge=0.0, le=1.0)

    # Quality metrics
    url_verified_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    candidate_to_evidence_rate: float = Field(default=0.0, ge=0.0, le=1.0)

    # Type coverage
    paper_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    dataset_coverage: float = Field(default=0.0, ge=0.0, le=1.0)
    repo_coverage: float = Field(default=0.0, ge=0.0, le=1.0)

    # Failures
    failure_cases: list[FailureCase] = Field(default_factory=list)

    # Meta
    evaluated_at: str
    config_snapshot: RagPipelineConfig | None = None


# ---------------------------------------------------------------------------
# Request / Response for API
# ---------------------------------------------------------------------------


class RagPipelineRequest(BaseModel):
    """POST /rag/pipeline 请求体."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    config: RagPipelineConfig | None = None
    query_plan_override: dict | None = None


class RagPipelineResponse(BaseModel):
    """POST /rag/pipeline 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    run_id: str
    candidates: list[RetrievalCandidate] = Field(default_factory=list)
    eval_report: RagEvalReport | None = None
    status: Literal["completed", "partial", "failed"]
    message: str = ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_RAG_CONFIG = RagPipelineConfig()

# 关键词匹配阈值
KEYWORD_MATCH_THRESHOLD = 0.3
"""Session 50: RAG Evaluation schemas.

评估指标:
- RetrievalMetrics: 检索质量 (Recall@5, MRR, NDCG@5, Hit Rate)
- AnswerMetrics: 回答质量 (Citation Precision, Evidence Coverage, Unsupported Claim Rate, Faithfulness)
- SystemMetrics: 系统质量 (latency p50/p95, total_questions, fallback_rate)

评估流程:
- RagEvalItem: 单个 question 的评估结果
- RagEvalReport: 一组 questions 的聚合报告
- baseline_diff: 与基线的 diff
- regressions: 退化的指标列表
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RetrievalMode = Literal["llm", "fallback"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- Retrieval metrics ---------- #


class RetrievalMetrics(BaseModel):
    """检索质量指标."""

    model_config = ConfigDict(extra="forbid")

    recall_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    hit_rate: float = 0.0


# ---------- Answer metrics ---------- #


class AnswerMetrics(BaseModel):
    """回答质量指标."""

    model_config = ConfigDict(extra="forbid")

    citation_precision: float = 0.0
    evidence_coverage: float = 0.0
    unsupported_claim_rate: float = 0.0
    faithfulness: float = 0.0


# ---------- System metrics ---------- #


class SystemMetrics(BaseModel):
    """系统质量指标."""

    model_config = ConfigDict(extra="forbid")

    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0
    total_questions: int = 0
    fallback_rate: float = 0.0


# ---------- Per-item evaluation ---------- #


class RagEvalItem(BaseModel):
    """单个 question 的评估结果."""

    model_config = ConfigDict(extra="forbid")

    question_id: str
    paper_id: str
    question: str
    retrieved_chunks: list[str] = Field(default_factory=list)
    cited_chunks: list[str] = Field(default_factory=list)
    answer: str = ""
    retrieval_metrics: RetrievalMetrics = Field(default_factory=RetrievalMetrics)
    answer_metrics: AnswerMetrics = Field(default_factory=AnswerMetrics)
    latency_ms: float = 0.0
    retrieval_mode: RetrievalMode = "llm"


# ---------- Aggregated report ---------- #


class RagEvalReport(BaseModel):
    """RAG 评估报告 (聚合)."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: datetime = Field(default_factory=_utcnow)
    items: list[RagEvalItem] = Field(default_factory=list)
    aggregate_retrieval: RetrievalMetrics = Field(default_factory=RetrievalMetrics)
    aggregate_answer: AnswerMetrics = Field(default_factory=AnswerMetrics)
    aggregate_system: SystemMetrics = Field(default_factory=SystemMetrics)
    baseline_diff: dict = Field(default_factory=dict)
    regressions: list[str] = Field(default_factory=list)


# ---------- Run / baseline request models ---------- #


class RagEvalRunRequest(BaseModel):
    """POST /eval/run 请求体."""

    model_config = ConfigDict(extra="forbid")

    fixtures_path: str | None = None
    scope: Literal["all_papers", "accepted_papers", "specific"] = "all_papers"
    paper_ids: list[str] | None = None
    llm_mock: bool = False  # True 时跳过真实 LLM, 用 heuristic mock


class RagEvalRunResponse(BaseModel):
    """POST /eval/run 响应 (与 RagEvalReport 一致, 保持简洁)."""

    model_config = ConfigDict(extra="forbid")

    report: RagEvalReport


class RagEvalSeedLibraryRequest(BaseModel):
    """POST /eval/seed-library 请求体."""

    model_config = ConfigDict(extra="forbid")

    fixtures_path: str | None = None


class RagEvalSeedLibraryResponse(BaseModel):
    """POST /eval/seed-library 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    paper_count: int
    chunk_count: int
    message: str = ""


__all__ = [
    "AnswerMetrics",
    "RagEvalItem",
    "RagEvalReport",
    "RagEvalRunRequest",
    "RagEvalRunResponse",
    "RagEvalSeedLibraryRequest",
    "RagEvalSeedLibraryResponse",
    "RetrievalMetrics",
    "RetrievalMode",
    "SystemMetrics",
]

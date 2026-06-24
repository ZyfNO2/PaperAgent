"""Session 47: Paper RAG retrieval & QA schemas.

参考 SOP §3.1：
- EvidenceRef: 一个被引用 chunk 的具体出处 + 命中分
- PaperRAGAnswer: 整轮问答返回 (answer + evidence_refs + unsupported_claims + confidence)

设计约束：
- answer 没命中时必须明说 (不能编)
- evidence_refs 与 unsupported_claims 互不重叠 (ref 必须真在 retrieved chunks 里)
- retrieval_mode 区分 llm / fallback (下游 UI 用)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SupportType = Literal["direct", "indirect", "background", "contradiction"]
RetrievalMode = Literal["llm", "fallback"]
AskScope = Literal["all_papers", "accepted_papers", "specific"]


class EvidenceRef(BaseModel):
    """引用一个 chunk 的具体出处."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    chunk_id: str
    page_start: int | None = None
    page_end: int | None = None
    quote: str = Field(default="", max_length=200)
    support_type: SupportType = "direct"
    score: float = 0.0


class PaperRAGAnswer(BaseModel):
    """整轮问答的输出."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    evidence_refs: list[EvidenceRef] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    used_papers: list[str] = Field(default_factory=list)
    retrieval_mode: RetrievalMode = "llm"


class PaperRAGAskRequest(BaseModel):
    """POST /ask 请求体."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=2)
    scope: AskScope = "all_papers"
    paper_ids: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class PaperIndexRequest(BaseModel):
    """POST /{paper_id}/index 请求体."""

    model_config = ConfigDict(extra="forbid")

    force: bool = False


class PaperIndexResponse(BaseModel):
    """POST /{paper_id}/index 响应."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    chunk_count: int = 0
    indexed: int = 0  # 本次新索引的 chunk 数 (跳过已索引的)
    skipped: int = 0
    duration_ms: int = 0


__all__ = [
    "AskScope",
    "EvidenceRef",
    "PaperIndexRequest",
    "PaperIndexResponse",
    "PaperRAGAnswer",
    "PaperRAGAskRequest",
    "RetrievalMode",
    "SupportType",
]
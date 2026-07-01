"""Session 60: Local RAG minimal-loop schemas.

4 端点:
- POST /manual                → ManualIngestRequest / ManualIngestResponse
- POST /index                 → ProjectIndexRequest / ProjectIndexResponse
- GET  /index/status          → IndexStatusResponse
- POST /local-ask             → LocalAskRequest / LocalAskResponse

约束:
- extra="forbid"
- 不复用前端类型
- 字段固定, 不允许悄悄吞掉多余字段
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Manual ingest (Session 60 M1)
# ---------------------------------------------------------------------------


class ManualIngestRequest(BaseModel):
    """POST /manual 请求体.

    用户手动提交文献标题 + 文本 (粘贴的摘要 / 笔记 / 整段文字).
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=10)
    url: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list)


class ManualIngestResponse(BaseModel):
    """POST /manual 响应.

    status: "ingested" / "duplicate" / "failed"
    parse_status: "parsed" / "skipped" / "failed" / "pending"
    """

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    status: str
    parse_status: str
    chunk_count: int
    is_duplicate: bool = False
    message: str = ""


# ---------------------------------------------------------------------------
# Project-wide index (Session 60 M2)
# ---------------------------------------------------------------------------


class ProjectIndexRequest(BaseModel):
    """POST /index 请求体 (整个 project)."""

    model_config = ConfigDict(extra="forbid")

    force: bool = False
    paper_ids: list[str] | None = None


class ProjectIndexResponse(BaseModel):
    """POST /index 响应."""

    model_config = ConfigDict(extra="forbid")

    chunk_count: int
    indexed: int
    skipped: int
    duration_ms: int
    paper_count: int
    message: str = ""


class IndexStatusResponse(BaseModel):
    """GET /index/status 响应.

    汇总当前 project 的索引状态.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total_papers: int
    total_chunks: int
    indexed_chunks: int
    unindexed_chunks: int
    embedding_provider: str
    papers: list[PaperIndexStatusEntry] = Field(default_factory=list)


class PaperIndexStatusEntry(BaseModel):
    """Index status 中的单条 paper 摘要."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    title: str
    chunk_count: int
    indexed_chunk_count: int
    is_indexed: bool


# ---------------------------------------------------------------------------
# Local RAG ask (Session 60 M3)
# ---------------------------------------------------------------------------


class LocalAskRequest(BaseModel):
    """POST /local-ask 请求体.

    只基于本地 embedding 索引检索, 不依赖 Evidence Ledger.
    """

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)
    paper_ids: list[str] | None = None


class LocalEvidenceRef(BaseModel):
    """本地问答 evidence 引用."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    chunk_id: str
    section_title: str | None = None
    chunk_type: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    quote: str
    score: float


class LocalAskResponse(BaseModel):
    """POST /local-ask 响应.

    retrieval_mode: "local_embedding" / "no_hit"
    confidence: 0-1 (heuristic, no LLM dependency)
    """

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    evidence_refs: list[LocalEvidenceRef] = Field(default_factory=list)
    retrieval_mode: str
    confidence: float = 0.0
    no_hit: bool = False
    message: str = ""
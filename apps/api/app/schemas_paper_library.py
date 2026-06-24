"""Paper Library schemas (Session 46).

PaperRecord / PaperChunk 数据模型:
- PaperRecord: 入库一篇论文后的统一元数据
- PaperChunk: 切块后的单个 chunk, 包含章节路径 / token 估算 / chunk_type

入库即 pending, 不自动进报告; 论文库负责全文存储和切块, 检索和问答留给 S47.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceMode = Literal["arxiv_download", "local_upload"]
ParseStatus = Literal["pending", "parsed", "failed", "skipped"]
MetadataStatus = Literal["resolved", "partial", "missing"]
ChunkType = Literal[
    "title",
    "abstract",
    "introduction",
    "related_work",
    "method",
    "experiment",
    "result",
    "limitation",
    "conclusion",
    "reference",
    "unknown",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- 核心模型 ---------- #


class PaperRecord(BaseModel):
    """入库一篇论文的元数据 + 状态."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    project_id: str
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    pdf_path: str | None = None
    sha256: str | None = None
    source_mode: SourceMode
    parse_status: ParseStatus = "pending"
    page_count: int = 0
    chunk_count: int = 0
    metadata_status: MetadataStatus = "missing"
    created_at: datetime = Field(default_factory=_utcnow)
    # 复用 EvidenceItem.evidence_id, 如果该论文同时入了 Evidence Ledger
    evidence_id: str | None = None


class PaperChunk(BaseModel):
    """切块后的单个 chunk (S47 embedding 时填充 embedding_id)."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    paper_id: str
    project_id: str
    section_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    page_start: int | None = None
    page_end: int | None = None
    text: str
    token_count: int = 0
    chunk_type: ChunkType = "unknown"
    embedding_id: str | None = None


# ---------- 请求 / 响应模型 ---------- #


class ArxivIngestRequest(BaseModel):
    """POST /paper-library/arxiv 请求体."""

    model_config = ConfigDict(extra="forbid")

    arxiv_id_or_url: str = Field(min_length=3)
    # 允许测试/前端覆盖 metadata; 通常不传
    override_title: str | None = None


class ArxivIngestResponse(BaseModel):
    """POST /paper-library/arxiv 响应."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    status: str  # "ingested" / "duplicate" / "failed"
    parse_status: ParseStatus
    chunk_count: int
    evidence_id: str | None = None
    is_duplicate: bool = False
    message: str = ""


class LocalUploadIngestRequest(BaseModel):
    """POST /paper-library/upload 请求体."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1)
    content_b64: str = Field(min_length=1)
    mime: str | None = None


class LocalUploadIngestResponse(BaseModel):
    """POST /paper-library/upload 响应."""

    model_config = ConfigDict(extra="forbid")

    paper_id: str
    parse_status: ParseStatus
    chunk_count: int
    evidence_id: str | None = None
    is_duplicate: bool = False
    message: str = ""


class PaperListResponse(BaseModel):
    """GET /paper-library 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    papers: list[PaperRecord]
    total_chunks: int
    total_papers: int


class PaperDetailChunkPreview(BaseModel):
    """GET /paper-library/{paper_id} 响应中的 chunk 预览."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    section_title: str | None = None
    section_path: list[str] = Field(default_factory=list)
    chunk_type: ChunkType = "unknown"
    token_count: int = 0
    text_preview: str  # 截断后的前 ~200 字符


class PaperDetailResponse(BaseModel):
    """GET /paper-library/{paper_id} 响应."""

    model_config = ConfigDict(extra="forbid")

    paper: PaperRecord
    chunks: list[PaperDetailChunkPreview]
    full_text_excerpt: str = ""  # 全文前 1500 字
    chunk_total: int

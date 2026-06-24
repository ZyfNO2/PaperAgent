"""Evidence schemas: 证据工作台数据模型 (SOP §5.5).

EvidenceItem 统一表示 paper / dataset / repo / note / custom 五种证据,
通过 ``evidence_type`` 区分, 通过 ``source_mode`` 区分 auto_search / manual / upload.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceType = Literal["paper", "dataset", "repo", "note", "custom", "paper_library_chunk"]
SourceMode = Literal["auto_search", "manual", "upload", "import", "assistant_intake", "paper_rag"]
ReviewStatus = Literal["pending", "accepted", "core", "background", "rejected", "needs_check"]
WorkspaceLane = Literal["user_preferred", "system_found", "selected", "rejected"]
RawInputType = Literal["url", "text", "github", "dataset_page", "paper_page", "image", "pdf", "paper_chunk"]
VerificationStatus = Literal["unverified", "verified", "failed", "partial", "skipped"]
VerificationSource = Literal["http", "arxiv", "openalex", "github", "huggingface", "kaggle", "manual", "none"]
# Session 48: paper_library_chunk 引用类型
SupportType = Literal["direct", "indirect", "background", "contradiction"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------- 手动添加请求 ---------- #


class PaperManualCreate(BaseModel):
    """POST /evidence/papers/manual  请求体."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    url: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    user_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "pending"


class DatasetManualCreate(BaseModel):
    """POST /evidence/datasets/manual 请求体."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    scale: str | None = None
    license: str | None = None
    download: str | None = None
    modality: list[str] = Field(default_factory=list)
    annotation: str | None = None
    user_note: str | None = None
    review_status: ReviewStatus = "pending"


class RepoManualCreate(BaseModel):
    """POST /evidence/repos/manual 请求体."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    repository_url: str | None = None
    paper_title: str | None = None
    license: str | None = None
    has_readme: bool = False
    has_env_file: bool = False
    has_training_script: bool = False
    has_eval_script: bool = False
    user_note: str | None = None
    review_status: ReviewStatus = "pending"


# ---------- 审核操作 ---------- #


class ReviewUpdate(BaseModel):
    """PATCH /evidence/{id}/review  请求体."""

    model_config = ConfigDict(extra="forbid")

    review_status: ReviewStatus
    user_note: str | None = None


# ---------- 证据实体 ---------- #


class EvidenceItem(BaseModel):
    """证据池中的一条 (SOP §5.5)."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    project_id: str
    evidence_type: EvidenceType
    source_mode: SourceMode

    # 通用字段
    title: str = Field(min_length=1)
    url: str | None = None
    year: int | None = None
    user_note: str | None = None
    tags: list[str] = Field(default_factory=list)
    review_status: ReviewStatus = "pending"
    created_at: datetime = Field(default_factory=_utcnow)

    # 论文专属
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    arxiv_id: str | None = None
    abstract: str | None = None
    paper_type: Literal["survey", "baseline_method", "application", "dataset_paper", "benchmark", "case_study", "irrelevant", "unknown"] = "unknown"

    # 数据集专属
    scale: str | None = None
    license: str | None = None
    download: str | None = None
    modality: list[str] = Field(default_factory=list)
    annotation: str | None = None
    dataset_status: Literal["ready", "needs_preprocess", "needs_permission", "weak_match", "unverified", "invalid"] = "unverified"

    # Repo 专属
    paper_title: str | None = None
    has_readme: bool = False
    has_env_file: bool = False
    has_training_script: bool = False
    has_eval_script: bool = False
    has_pretrained_weight: bool = False
    repo_type: Literal["official", "reproduction", "baseline_framework", "demo_only", "not_reproducible", "unknown"] = "unknown"

    # 评分
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)

    # Session 9 §4.1: 双栏工作台 + Agent Card Intake 字段
    workspace_lane: WorkspaceLane = "system_found"
    workspace_order: int | None = None
    paired_with: list[str] = Field(default_factory=list)

    raw_input_type: RawInputType | None = None
    raw_input_ref: str | None = None
    extraction_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    extraction_warnings: list[str] = Field(default_factory=list)

    # Session 10 §4.1: 多源轻验证与 URL Verified 字段
    url_verified: bool | None = None
    verification_status: VerificationStatus = "unverified"
    verification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification_source: VerificationSource = "none"
    verification_checked_at: datetime | None = None
    verification_warnings: list[str] = Field(default_factory=list)
    verification_metadata: dict = Field(default_factory=dict)

    # Session 13 §7.1: Skill 来源
    created_by_skill: str | None = None
    scored_by_skill: str | None = None
    validated_by_skill: str | None = None

    # Session 15 §16: 来源 materials / parse 信息
    from_material_id: str | None = None
    parse_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    page_refs: list[str] = Field(default_factory=list)

    # Session 48 §3.1: paper_library_chunk 类型扩展 (向后兼容, 全 Optional)
    paper_id: str | None = None
    chunk_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    quote: str | None = Field(default=None, max_length=2000)
    support_type: SupportType | None = None


# ---------- Session 10: Verification 模型 (§4.2) ---------- #


class VerificationResult(BaseModel):
    """单条 evidence 的验证结果."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    evidence_type: str
    ok: bool
    url_verified: bool
    verification_status: VerificationStatus
    verification_confidence: float
    verification_source: VerificationSource
    normalized_url: str | None = None
    metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    checked_at: str


class VerificationSummary(BaseModel):
    """批量验证摘要 (§6.3)."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    total: int
    verified: int
    partial: int
    failed: int
    skipped: int
    avg_confidence: float
    high_risk_items: list[VerificationResult] = Field(default_factory=list)


class VerificationBatchRequest(BaseModel):
    """POST /evidence/verify 请求体 (§6.2)."""

    model_config = ConfigDict(extra="forbid")

    scope: Literal[
        "all", "paper", "dataset", "repo", "note",
        "assistant_intake", "user_preferred", "selected",
    ] = "all"
    include_rejected: bool = False
    include_pending: bool = True
    refresh: bool = False


class ManualVerificationUpdate(BaseModel):
    """PATCH /evidence/{id}/verification 请求体 (§6.4)."""

    model_config = ConfigDict(extra="forbid")

    verification_status: VerificationStatus
    verification_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    verification_source: VerificationSource = "manual"
    reason: str | None = None


# ---------- 证据池响应 ---------- #


class EvidenceLedgerResponse(BaseModel):
    """GET /evidence  响应: 一个 project 的证据池."""

    project_id: str
    papers: list[EvidenceItem] = Field(default_factory=list)
    datasets: list[EvidenceItem] = Field(default_factory=list)
    repos: list[EvidenceItem] = Field(default_factory=list)
    notes: list[EvidenceItem] = Field(default_factory=list)

    paper_count: int = 0
    dataset_count: int = 0
    repo_count: int = 0
    accepted_count: int = 0
    core_count: int = 0
    rejected_count: int = 0
    needs_check_count: int = 0


class EvidenceActionResponse(BaseModel):
    """POST/PATCH/DELETE 证据后返回: 成功 + 当前 evidence_item + 池摘要."""

    ok: bool
    evidence_id: str
    evidence: EvidenceItem | None = None
    ledger_summary: EvidenceLedgerResponse
    message: str = ""

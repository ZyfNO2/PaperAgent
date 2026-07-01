"""Session 15: 全文资料与图片 / PDF / 网页卡片化 schema.

非结构化资料 -> MaterialItem -> DraftEvidenceCard -> EvidenceItem
所有解析结果默认 pending, 走用户审核后再进入 Evidence Ledger.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


MaterialSourceType = Literal[
    "pdf",
    "image",
    "screenshot",
    "web_text",
    "url_note",
    "manual_note",
]

MaterialParseStatus = Literal["pending", "parsed", "failed", "skipped"]
DraftStatus = Literal["draft", "edited", "imported", "rejected"]
DraftSuggestedType = Literal["paper", "dataset", "repo", "note", "custom"]


# ---------- 资料项 ---------- #


class MaterialItem(BaseModel):
    """一份用户提交的非结构化资料 (SOP §6.2)."""

    model_config = ConfigDict(extra="forbid")

    material_id: str
    project_id: str
    source_type: MaterialSourceType
    filename: str | None = None
    original_url: str | None = None
    title: str | None = None
    storage_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    text_excerpt: str | None = None
    page_count: int | None = None
    page_range: str | None = None
    created_at: str
    parse_status: MaterialParseStatus = "pending"
    parse_confidence: float | None = None
    parse_warnings: list[str] = Field(default_factory=list)
    user_note: str | None = None
    metadata: dict = Field(default_factory=dict)


# ---------- 草稿卡片 ---------- #


class DraftEvidenceCard(BaseModel):
    """从资料生成的待确认草稿 (SOP §6.3)."""

    model_config = ConfigDict(extra="forbid")

    draft_card_id: str
    project_id: str
    material_id: str
    suggested_type: DraftSuggestedType
    title: str
    summary: str
    extracted_claims: list[str] = Field(default_factory=list)
    extracted_entities: list[str] = Field(default_factory=list)
    possible_url: str | None = None
    possible_doi: str | None = None
    possible_arxiv_id: str | None = None
    source_excerpt: str | None = None
    page_refs: list[str] = Field(default_factory=list)
    extraction_confidence: float = 0.0
    warnings: list[str] = Field(default_factory=list)
    status: DraftStatus = "draft"
    created_at: str
    updated_at: str


# ---------- 请求 / 响应 ---------- #


class MaterialTextRequest(BaseModel):
    """POST /materials/text 请求体."""

    model_config = ConfigDict(extra="forbid")

    source_type: MaterialSourceType
    title: str | None = None
    text: str = Field(default="", max_length=100_000)
    url: str | None = None
    user_note: str | None = None


class MaterialUploadRequest(BaseModel):
    """POST /materials/upload 请求体 (base64 形式, 避免 multipart 依赖)."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1)
    content_b64: str = Field(default="", description="文件内容的 base64 编码")
    mime: str | None = None
    user_note: str | None = None
    page_range: str | None = None
    preferred_type: DraftSuggestedType | None = None
    auto_build_cards: bool = True
    material_id: str | None = Field(default=None, description="测试可注入以与 pdf_parser.set_default_text 配对")


class MaterialUploadResponse(BaseModel):
    """POST /materials/upload 响应."""

    model_config = ConfigDict(extra="forbid")

    material: MaterialItem
    draft_cards: list[DraftEvidenceCard] = Field(default_factory=list)
    message: str = ""


class MaterialBuildCardsRequest(BaseModel):
    """POST /materials/{id}/cards 请求体."""

    model_config = ConfigDict(extra="forbid")

    max_cards: int = Field(default=3, ge=1, le=10)
    preferred_type: DraftSuggestedType | None = None
    user_note: str | None = None


class MaterialListResponse(BaseModel):
    """GET /materials 响应."""

    model_config = ConfigDict(extra="forbid")

    project_id: str
    materials: list[MaterialItem] = Field(default_factory=list)
    drafts: list[DraftEvidenceCard] = Field(default_factory=list)


class DraftCardUpdate(BaseModel):
    """PATCH /materials/cards/{id} 请求体."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    summary: str | None = None
    suggested_type: DraftSuggestedType | None = None
    possible_url: str | None = None
    possible_doi: str | None = None
    possible_arxiv_id: str | None = None
    status: DraftStatus | None = None
    user_note: str | None = None


class MaterialImportRequest(BaseModel):
    """POST /materials/cards/import 请求体."""

    model_config = ConfigDict(extra="forbid")

    draft_card_ids: list[str] = Field(default_factory=list)
    workspace_lane: Literal["system_found", "user_preferred"] = "user_preferred"
    auto_verify: bool = False


class MaterialImportResponse(BaseModel):
    """POST /materials/cards/import 响应 (SOP §6.4)."""

    model_config = ConfigDict(extra="forbid")

    imported: int = 0
    skipped: int = 0
    evidence_ids: list[str] = Field(default_factory=list)
    skipped_draft_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    message: str = ""
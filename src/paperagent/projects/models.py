from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class MemoryScope(StrEnum):
    LONG_TERM = "long_term"
    WORKING = "working"


class MemoryStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryCategory(StrEnum):
    OBJECTIVE = "objective"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    FINDING = "finding"
    NEXT_ACTION = "next_action"


class TailoringDecision(StrEnum):
    GO = "GO"
    REVISE = "REVISE"
    NO_GO = "NO-GO"
    BLOCKED = "BLOCKED"


class ResearchProject(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    name: str
    research_question: str
    created_at: datetime
    updated_at: datetime


class CitationLocator(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    ingestion_version: int = Field(ge=1)
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    quote: str | None = None


class PaperVersion(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    project_id: str
    title: str
    source_path: Path
    content_sha256: str
    ingestion_version: int = Field(ge=1)
    media_type: str
    ingested_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceUnit(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit_id: str
    project_id: str
    paper_id: str
    ingestion_version: int = Field(ge=1)
    content: str
    section: str | None = None
    page: int | None = Field(default=None, ge=1)
    paragraph: int | None = Field(default=None, ge=1)
    keywords: tuple[str, ...] = ()
    locator: CitationLocator


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit: EvidenceUnit
    score: float = Field(ge=0)
    lexical_score: float = Field(ge=0)
    semantic_score: float = Field(ge=0)
    paper_title: str


class ProjectMemoryEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_id: str
    project_id: str
    scope: MemoryScope
    category: MemoryCategory
    content: str
    evidence_unit_ids: tuple[str, ...] = ()
    status: MemoryStatus
    proposed_at: datetime
    reviewed_at: datetime | None = None
    review_note: str | None = None


class IngestionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper: PaperVersion
    evidence_units: tuple[EvidenceUnit, ...]


class TailoringModule(BaseModel):
    model_config = ConfigDict(frozen=True)

    paper_id: str
    paper_title: str
    evidence_unit_ids: tuple[str, ...]
    proposed_role: str
    status: Literal["verified", "proposed", "unknown"]


class TailoringPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    decision: TailoringDecision
    reason_code: str | None = None
    baseline_paper_id: str | None = None
    baseline_evidence_unit_ids: tuple[str, ...] = ()
    hypothesis: str
    modules: tuple[TailoringModule, ...] = ()
    citations: tuple[CitationLocator, ...] = ()
    risks: tuple[str, ...] = ()

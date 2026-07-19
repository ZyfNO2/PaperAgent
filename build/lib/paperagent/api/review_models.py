from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field

from paperagent.schemas.base import FrozenModel


class ReviewDecision(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PaperReviewUpdate(FrozenModel):
    decision: ReviewDecision
    favorite: bool = False
    expected_version: int = Field(ge=0)


class PaperReview(FrozenModel):
    task_id: str
    paper_id: str
    decision: ReviewDecision = ReviewDecision.PENDING
    favorite: bool = False
    version: int = Field(default=0, ge=0)


class ReviewPaperCard(FrozenModel):
    task_id: str
    paper_id: str
    title: str
    locator: str
    summary: str
    verification_status: str
    gap_ids: list[str] = Field(default_factory=list)
    decision: ReviewDecision = ReviewDecision.PENDING
    favorite: bool = False
    review_version: int = Field(default=0, ge=0)


class PaperCardPage(FrozenModel):
    task_id: str
    items: list[ReviewPaperCard]
    next_cursor: str | None = None


ExportFormat = Literal["json", "markdown", "bibtex"]
ExportSelection = Literal["accepted", "favorite", "all"]


class ExportManifest(FrozenModel):
    task_id: str
    format: ExportFormat
    selection: ExportSelection
    item_count: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExportDocument(FrozenModel):
    manifest: ExportManifest
    media_type: str
    filename: str
    content: str

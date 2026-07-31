from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator

AcademicChannel = Literal["exact", "lexical", "dense", "visual"]
AcademicQueryKind = Literal[
    "identity",
    "method",
    "figure",
    "table",
    "equation",
    "comparison",
    "tailoring",
]
AcademicObjectType = Literal[
    "document",
    "page",
    "section",
    "paragraph",
    "figure",
    "caption",
    "table",
    "table_cell",
    "equation",
    "algorithm",
    "reference",
    "citation",
    "repository_link",
]
RetrievalRoundKind = Literal["primary", "corrective", "conflict"]
SufficiencyDecision = Literal["sufficient", "partial", "insufficient", "blocked"]


class FrozenAcademicModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class EvidenceLocatorView(FrozenAcademicModel):
    """PaperAgent's read-only view of PaperClaw's canonical locator.

    This is an internal Python 3.11 compatibility view, not a second wire
    contract.  Serialization at the repository seam is owned by PaperClaw.
    """

    schema_version: Literal["academic.v1"]
    paper_id: str
    version_id: str
    object_id: str
    page_number: int = Field(ge=1)
    object_type: AcademicObjectType
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    section_path: tuple[str, ...] = ()
    bounding_box: tuple[float, float, float, float] | None = None
    paragraph_index: int | None = Field(default=None, ge=0)
    line_range: tuple[int, int] | None = None
    table_row: int | None = Field(default=None, ge=0)
    table_column: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_coordinates(self) -> EvidenceLocatorView:
        if self.bounding_box is not None:
            x0, y0, x1, y1 = self.bounding_box
            if min(x0, y0) < 0 or x1 < x0 or y1 < y0:
                raise ValueError("invalid bounding_box")
        if self.line_range is not None:
            start, end = self.line_range
            if start < 0 or end < start:
                raise ValueError("invalid line_range")
        return self


# Source compatibility for the pre-freeze PaperAgent interface.
AcademicLocator = EvidenceLocatorView


class AcademicCandidate(FrozenAcademicModel):
    evidence_id: str
    locator: EvidenceLocatorView
    text: str
    score: float = Field(ge=0)
    provenance: Literal["extracted", "inferred"]
    channel_scores: dict[AcademicChannel, float] = Field(default_factory=dict)
    explanation: tuple[str, ...] = ()


class AcademicQueryPlan(FrozenAcademicModel):
    kind: AcademicQueryKind
    original_question: str
    rewritten_query: str
    exact_identifiers: tuple[str, ...] = ()
    channels: tuple[AcademicChannel, ...]
    object_types: tuple[AcademicObjectType, ...] = ()


class AcademicRetrievalRequest(FrozenAcademicModel):
    project_id: str
    query: str
    original_question: str
    kind: AcademicQueryKind
    round_kind: RetrievalRoundKind
    channels: tuple[AcademicChannel, ...]
    paper_ids: tuple[str, ...] = ()
    object_types: tuple[AcademicObjectType, ...] = ()
    section_scope: tuple[str, ...] = ()
    max_candidates: int = Field(default=10, ge=1, le=100)
    max_chars: int = Field(default=12_000, ge=1, le=100_000)


class AcademicRetrievalResult(FrozenAcademicModel):
    candidates: tuple[AcademicCandidate, ...]
    sufficiency: SufficiencyDecision
    reasons: tuple[str, ...]
    degraded_channels: tuple[AcademicChannel, ...]
    conflict_detected: bool
    trace_id: str
    trace_details: dict[str, object] = Field(default_factory=dict)


class AcademicEvidenceEntry(FrozenAcademicModel):
    evidence_id: str
    locator: EvidenceLocatorView
    status: Literal["accepted", "rejected", "conflicted"]
    supported_claims: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()


class AcademicEvidenceLedger(FrozenAcademicModel):
    entries: tuple[AcademicEvidenceEntry, ...]
    accepted_ids: tuple[str, ...]
    rejected_ids: tuple[str, ...]
    conflicted_ids: tuple[str, ...]

    @model_validator(mode="after")
    def validate_derived_ids(self) -> AcademicEvidenceLedger:
        expected = {
            "accepted": tuple(
                entry.evidence_id for entry in self.entries if entry.status == "accepted"
            ),
            "rejected": tuple(
                entry.evidence_id for entry in self.entries if entry.status == "rejected"
            ),
            "conflicted": tuple(
                entry.evidence_id for entry in self.entries if entry.status == "conflicted"
            ),
        }
        if self.accepted_ids != expected["accepted"]:
            raise ValueError("accepted_ids must be derived from entries")
        if self.rejected_ids != expected["rejected"]:
            raise ValueError("rejected_ids must be derived from entries")
        if self.conflicted_ids != expected["conflicted"]:
            raise ValueError("conflicted_ids must be derived from entries")
        return self


class AcademicRAGResult(FrozenAcademicModel):
    project_id: str
    query_plan: AcademicQueryPlan
    ledger: AcademicEvidenceLedger
    sufficiency: SufficiencyDecision
    reasons: tuple[str, ...]
    trace_ids: tuple[str, ...]
    rounds_used: dict[RetrievalRoundKind, int]
    stop_reason: str
    decomposition_strategy: str = "parallel"
    sub_query_ids: tuple[str, ...] = ()
    context_evidence_ids: tuple[str, ...] = ()
    generated_claims: tuple[str, ...] = ()
    citation_mismatches: tuple[str, ...] = ()
    retrieval_candidates: tuple[AcademicCandidate, ...] = ()
    retrieval_trace_details: tuple[dict[str, object], ...] = ()


@runtime_checkable
class AcademicEvidenceSource(Protocol):
    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult: ...

    def resolve(self, locator: EvidenceLocatorView) -> AcademicCandidate: ...

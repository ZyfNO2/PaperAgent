from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.common import ToolErrorRecord
from paperagent.schemas.plan import PreparedQuery


class SearchCandidate(FrozenModel):
    candidate_id: str
    query_id: str
    gap_id: str
    source_type: Literal["paper", "dataset", "repository", "web", "user_material"]
    title: str
    locator: str
    snippet: str
    provider: str = "fake_search"
    metadata: dict[str, str] = Field(default_factory=dict)


class RetrievalState(FrozenModel):
    round: int = Field(default=0, ge=0)
    max_rounds: int = Field(default=2, ge=1)
    prepared_queries: list[PreparedQuery] = Field(default_factory=list)
    completed_query_ids: list[str] = Field(default_factory=list)
    raw_candidates: list[SearchCandidate] = Field(default_factory=list)
    tool_errors: list[ToolErrorRecord] = Field(default_factory=list)
    budget_exhausted: bool = False

    @model_validator(mode="after")
    def validate_retrieval(self) -> RetrievalState:
        if self.round > self.max_rounds:
            raise ValueError("retrieval round exceeds max_rounds")
        if len(self.completed_query_ids) != len(set(self.completed_query_ids)):
            raise ValueError("completed query IDs must be unique")
        return self


class EvidenceConflict(FrozenModel):
    conflict_id: str
    evidence_ids: list[str]
    description: str


class EvidenceItem(FrozenModel):
    evidence_id: str
    source_type: Literal["paper", "dataset", "repository", "web", "user_material"]
    title: str
    locator: str
    retrieved_at: datetime
    verification_status: Literal["accepted", "rejected", "pending", "failed_verification"]
    supports_gap_ids: list[str]
    summary: str
    content_hash: str
    provider: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @property
    def stable_identifier(self) -> str:
        for key, prefix in (
            ("doi", "doi:"),
            ("arxiv_id", "arxiv:"),
            ("openalex_id", "openalex:"),
            ("semantic_scholar_id", "s2:"),
        ):
            value = self.metadata.get(key)
            if value:
                return f"{prefix}{value}"
        return self.locator


class EvidenceBundle(FrozenModel):
    items: list[EvidenceItem] = Field(default_factory=list)
    accepted_ids: list[str] = Field(default_factory=list)
    rejected_ids: list[str] = Field(default_factory=list)
    pending_ids: list[str] = Field(default_factory=list)
    failed_verification_ids: list[str] = Field(default_factory=list)
    coverage_by_gap: dict[str, int] = Field(default_factory=dict)
    conflicts: list[EvidenceConflict] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status_sets(self) -> EvidenceBundle:
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence IDs must be globally unique")
        sets = {
            "accepted": set(self.accepted_ids),
            "rejected": set(self.rejected_ids),
            "pending": set(self.pending_ids),
            "failed_verification": set(self.failed_verification_ids),
        }
        all_status_ids: list[str] = [item for values in sets.values() for item in values]
        if len(all_status_ids) != len(set(all_status_ids)):
            raise ValueError("each evidence ID must belong to exactly one status set")
        item_by_id = {item.evidence_id: item for item in self.items}
        for evidence_id, item in item_by_id.items():
            if evidence_id not in sets[item.verification_status]:
                raise ValueError(
                    f"evidence {evidence_id} missing from {item.verification_status} set"
                )
        unknown_ids = set(all_status_ids) - set(item_by_id)
        if unknown_ids:
            raise ValueError(f"status sets contain unknown evidence IDs: {sorted(unknown_ids)}")
        expected_coverage: dict[str, int] = {}
        for item in self.items:
            if item.verification_status == "accepted":
                for gap_id in item.supports_gap_ids:
                    expected_coverage[gap_id] = expected_coverage.get(gap_id, 0) + 1
        if self.coverage_by_gap != expected_coverage:
            raise ValueError("coverage_by_gap must count accepted evidence only")
        return self

    def accepted_items(self) -> list[EvidenceItem]:
        accepted = set(self.accepted_ids)
        return [item for item in self.items if item.evidence_id in accepted]

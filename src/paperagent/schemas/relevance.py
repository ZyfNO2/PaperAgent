from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel

EvidenceScope = Literal["direct", "indirect", "background_only", "irrelevant"]
GapSupportType = Literal[
    "direct_support",
    "indirect_support",
    "counter_evidence",
    "insufficient",
    "unrelated",
]


class ResearchContract(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    task_type: str | None = None
    domain: str | None = None
    dataset: str | None = None
    baseline_family: str | None = None
    target_metric: str | None = None
    intervention_types: list[str] = Field(default_factory=list)
    deployment_constraints: list[str] = Field(default_factory=list)
    research_claim: str | None = None
    positive_terms: list[str] = Field(default_factory=list)
    negative_terms: list[str] = Field(default_factory=list)
    required_gap_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unavailable_private_evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract(self) -> ResearchContract:
        if len(self.required_gap_ids) != len(set(self.required_gap_ids)):
            raise ValueError("required_gap_ids must be unique")
        return self


class LexicalRelevanceAssessment(FrozenModel):
    evidence_id: str
    lexical_score: float = Field(ge=0.0, le=1.0)
    matched_terms: list[str] = Field(default_factory=list)
    missing_mandatory_terms: list[str] = Field(default_factory=list)
    negative_matches: list[str] = Field(default_factory=list)
    decision: Literal["pass", "reject"]
    reason_codes: list[str] = Field(default_factory=list)


class RelevanceAssessment(FrozenModel):
    evidence_id: str
    task_match: bool
    domain_match: bool
    dataset_match: bool | None = None
    baseline_match: bool | None = None
    mechanism_match: bool | None = None
    constraint_match: bool | None = None
    evidence_scope: EvidenceScope
    relevance_score: float = Field(ge=0.0, le=1.0)
    decision: Literal["pass", "reject"]
    supporting_spans: list[str] = Field(default_factory=list)
    conflict_spans: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    assessment_source: Literal["deterministic", "fixture"] = "deterministic"

    @model_validator(mode="after")
    def validate_support(self) -> RelevanceAssessment:
        if (
            self.decision == "pass"
            and self.evidence_scope in {"direct", "indirect"}
            and not self.supporting_spans
        ):
            raise ValueError("accepted direct or indirect relevance requires a supporting span")
        if self.decision == "reject" and self.evidence_scope not in {
            "background_only",
            "irrelevant",
        }:
            raise ValueError("rejected relevance must be background_only or irrelevant")
        return self


class GapSupportAssessment(FrozenModel):
    evidence_id: str
    gap_id: str
    support_type: GapSupportType
    supported_claim: str | None = None
    supporting_span_hash: str | None = None
    checklist_results: dict[str, bool] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    decision: Literal["accept", "reject"]

    @model_validator(mode="after")
    def validate_binding(self) -> GapSupportAssessment:
        if self.decision == "accept" and self.support_type not in {
            "direct_support",
            "indirect_support",
            "counter_evidence",
        }:
            raise ValueError("accepted gap binding requires a supporting support_type")
        if self.decision == "accept" and not self.supporting_span_hash:
            raise ValueError("accepted gap binding requires supporting_span_hash")
        return self


class EvidenceLedgerEntry(FrozenModel):
    evidence_id: str
    identity_verified: bool
    relevance_scope: EvidenceScope
    gap_supports: list[GapSupportAssessment] = Field(default_factory=list)
    supported_claims: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    accepted: bool
    rejection_reasons: list[str] = Field(default_factory=list)


class EvidenceLedger(FrozenModel):
    schema_version: Literal["0.1"] = "0.1"
    entries: list[EvidenceLedgerEntry] = Field(default_factory=list)
    accepted_ids: list[str] = Field(default_factory=list)
    rejected_ids: list[str] = Field(default_factory=list)
    coverage_by_gap: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ledger(self) -> EvidenceLedger:
        ids = [entry.evidence_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence ledger IDs must be unique")
        accepted = {entry.evidence_id for entry in self.entries if entry.accepted}
        rejected = {entry.evidence_id for entry in self.entries if not entry.accepted}
        if set(self.accepted_ids) != accepted:
            raise ValueError("accepted_ids must be derived from accepted ledger entries")
        if set(self.rejected_ids) != rejected:
            raise ValueError("rejected_ids must be derived from rejected ledger entries")
        coverage: dict[str, int] = {}
        for entry in self.entries:
            if not entry.accepted:
                continue
            for support in entry.gap_supports:
                if support.decision == "accept":
                    coverage[support.gap_id] = coverage.get(support.gap_id, 0) + 1
        if self.coverage_by_gap != coverage:
            raise ValueError("coverage_by_gap must be derived from accepted gap bindings")
        return self

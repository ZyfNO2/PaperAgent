from __future__ import annotations

import math
from collections import Counter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RetrievedEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    stable_identifier: str = Field(min_length=1)
    rank: int = Field(ge=1)
    context_tokens: int = Field(ge=0)
    cited: bool = False

    @model_validator(mode="after")
    def reject_blank_identifiers(self) -> RetrievedEvidence:
        if not self.evidence_id.strip() or not self.stable_identifier.strip():
            raise ValueError("evidence identifiers must be non-blank")
        return self


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    supporting_evidence_ids: tuple[str, ...] = ()
    critical: bool = False

    @model_validator(mode="after")
    def reject_blank_identifiers(self) -> ClaimAssessment:
        if not self.claim_id.strip():
            raise ValueError("claim ID must be non-blank")
        if any(not evidence_id.strip() for evidence_id in self.supporting_evidence_ids):
            raise ValueError("supporting evidence IDs must be non-blank")
        if len(set(self.supporting_evidence_ids)) != len(self.supporting_evidence_ids):
            raise ValueError("supporting evidence IDs must be unique per claim")
        return self


class RAGEvaluationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    relevant_identifiers: tuple[str, ...]
    retrieved: tuple[RetrievedEvidence, ...]
    claims: tuple[ClaimAssessment, ...]
    total_context_tokens: int = Field(ge=0)
    used_context_tokens: int = Field(ge=0)
    llm_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)
    terminal: Literal["succeeded", "blocked", "failed"]
    block_reason: str | None = None

    @model_validator(mode="after")
    def validate_contract(self) -> RAGEvaluationInput:
        if not self.case_id.strip():
            raise ValueError("case ID must be non-blank")
        if not self.relevant_identifiers:
            raise ValueError("at least one relevant identifier is required")
        if any(not identifier.strip() for identifier in self.relevant_identifiers):
            raise ValueError("relevant identifiers must be non-blank")
        if len(set(self.relevant_identifiers)) != len(self.relevant_identifiers):
            raise ValueError("relevant identifiers must be unique")
        evidence_ids = tuple(item.evidence_id for item in self.retrieved)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("retrieved evidence IDs must be unique")
        ranks = tuple(item.rank for item in self.retrieved)
        if len(set(ranks)) != len(ranks):
            raise ValueError("retrieval ranks must be unique")
        if ranks and set(ranks) != set(range(1, len(ranks) + 1)):
            raise ValueError("retrieval ranks must be contiguous from 1")
        known_evidence = set(evidence_ids)
        claim_ids = tuple(item.claim_id for item in self.claims)
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("claim IDs must be unique")
        for claim in self.claims:
            unknown = set(claim.supporting_evidence_ids) - known_evidence
            if unknown:
                raise ValueError(
                    f"claim {claim.claim_id!r} references unknown evidence: {sorted(unknown)}"
                )
        if self.used_context_tokens > self.total_context_tokens:
            raise ValueError("used context tokens cannot exceed total context tokens")
        retrieved_tokens = sum(item.context_tokens for item in self.retrieved)
        if retrieved_tokens > self.total_context_tokens:
            raise ValueError("retrieved evidence tokens cannot exceed total context tokens")
        if self.terminal == "succeeded" and (not self.retrieved or not self.claims):
            raise ValueError("succeeded RAG evaluations require retrieved evidence and claims")
        if self.terminal == "blocked" and not (self.block_reason and self.block_reason.strip()):
            raise ValueError("blocked evaluations require a block reason")
        return self


def _validated_cutoff_keys(values: dict[str, float], *, label: str) -> tuple[str, ...]:
    if not values:
        raise ValueError(f"{label} must contain at least one cutoff")
    cutoffs: list[int] = []
    for key, value in values.items():
        try:
            cutoff = int(key)
        except ValueError as exc:
            raise ValueError(f"{label} cutoff keys must be positive integers") from exc
        if cutoff < 1 or str(cutoff) != key:
            raise ValueError(f"{label} cutoff keys must be canonical positive integers")
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError(f"{label} values must be finite rates between 0 and 1")
        cutoffs.append(cutoff)
    return tuple(str(cutoff) for cutoff in sorted(cutoffs))


class RAGEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1)
    recall_at_k: dict[str, float]
    precision_at_k: dict[str, float]
    evidence_precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    citation_support_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    unsupported_claim_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    critical_unsupported_claims: tuple[str, ...]
    duplicate_source_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    context_utilization: float = Field(ge=0, le=1, allow_inf_nan=False)
    llm_calls: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)
    terminal: Literal["succeeded", "blocked", "failed"]
    block_reason: str | None

    @model_validator(mode="after")
    def validate_metrics(self) -> RAGEvaluationReport:
        recall_keys = _validated_cutoff_keys(self.recall_at_k, label="recall_at_k")
        precision_keys = _validated_cutoff_keys(self.precision_at_k, label="precision_at_k")
        if recall_keys != precision_keys:
            raise ValueError("recall and precision must use the same cutoffs")
        if not self.case_id.strip():
            raise ValueError("case ID must be non-blank")
        if any(not claim_id.strip() for claim_id in self.critical_unsupported_claims):
            raise ValueError("critical unsupported claim IDs must be non-blank")
        if len(set(self.critical_unsupported_claims)) != len(
            self.critical_unsupported_claims
        ):
            raise ValueError("critical unsupported claim IDs must be unique")
        return self


class RAGEvaluationAggregate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_count: int = Field(ge=1)
    mean_recall_at_k: dict[str, float]
    mean_precision_at_k: dict[str, float]
    mean_evidence_precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    mean_citation_support_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    mean_unsupported_claim_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    mean_duplicate_source_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    mean_context_utilization: float = Field(ge=0, le=1, allow_inf_nan=False)
    total_llm_calls: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    total_estimated_cost_usd: float = Field(ge=0, allow_inf_nan=False)
    terminal_distribution: dict[str, int]
    blocker_distribution: dict[str, int]

    @model_validator(mode="after")
    def validate_aggregate(self) -> RAGEvaluationAggregate:
        recall_keys = _validated_cutoff_keys(self.mean_recall_at_k, label="mean_recall_at_k")
        precision_keys = _validated_cutoff_keys(
            self.mean_precision_at_k, label="mean_precision_at_k"
        )
        if recall_keys != precision_keys:
            raise ValueError("mean recall and precision must use the same cutoffs")
        if any(count < 0 for count in self.terminal_distribution.values()):
            raise ValueError("terminal distribution counts must be non-negative")
        if sum(self.terminal_distribution.values()) != self.case_count:
            raise ValueError("terminal distribution must sum to case count")
        if any(count < 0 for count in self.blocker_distribution.values()):
            raise ValueError("blocker distribution counts must be non-negative")
        if sum(self.blocker_distribution.values()) > self.case_count:
            raise ValueError("blocker distribution cannot exceed case count")
        return self


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def evaluate_rag_case(
    evaluation: RAGEvaluationInput,
    *,
    cutoffs: tuple[int, ...] = (1, 3, 5, 10),
) -> RAGEvaluationReport:
    if not cutoffs or any(cutoff < 1 for cutoff in cutoffs):
        raise ValueError("RAG cutoffs must contain positive integers")
    if len(set(cutoffs)) != len(cutoffs):
        raise ValueError("RAG cutoffs must be unique")

    ordered = tuple(sorted(evaluation.retrieved, key=lambda item: item.rank))
    relevant = set(evaluation.relevant_identifiers)
    recall_at_k: dict[str, float] = {}
    precision_at_k: dict[str, float] = {}
    for cutoff in cutoffs:
        top = ordered[:cutoff]
        matched_unique = {
            item.stable_identifier for item in top if item.stable_identifier in relevant
        }
        recall_at_k[str(cutoff)] = _ratio(len(matched_unique), len(relevant))
        precision_at_k[str(cutoff)] = _ratio(
            sum(item.stable_identifier in relevant for item in top),
            len(top),
        )

    retrieved_unique = {item.stable_identifier for item in ordered}
    evidence_precision = _ratio(len(retrieved_unique & relevant), len(retrieved_unique))
    cited_ids = {item.evidence_id for item in ordered if item.cited}
    supported_claims = {
        claim.claim_id
        for claim in evaluation.claims
        if cited_ids.intersection(claim.supporting_evidence_ids)
    }
    unsupported_claims = tuple(
        claim.claim_id for claim in evaluation.claims if claim.claim_id not in supported_claims
    )
    critical_unsupported = tuple(
        claim.claim_id
        for claim in evaluation.claims
        if claim.critical and claim.claim_id not in supported_claims
    )
    duplicate_count = len(ordered) - len(retrieved_unique)

    return RAGEvaluationReport(
        case_id=evaluation.case_id,
        recall_at_k=recall_at_k,
        precision_at_k=precision_at_k,
        evidence_precision=evidence_precision,
        citation_support_rate=_ratio(len(supported_claims), len(evaluation.claims)),
        unsupported_claim_rate=_ratio(len(unsupported_claims), len(evaluation.claims)),
        critical_unsupported_claims=critical_unsupported,
        duplicate_source_rate=_ratio(duplicate_count, len(ordered)),
        context_utilization=_ratio(
            evaluation.used_context_tokens,
            evaluation.total_context_tokens,
        ),
        llm_calls=evaluation.llm_calls,
        total_tokens=evaluation.input_tokens + evaluation.output_tokens,
        estimated_cost_usd=evaluation.estimated_cost_usd,
        terminal=evaluation.terminal,
        block_reason=evaluation.block_reason,
    )


def aggregate_rag_reports(
    reports: tuple[RAGEvaluationReport, ...],
) -> RAGEvaluationAggregate:
    if not reports:
        raise ValueError("at least one RAG report is required")
    case_ids = tuple(report.case_id for report in reports)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("RAG aggregate case IDs must be unique")

    cutoff_keys = _validated_cutoff_keys(reports[0].recall_at_k, label="recall_at_k")
    expected_cutoffs = set(cutoff_keys)
    for report in reports:
        if set(report.recall_at_k) != expected_cutoffs:
            raise ValueError("RAG reports must use the same recall cutoffs")
        if set(report.precision_at_k) != expected_cutoffs:
            raise ValueError("RAG reports must use the same precision cutoffs")

    count = len(reports)
    terminal_counts = Counter(report.terminal for report in reports)
    blocker_counts = Counter(
        report.block_reason for report in reports if report.block_reason is not None
    )
    return RAGEvaluationAggregate(
        case_count=count,
        mean_recall_at_k={
            key: sum(report.recall_at_k[key] for report in reports) / count for key in cutoff_keys
        },
        mean_precision_at_k={
            key: sum(report.precision_at_k[key] for report in reports) / count
            for key in cutoff_keys
        },
        mean_evidence_precision=sum(report.evidence_precision for report in reports) / count,
        mean_citation_support_rate=sum(report.citation_support_rate for report in reports) / count,
        mean_unsupported_claim_rate=sum(report.unsupported_claim_rate for report in reports)
        / count,
        mean_duplicate_source_rate=sum(report.duplicate_source_rate for report in reports) / count,
        mean_context_utilization=sum(report.context_utilization for report in reports) / count,
        total_llm_calls=sum(report.llm_calls for report in reports),
        total_tokens=sum(report.total_tokens for report in reports),
        total_estimated_cost_usd=sum(report.estimated_cost_usd for report in reports),
        terminal_distribution=dict(sorted(terminal_counts.items())),
        blocker_distribution=dict(sorted(blocker_counts.items())),
    )
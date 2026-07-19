from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.rag_evaluation import (
    ClaimAssessment,
    RAGEvaluationAggregate,
    RAGEvaluationInput,
    RAGEvaluationReport,
    RetrievedEvidence,
    aggregate_rag_reports,
    evaluate_rag_case,
)


def _input(*, case_id: str = "case-1") -> RAGEvaluationInput:
    return RAGEvaluationInput(
        case_id=case_id,
        relevant_identifiers=("doi:a", "doi:b"),
        retrieved=(
            RetrievedEvidence(
                evidence_id="E1",
                stable_identifier="doi:a",
                rank=1,
                context_tokens=100,
                cited=True,
            ),
            RetrievedEvidence(
                evidence_id="E2",
                stable_identifier="doi:b",
                rank=2,
                context_tokens=100,
                cited=True,
            ),
        ),
        claims=(
            ClaimAssessment(
                claim_id="C1",
                supporting_evidence_ids=("E1",),
                critical=True,
            ),
            ClaimAssessment(claim_id="C2", supporting_evidence_ids=("E2",)),
        ),
        total_context_tokens=250,
        used_context_tokens=200,
        llm_calls=2,
        input_tokens=500,
        output_tokens=100,
        estimated_cost_usd=0.02,
        terminal="succeeded",
    )


def test_blank_evidence_identifier_is_rejected() -> None:
    with pytest.raises(ValidationError, match="identifiers must be non-blank"):
        RetrievedEvidence(
            evidence_id=" ",
            stable_identifier="doi:a",
            rank=1,
            context_tokens=1,
        )


def test_duplicate_support_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="must be unique per claim"):
        ClaimAssessment(claim_id="C1", supporting_evidence_ids=("E1", "E1"))


def test_input_identity_and_rank_invariants_are_rejected() -> None:
    payload = _input().model_dump(mode="json")
    payload["relevant_identifiers"] = ["doi:a", "doi:a"]
    with pytest.raises(ValidationError, match="relevant identifiers must be unique"):
        RAGEvaluationInput.model_validate(payload)

    payload = _input().model_dump(mode="json")
    payload["retrieved"][1]["evidence_id"] = "E1"
    with pytest.raises(ValidationError, match="evidence IDs must be unique"):
        RAGEvaluationInput.model_validate(payload)

    payload = _input().model_dump(mode="json")
    payload["retrieved"][1]["rank"] = 3
    with pytest.raises(ValidationError, match="ranks must be contiguous"):
        RAGEvaluationInput.model_validate(payload)


def test_impossible_context_accounting_is_rejected() -> None:
    payload = _input().model_dump(mode="json")
    payload["used_context_tokens"] = 251
    with pytest.raises(ValidationError, match="used context tokens cannot exceed"):
        RAGEvaluationInput.model_validate(payload)


def test_invalid_cutoffs_are_rejected() -> None:
    with pytest.raises(ValueError, match="positive integers"):
        evaluate_rag_case(_input(), cutoffs=(0,))
    with pytest.raises(ValueError, match="must be unique"):
        evaluate_rag_case(_input(), cutoffs=(1, 1))


def test_report_terminal_and_support_invariants_are_rejected() -> None:
    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["terminal"] = "blocked"
    payload["block_reason"] = None
    with pytest.raises(ValidationError, match="blocked reports require"):
        RAGEvaluationReport.model_validate(payload)

    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["critical_unsupported_claims"] = ["C1"]
    with pytest.raises(ValidationError, match="require a non-zero unsupported rate"):
        RAGEvaluationReport.model_validate(payload)


def test_aggregate_rejects_empty_duplicate_and_inconsistent_cases() -> None:
    with pytest.raises(ValueError, match="at least one RAG report"):
        aggregate_rag_reports(())

    report = evaluate_rag_case(_input(), cutoffs=(1, 2))
    with pytest.raises(ValueError, match="case IDs must be unique"):
        aggregate_rag_reports((report, report))

    other = evaluate_rag_case(_input(case_id="case-2"), cutoffs=(1, 3))
    with pytest.raises(ValueError, match="same recall cutoffs"):
        aggregate_rag_reports((report, other))


def test_aggregate_model_rejects_distribution_drift() -> None:
    first = evaluate_rag_case(_input(case_id="case-1"), cutoffs=(1, 2))
    second = evaluate_rag_case(_input(case_id="case-2"), cutoffs=(1, 2))
    payload = aggregate_rag_reports((first, second)).model_dump(mode="json")
    payload["terminal_distribution"] = {"succeeded": 1}

    with pytest.raises(ValidationError, match="must sum to case count"):
        RAGEvaluationAggregate.model_validate(payload)

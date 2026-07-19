from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.rag_evaluation import (
    ClaimAssessment,
    RAGEvaluationInput,
    RetrievedEvidence,
    aggregate_rag_reports,
    evaluate_rag_case,
)


def _input(*, terminal: str = "succeeded", block_reason: str | None = None) -> RAGEvaluationInput:
    return RAGEvaluationInput(
        case_id="case-1",
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
        terminal=terminal,
        block_reason=block_reason,
    )


def test_perfect_rag_case_reports_separate_retrieval_and_grounding_metrics() -> None:
    report = evaluate_rag_case(_input(), cutoffs=(1, 2))

    assert report.recall_at_k == {"1": 0.5, "2": 1.0}
    assert report.precision_at_k == {"1": 1.0, "2": 1.0}
    assert report.evidence_precision == 1.0
    assert report.citation_support_rate == 1.0
    assert report.unsupported_claim_rate == 0.0
    assert report.critical_unsupported_claims == ()
    assert report.context_utilization == 0.8
    assert report.total_tokens == 600


def test_duplicate_and_uncited_evidence_reduce_metrics() -> None:
    evaluation = _input().model_copy(
        update={
            "retrieved": (
                RetrievedEvidence(
                    evidence_id="E1",
                    stable_identifier="doi:a",
                    rank=1,
                    context_tokens=50,
                    cited=True,
                ),
                RetrievedEvidence(
                    evidence_id="E2",
                    stable_identifier="doi:a",
                    rank=2,
                    context_tokens=50,
                    cited=False,
                ),
            ),
        }
    )
    report = evaluate_rag_case(evaluation, cutoffs=(2,))

    assert report.recall_at_k["2"] == 0.5
    assert report.duplicate_source_rate == 0.5
    assert report.citation_support_rate == 0.5
    assert report.unsupported_claim_rate == 0.5


def test_unknown_claim_evidence_is_rejected() -> None:
    payload = _input().model_dump(mode="json")
    payload["claims"] = [
        {
            "claim_id": "C1",
            "supporting_evidence_ids": ["MISSING"],
            "critical": False,
        }
    ]
    with pytest.raises(ValidationError, match="unknown evidence"):
        RAGEvaluationInput.model_validate(payload)


def test_blocked_input_requires_reason() -> None:
    with pytest.raises(ValidationError, match="block reason"):
        _input(terminal="blocked")


def test_aggregate_preserves_blocker_distribution_and_cost() -> None:
    succeeded = evaluate_rag_case(_input(), cutoffs=(1, 2))
    blocked = evaluate_rag_case(
        _input(terminal="blocked", block_reason="retrieval_no_results"),
        cutoffs=(1, 2),
    )

    aggregate = aggregate_rag_reports((succeeded, blocked))

    assert aggregate.case_count == 2
    assert aggregate.terminal_distribution == {"blocked": 1, "succeeded": 1}
    assert aggregate.blocker_distribution == {"retrieval_no_results": 1}
    assert aggregate.total_llm_calls == 4
    assert aggregate.total_tokens == 1200
    assert aggregate.total_estimated_cost_usd == pytest.approx(0.04)

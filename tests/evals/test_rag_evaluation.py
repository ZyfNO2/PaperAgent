from __future__ import annotations

from typing import Literal

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


def _input(
    *,
    case_id: str = "case-1",
    terminal: Literal["succeeded", "blocked", "failed"] = "succeeded",
    block_reason: str | None = None,
) -> RAGEvaluationInput:
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
    payload = _input().model_dump(mode="json")
    payload["retrieved"] = [
        {
            "evidence_id": "E1",
            "stable_identifier": "doi:a",
            "rank": 1,
            "context_tokens": 50,
            "cited": True,
        },
        {
            "evidence_id": "E2",
            "stable_identifier": "doi:a",
            "rank": 2,
            "context_tokens": 50,
            "cited": False,
        },
    ]
    evaluation = RAGEvaluationInput.model_validate(payload)
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


def test_succeeded_input_requires_evidence_and_claims() -> None:
    payload = _input().model_dump(mode="json")
    payload["claims"] = []
    with pytest.raises(ValidationError, match="require retrieved evidence and claims"):
        RAGEvaluationInput.model_validate(payload)


def test_succeeded_input_rejects_block_reason() -> None:
    with pytest.raises(ValidationError, match="cannot carry a block reason"):
        _input(block_reason="stale blocker")


def test_blocked_input_requires_reason() -> None:
    with pytest.raises(ValidationError, match="block reason"):
        _input(terminal="blocked")


def test_report_rejects_out_of_range_metric_values() -> None:
    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["recall_at_k"]["1"] = 1.5
    with pytest.raises(ValidationError, match="finite rates between 0 and 1"):
        RAGEvaluationReport.model_validate(payload)


def test_report_rejects_inconsistent_support_rates() -> None:
    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["citation_support_rate"] = 0.75
    with pytest.raises(ValidationError, match="support rates must sum to 1"):
        RAGEvaluationReport.model_validate(payload)


def test_aggregate_is_cutoff_order_independent() -> None:
    first = evaluate_rag_case(_input(case_id="case-1"), cutoffs=(1, 2))
    second_payload = evaluate_rag_case(_input(case_id="case-2"), cutoffs=(1, 2)).model_dump(
        mode="json"
    )
    second_payload["recall_at_k"] = {"2": 1.0, "1": 0.5}
    second_payload["precision_at_k"] = {"2": 1.0, "1": 1.0}
    second = RAGEvaluationReport.model_validate(second_payload)

    aggregate = aggregate_rag_reports((first, second))

    assert tuple(aggregate.mean_recall_at_k) == ("1", "2")
    assert aggregate.mean_recall_at_k == {"1": 0.5, "2": 1.0}


def test_aggregate_rejects_duplicate_case_ids() -> None:
    report = evaluate_rag_case(_input(), cutoffs=(1, 2))
    with pytest.raises(ValueError, match="case IDs must be unique"):
        aggregate_rag_reports((report, report))


def test_aggregate_preserves_blocker_distribution_and_cost() -> None:
    succeeded = evaluate_rag_case(_input(case_id="case-1"), cutoffs=(1, 2))
    blocked = evaluate_rag_case(
        _input(
            case_id="case-2",
            terminal="blocked",
            block_reason="retrieval_no_results",
        ),
        cutoffs=(1, 2),
    )

    aggregate = aggregate_rag_reports((succeeded, blocked))

    assert aggregate.case_count == 2
    assert aggregate.terminal_distribution == {"blocked": 1, "succeeded": 1}
    assert aggregate.blocker_distribution == {"retrieval_no_results": 1}
    assert aggregate.total_llm_calls == 4
    assert aggregate.total_tokens == 1200
    assert aggregate.total_estimated_cost_usd == pytest.approx(0.04)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("blank_relevant", "relevant identifiers must be non-blank"),
        ("duplicate_relevant", "relevant identifiers must be unique"),
        ("duplicate_evidence", "retrieved evidence IDs must be unique"),
        ("duplicate_rank", "retrieval ranks must be unique"),
        ("noncontiguous_rank", "retrieval ranks must be contiguous"),
        ("duplicate_claim", "claim IDs must be unique"),
        ("used_context_overflow", "used context tokens cannot exceed"),
        ("retrieved_context_overflow", "retrieved evidence tokens cannot exceed"),
    ],
)
def test_input_contract_rejects_structural_inconsistency(
    mutation: str,
    message: str,
) -> None:
    payload = _input().model_dump(mode="json")
    if mutation == "blank_relevant":
        payload["relevant_identifiers"] = ["doi:a", " "]
    elif mutation == "duplicate_relevant":
        payload["relevant_identifiers"] = ["doi:a", "doi:a"]
    elif mutation == "duplicate_evidence":
        payload["retrieved"][1]["evidence_id"] = "E1"
    elif mutation == "duplicate_rank":
        payload["retrieved"][1]["rank"] = 1
    elif mutation == "noncontiguous_rank":
        payload["retrieved"][1]["rank"] = 3
    elif mutation == "duplicate_claim":
        payload["claims"][1]["claim_id"] = "C1"
    elif mutation == "used_context_overflow":
        payload["used_context_tokens"] = 251
    elif mutation == "retrieved_context_overflow":
        payload["total_context_tokens"] = 150
    with pytest.raises(ValidationError, match=message):
        RAGEvaluationInput.model_validate(payload)


def test_identifier_models_reject_blanks_and_duplicate_support() -> None:
    with pytest.raises(ValidationError, match="identifiers must be non-blank"):
        RetrievedEvidence(
            evidence_id=" ",
            stable_identifier="doi:a",
            rank=1,
            context_tokens=0,
        )
    with pytest.raises(ValidationError, match="claim ID must be non-blank"):
        ClaimAssessment(claim_id=" ")
    with pytest.raises(ValidationError, match="supporting evidence IDs must be non-blank"):
        ClaimAssessment(claim_id="C1", supporting_evidence_ids=(" ",))
    with pytest.raises(ValidationError, match="must be unique per claim"):
        ClaimAssessment(claim_id="C1", supporting_evidence_ids=("E1", "E1"))


@pytest.mark.parametrize("cutoffs", [(), (0,), (1, 1)])
def test_evaluation_rejects_invalid_cutoffs(cutoffs: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="cutoffs"):
        evaluate_rag_case(_input(), cutoffs=cutoffs)


def test_report_rejects_cutoff_and_critical_claim_inconsistency() -> None:
    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["precision_at_k"] = {"1": 1.0}
    with pytest.raises(ValidationError, match="same cutoffs"):
        RAGEvaluationReport.model_validate(payload)

    payload = evaluate_rag_case(_input(), cutoffs=(1, 2)).model_dump(mode="json")
    payload["critical_unsupported_claims"] = ["C1"]
    with pytest.raises(ValidationError, match="non-zero unsupported rate"):
        RAGEvaluationReport.model_validate(payload)


def test_aggregate_rejects_empty_and_mismatched_cutoffs() -> None:
    with pytest.raises(ValueError, match="at least one RAG report"):
        aggregate_rag_reports(())

    first = evaluate_rag_case(_input(case_id="case-1"), cutoffs=(1, 2))
    second_payload = evaluate_rag_case(_input(case_id="case-2"), cutoffs=(1, 2)).model_dump(
        mode="json"
    )
    second_payload["recall_at_k"] = {"1": 0.5, "3": 1.0}
    second_payload["precision_at_k"] = {"1": 1.0, "3": 1.0}
    second = RAGEvaluationReport.model_validate(second_payload)
    with pytest.raises(ValueError, match="same recall cutoffs"):
        aggregate_rag_reports((first, second))


def test_aggregate_model_rejects_invalid_distributions() -> None:
    valid = aggregate_rag_reports((evaluate_rag_case(_input(), cutoffs=(1, 2)),)).model_dump(
        mode="json"
    )
    valid["terminal_distribution"] = {"unknown": 1}
    with pytest.raises(ValidationError, match="unknown terminal"):
        RAGEvaluationAggregate.model_validate(valid)

    valid = aggregate_rag_reports((evaluate_rag_case(_input(), cutoffs=(1, 2)),)).model_dump(
        mode="json"
    )
    valid["blocker_distribution"] = {" ": 1}
    with pytest.raises(ValidationError, match="reasons must be non-blank"):
        RAGEvaluationAggregate.model_validate(valid)

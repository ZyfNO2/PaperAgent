from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, cast

from paperagent.claw_benchmark_normalizer import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceLedger,
    EvidenceLedgerEntry,
    FinalOutcome,
    FinalReport,
    GapSupportAssessment,
    ResearchRequest,
)
from paperagent.state import PaperAgentState


def _revise_state(
    *,
    next_action: str,
    quality_route: Literal[
        "pass",
        "repair_retrieval",
        "repair_method",
        "human_review",
        "blocked",
    ] = "blocked",
) -> PaperAgentState:
    return cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="held-out research task"),
            "final_outcome": FinalOutcome(
                execution_status="succeeded",
                scientific_verdict="REVISE",
                quality_route=quality_route,
                report_status="completed",
                reason_codes=["Q_INSUFFICIENT_COVERAGE"],
                recommended_next_actions=[next_action],
            ),
            "report": FinalReport(
                status="completed",
                executive_summary="Evidence remains incomplete.",
                verified_findings=[],
                inferred_findings=[],
                limitations=["The required evidence is incomplete."],
                next_actions=[next_action],
                evidence_ids=[],
            ),
        },
    )


def test_free_text_next_actions_cannot_infer_pilot_label() -> None:
    state = _revise_state(
        next_action="Run a pilot, bounded retrieval, method repair, and freeze baseline."
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="held-out-001"),
    )
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended is False


def test_explicit_structured_pilot_signal_is_preserved() -> None:
    state = _revise_state(
        next_action="Collect one more observation.", quality_route="repair_method"
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(
            case_id="held-out-002",
            pilot_recommended=True,
        ),
    )
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended is True


def test_canonical_ledger_controls_evidence_review_semantics() -> None:
    evidence_id = "ev-held-out"
    state = cast(
        PaperAgentState,
        {
            **_revise_state(next_action="Collect one more observation."),
            "evidence": EvidenceBundle(
                items=[
                    EvidenceItem(
                        evidence_id=evidence_id,
                        source_type="paper",
                        title="Held-out evidence",
                        locator="https://example.invalid/paper",
                        retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                        verification_status="accepted",
                        supports_gap_ids=["gap-held-out"],
                        summary="Task-matched evidence.",
                        content_hash="sha256:held-out",
                    )
                ],
                accepted_ids=[evidence_id],
                identity_verified_ids=[evidence_id],
                coverage_by_gap={"gap-held-out": 1},
            ),
            "evidence_ledger": EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        evidence_id=evidence_id,
                        identity_verified=True,
                        relevance_scope="direct",
                        gap_supports=[
                            GapSupportAssessment(
                                evidence_id=evidence_id,
                                gap_id="gap-held-out",
                                support_type="direct_support",
                                supported_claim="The evidence directly supports the gap.",
                                supporting_span_hash="sha256:span",
                                checklist_results={"relevance_passed": True},
                                confidence=0.9,
                                decision="accept",
                            )
                        ],
                        supported_claims=["claim-held-out"],
                        accepted=True,
                    )
                ],
                accepted_ids=[evidence_id],
                coverage_by_gap={"gap-held-out": 1},
            ),
        },
    )

    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="held-out-ledger"),
    )

    review = trace.evidence_reviews[0]
    assert review.identity_verified is True
    assert review.relevance_reviewed is True
    assert review.relevance_passed is True
    assert review.accepted is True
    assert review.role == "gap"
    assert review.gap_ids == ("gap-held-out",)
    assert review.claim_ids == ("claim-held-out",)


def test_leakage_signal_is_live_and_not_a_model_default() -> None:
    state = _revise_state(next_action="Collect more evidence.")
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(
            case_id="held-out-003",
            future_or_test_leakage=True,
            leakage_findings=("conditioned_rule:example.py",),
        ),
    )
    assert trace.future_or_test_leakage is True
    assert "conditioned_rule:example.py" in trace.trace_error_codes


def test_clean_context_explicitly_sets_no_leakage() -> None:
    state = _revise_state(next_action="Collect more evidence.")
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="held-out-004"),
    )
    assert trace.future_or_test_leakage is False


def test_not_evaluated_state_fails_closed_in_benchmark_trace() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="A failed research run"),
            "final_outcome": FinalOutcome(
                execution_status="failed",
                scientific_verdict="NOT_EVALUATED",
                quality_route="blocked",
                report_status="blocked",
                reason_codes=["PROVIDER_FAILURE"],
                blocker_code="PROVIDER_FAILURE",
            ),
        },
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="held-out-005"),
    )
    assert trace.decision == "REVISE"
    assert trace.trace_audit_passed is False
    assert "NOT_EVALUATED" in trace.trace_error_codes


def test_user_objective_is_not_external_verification() -> None:
    state = cast(
        PaperAgentState,
        {"request": ResearchRequest(question="peatland methane flux modelling")},
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="held-out-006"),
    )
    assert trace.fact_partitions.verified == (
        "User-declared research objective: peatland methane flux modelling",
    )
    assert trace.fact_partitions.inferred == ()
    assert trace.fact_partitions.proposed == ()

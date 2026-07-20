from __future__ import annotations

from typing import Literal, cast

from paperagent.claw_benchmark_normalizer import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.schemas import FinalOutcome, FinalReport, ResearchRequest
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

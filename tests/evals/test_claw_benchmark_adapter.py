from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from paperagent.claw_academic_benchmark import evaluate_case, load_gold_dataset
from paperagent.claw_benchmark_adapter import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    EvidenceLedger,
    EvidenceLedgerEntry,
    FinalOutcome,
    FinalReport,
    GapSupportAssessment,
    RelevanceAssessment,
    ResearchPlan,
    ResearchRequest,
    SearchQuery,
    TraceAuditResult,
)
from paperagent.state import PaperAgentState

REPOSITORY_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
DATASET_ROOT = REPOSITORY_ROOT / "evals" / "claw_academic_tailoring_v1"
_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _plan() -> ResearchPlan:
    roles = {
        "gap-baseline": "reproducible baseline evidence",
        "gap-problem": "research gap and limitation evidence",
        "gap-parallel": "parallel method mechanism evidence",
        "gap-comparison": "strong comparison and SOTA evidence",
        "gap-risk": "risk and negative-result evidence",
    }
    return ResearchPlan(
        status="ready",
        problem_statement="Evaluate a lightweight UAV small-object detector.",
        scope="A bounded pilot under a declared device budget.",
        research_questions=["Which single mechanism improves AP_small?"],
        evidence_gaps=[
            EvidenceGap(gap_id=gap_id, description=description)
            for gap_id, description in roles.items()
        ],
        search_queries=[
            SearchQuery(
                query_id=f"query-{index}",
                gap_id=gap_id,
                query=description,
                source_types=["paper"],
            )
            for index, (gap_id, description) in enumerate(roles.items(), start=1)
        ],
        success_criteria=["Produce a bounded pilot plan."],
        risks=["deployment device remains unknown"],
    )


def _accepted_evidence() -> tuple[
    EvidenceBundle,
    EvidenceLedger,
    list[RelevanceAssessment],
]:
    item = EvidenceItem(
        evidence_id="ev-baseline",
        source_type="paper",
        title="A reproducible lightweight detector baseline",
        locator="doi:10.1000/baseline",
        retrieved_at=_NOW,
        verification_status="accepted",
        supports_gap_ids=["gap-baseline"],
        summary="The paper defines a maintained lightweight detector baseline.",
        content_hash="sha256:baseline",
        provider="fixture",
        metadata={"doi": "10.1000/baseline", "full_text_checked": "true"},
    )
    support = GapSupportAssessment(
        evidence_id=item.evidence_id,
        gap_id="gap-baseline",
        support_type="direct_support",
        supported_claim="The baseline is reproducible.",
        supporting_span_hash="sha256:span",
        checklist_results={"baseline_role": True},
        confidence=1.0,
        decision="accept",
    )
    ledger = EvidenceLedger(
        entries=[
            EvidenceLedgerEntry(
                evidence_id=item.evidence_id,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=[support],
                supported_claims=["The baseline is reproducible."],
                accepted=True,
            )
        ],
        accepted_ids=[item.evidence_id],
        rejected_ids=[],
        coverage_by_gap={"gap-baseline": 1},
    )
    bundle = EvidenceBundle(
        items=[item],
        accepted_ids=[item.evidence_id],
        identity_verified_ids=[item.evidence_id],
        coverage_by_gap={"gap-baseline": 1},
    )
    relevance = [
        RelevanceAssessment(
            evidence_id=item.evidence_id,
            task_match=True,
            domain_match=True,
            baseline_match=True,
            evidence_scope="direct",
            relevance_score=1.0,
            decision="pass",
            supporting_spans=["maintained lightweight detector baseline"],
        )
    ]
    return bundle, ledger, relevance


def test_real_state_normalization_is_gold_independent_and_conservative() -> None:
    evidence, ledger, relevance = _accepted_evidence()
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="轻量化无人机小目标检测",
                domain_hint="uav object detection",
                clarification_answer="Use a Jetson-class device and prioritize AP_small.",
            ),
            "plan": _plan(),
            "evidence": evidence,
            "evidence_ledger": ledger,
            "relevance_assessments": relevance,
            "final_outcome": FinalOutcome(
                execution_status="succeeded",
                scientific_verdict="REVISE",
                quality_route="repair_method",
                report_status="completed",
                reason_codes=["BASELINE_NOT_REPRODUCED"],
                recommended_next_actions=["Run the minimum bounded pilot."],
            ),
            "report": FinalReport(
                status="completed",
                executive_summary="Evidence exists, but the baseline is not frozen.",
                verified_findings=[],
                inferred_findings=[],
                limitations=["Baseline reproduction remains pending."],
                next_actions=["Run the minimum bounded pilot."],
                evidence_ids=["ev-baseline"],
            ),
            "trace_audit": TraceAuditResult(passed=True, results=[]),
        },
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(
            case_id="at-001-uav-small-object-lightweight",
            resolved_unknowns=("deployment_device", "accuracy_latency_priority"),
            stronger_baselines_considered=True,
            negative_results_visible=True,
        ),
    )

    assert trace.case_id == "at-001-uav-small-object-lightweight"
    assert set(trace.retrieval_roles) == {
        "baseline",
        "gap",
        "parallel_method",
        "strong_comparison",
        "risk",
    }
    assert trace.evidence_reviews[0].accepted
    assert trace.evidence_reviews[0].role == "baseline"
    assert trace.evidence_reviews[0].full_text_checked
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended
    assert trace.module_design_deferred
    assert trace.baseline is None

    dataset = load_gold_dataset(DATASET_ROOT)
    case = next(item for item in dataset.cases if item.case_id == trace.case_id)
    result = evaluate_case(case, trace)
    assert result.decision_matches
    assert not result.hard_failures
    assert result.score < 100


def test_revise_with_actionable_recovery_infers_pilot() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="轻量化无人机小目标检测"),
            "final_outcome": FinalOutcome(
                execution_status="succeeded",
                scientific_verdict="REVISE",
                quality_route="blocked",
                report_status="completed",
                reason_codes=["Q_INSUFFICIENT_COVERAGE"],
                recommended_next_actions=[
                    "Run a focused retrieval round with stricter relevance.",
                    "Freeze the baseline before method design.",
                ],
            ),
            "report": FinalReport(
                status="completed",
                executive_summary="Evidence was insufficient.",
                verified_findings=[],
                inferred_findings=[],
                limitations=["Baseline reproduction remains pending."],
                next_actions=[
                    "Run a focused retrieval round with stricter relevance.",
                    "Freeze the baseline before method design.",
                ],
                evidence_ids=[],
            ),
        },
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(
            case_id="at-001-uav-small-object-lightweight",
            stronger_baselines_considered=True,
            negative_results_visible=True,
        ),
    )
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended
    assert trace.trace_audit_passed is not False

    dataset = load_gold_dataset(DATASET_ROOT)
    case = next(item for item in dataset.cases if item.case_id == trace.case_id)
    result = evaluate_case(case, trace)
    assert result.decision_matches
    assert result.observed_decision == "REVISE_TO_PILOT"


def test_revise_with_only_placeholder_recovery_defers_pilot() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="轻量化无人机小目标检测"),
            "final_outcome": FinalOutcome(
                execution_status="succeeded",
                scientific_verdict="REVISE",
                quality_route="blocked",
                report_status="completed",
                reason_codes=["Q_INSUFFICIENT_COVERAGE"],
                recommended_next_actions=[
                    "capture missing evidence and rerun the bounded workflow"
                ],
            ),
            "report": FinalReport(
                status="completed",
                executive_summary="Evidence was insufficient.",
                verified_findings=[],
                inferred_findings=[],
                limitations=["Public evidence remains insufficient."],
                next_actions=[],
                evidence_ids=[],
            ),
        },
    )
    trace = normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(
            case_id="at-001-uav-small-object-lightweight",
            stronger_baselines_considered=True,
            negative_results_visible=True,
        ),
    )
    assert trace.decision == "REVISE"
    assert trace.pilot_recommended is False


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
        BenchmarkNormalizationContext(
            case_id="at-019-unet-unspecified-medical-segmentation",
            stronger_baselines_considered=False,
            negative_results_visible=False,
        ),
    )
    assert trace.decision == "REVISE"
    assert trace.trace_audit_passed is False
    assert "NOT_EVALUATED" in trace.trace_error_codes

    dataset = load_gold_dataset(DATASET_ROOT)
    case = next(item for item in dataset.cases if item.case_id == trace.case_id)
    result = evaluate_case(case, trace)
    assert result.status == "failed"
    assert "TRACE_CONTRACT_FAILURE" in {item.code for item in result.hard_failures}

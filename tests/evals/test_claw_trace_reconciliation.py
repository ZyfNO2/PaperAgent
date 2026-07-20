from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from paperagent.claw_benchmark_adapter import (
    BenchmarkNormalizationContext,
    normalize_paperagent_state,
)
from paperagent.claw_trace_reconciliation import reconcile_ledger_relevance
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    EvidenceLedger,
    EvidenceLedgerEntry,
    GapSupportAssessment,
    ResearchPlan,
    SearchQuery,
)
from paperagent.state import PaperAgentState

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _state(*, ledger_relevance_passed: bool | None) -> PaperAgentState:
    evidence_id = "ev-dataset"
    checklist: dict[str, bool] = {}
    if ledger_relevance_passed is not None:
        checklist["relevance_passed"] = ledger_relevance_passed
    support = GapSupportAssessment(
        evidence_id=evidence_id,
        gap_id="dataset_gap",
        support_type="direct_support",
        supported_claim="A public benchmark dataset is available.",
        supporting_span_hash="sha256:span",
        checklist_results=checklist,
        confidence=0.9,
        decision="accept",
    )
    item = EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title="A public benchmark dataset",
        locator="doi:10.1000/dataset",
        retrieved_at=_NOW,
        verification_status="accepted",
        supports_gap_ids=["dataset_gap"],
        summary="The source describes a public benchmark dataset.",
        content_hash="sha256:dataset",
        provider="fixture",
    )
    return cast(
        PaperAgentState,
        {
            "plan": ResearchPlan(
                status="ready",
                problem_statement="Select a public benchmark dataset.",
                scope="Dataset availability evidence before implementation.",
                evidence_gaps=[
                    EvidenceGap(
                        gap_id="dataset_gap",
                        description="dataset availability gap evidence",
                    )
                ],
                search_queries=[
                    SearchQuery(
                        query_id="q1",
                        gap_id="dataset_gap",
                        query="public benchmark dataset availability",
                        source_types=["paper"],
                    )
                ],
                success_criteria=["Record one verified public dataset source."],
                risks=[],
            ),
            "evidence": EvidenceBundle(
                items=[item],
                accepted_ids=[evidence_id],
                identity_verified_ids=[evidence_id],
                coverage_by_gap={"dataset_gap": 1},
            ),
            "evidence_ledger": EvidenceLedger(
                entries=[
                    EvidenceLedgerEntry(
                        evidence_id=evidence_id,
                        identity_verified=True,
                        relevance_scope="direct",
                        gap_supports=[support],
                        supported_claims=[support.supported_claim],
                        accepted=True,
                    )
                ],
                accepted_ids=[evidence_id],
                rejected_ids=[],
                coverage_by_gap={"dataset_gap": 1},
            ),
        },
    )


def _normalized(state: PaperAgentState):
    return normalize_paperagent_state(
        state,
        BenchmarkNormalizationContext(case_id="at-019-unet-unspecified-medical-segmentation"),
    )


def test_positive_accepted_ledger_check_reconciles_missing_relevance_row() -> None:
    state = _state(ledger_relevance_passed=True)
    before = _normalized(state)

    assert before.evidence_reviews[0].accepted
    assert before.evidence_reviews[0].identity_verified
    assert before.evidence_reviews[0].relevance_reviewed is False
    assert before.evidence_reviews[0].relevance_passed is False

    after = reconcile_ledger_relevance(state, before)

    assert after.evidence_reviews[0].relevance_reviewed is True
    assert after.evidence_reviews[0].relevance_passed is True
    assert after.evidence_reviews[0].identity_verified is True
    assert after.evidence_reviews[0].gap_ids == ("dataset_gap",)


def test_missing_ledger_relevance_check_does_not_synthesize_review() -> None:
    state = _state(ledger_relevance_passed=None)
    after = reconcile_ledger_relevance(state, _normalized(state))

    assert after.evidence_reviews[0].relevance_reviewed is False
    assert after.evidence_reviews[0].relevance_passed is False


def test_negative_ledger_relevance_check_does_not_synthesize_review() -> None:
    state = _state(ledger_relevance_passed=False)
    after = reconcile_ledger_relevance(state, _normalized(state))

    assert after.evidence_reviews[0].relevance_reviewed is False
    assert after.evidence_reviews[0].relevance_passed is False

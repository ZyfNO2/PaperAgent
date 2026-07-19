from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from paperagent.academic_methodology import AuditVerdict
from paperagent.evidence_relevance import apply_ledger_to_bundle, build_evidence_ledger
from paperagent.outcome import audit_state_consistency, derive_final_outcome
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    FinalOutcome,
    FinalReport,
    QualityDecision,
    ReportClaim,
    ResearchPlan,
    ResearchRequest,
    SearchQuery,
    TraceEvent,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _plan(gap_id: str, description: str) -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="Improve steel surface defect detection.",
        scope="NEU-DET visual inspection.",
        research_questions=["Which mechanism improves robust defect detection?"],
        evidence_gaps=[
            EvidenceGap(gap_id=gap_id, description=description, minimum_accepted_items=1)
        ],
        search_queries=[
            SearchQuery(
                query_id="query-1",
                gap_id=gap_id,
                query=f"steel defect detection {description}",
                source_types=["paper"],
            )
        ],
        success_criteria=["The required evidence gap is supported."],
        risks=[],
    )


def _verified_item(
    *,
    evidence_id: str,
    title: str,
    summary: str,
    gap_id: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=_NOW,
        verification_status="accepted",
        supports_gap_ids=[gap_id],
        summary=summary,
        content_hash=f"sha256:{evidence_id}",
        provider="literature_retrieval",
        metadata={
            "verification_status": "verified",
            "doi": f"10.1000/{evidence_id}",
            "candidate_gap_ids": gap_id,
        },
    )


def _identity_bundle(item: EvidenceItem) -> EvidenceBundle:
    return EvidenceBundle(
        items=[item],
        accepted_ids=[item.evidence_id],
        identity_verified_ids=[item.evidence_id],
        coverage_by_gap={gap_id: 1 for gap_id in item.supports_gap_ids},
    )


def test_real_but_unrelated_paper_is_identity_verified_and_relevance_rejected() -> None:
    plan = _plan("gap-small-object", "small defect object localization")
    item = _verified_item(
        evidence_id="ev-particle",
        title="Precision measurements in high energy particle collisions",
        summary="A collider physics analysis of boson decay channels.",
        gap_id="gap-small-object",
    )
    _, _, relevance, bindings, ledger = build_evidence_ledger(
        request=ResearchRequest(
            question="Improve steel defect detection.", domain_hint="steel defect detection"
        ),
        plan=plan,
        evidence=_identity_bundle(item),
    )
    bundle = apply_ledger_to_bundle(_identity_bundle(item), ledger)

    assert bundle.identity_verified_ids == ["ev-particle"]
    assert bundle.accepted_ids == []
    assert bundle.relevance_rejected_ids == ["ev-particle"]
    assert bundle.coverage_by_gap == {}
    assert relevance[0].decision == "reject"
    assert all(binding.decision == "reject" for binding in bindings)


def test_related_paper_cannot_support_an_unrelated_gap_from_query_provenance_alone() -> None:
    plan = _plan("gap-imbalance", "class imbalance mitigation")
    item = _verified_item(
        evidence_id="ev-attention",
        title="Attention networks for steel surface defect detection",
        summary="The detector improves localization using a spatial attention block.",
        gap_id="gap-imbalance",
    )
    _, _, relevance, bindings, ledger = build_evidence_ledger(
        request=ResearchRequest(
            question="Improve steel defect detection.", domain_hint="steel defect detection"
        ),
        plan=plan,
        evidence=_identity_bundle(item),
    )

    assert relevance[0].decision == "pass"
    assert bindings[0].decision == "reject"
    assert bindings[0].support_type == "insufficient"
    assert ledger.accepted_ids == []
    assert ledger.coverage_by_gap == {}


def test_relevant_paper_with_claim_level_gap_overlap_enters_ledger() -> None:
    plan = _plan("gap-imbalance", "class imbalance mitigation")
    item = _verified_item(
        evidence_id="ev-imbalance",
        title="Class imbalance mitigation for steel defect detection",
        summary="A class-balanced loss improves rare steel defect detection.",
        gap_id="gap-imbalance",
    )
    _, _, relevance, bindings, ledger = build_evidence_ledger(
        request=ResearchRequest(
            question="Improve steel defect detection.", domain_hint="steel defect detection"
        ),
        plan=plan,
        evidence=_identity_bundle(item),
    )

    assert relevance[0].decision == "pass"
    assert bindings[0].decision == "accept"
    assert bindings[0].supporting_span_hash is not None
    assert ledger.accepted_ids == ["ev-imbalance"]
    assert ledger.coverage_by_gap == {"gap-imbalance": 1}


def test_methodology_no_go_is_a_successful_scientific_outcome() -> None:
    state = {
        "plan": _plan("gap-imbalance", "class imbalance mitigation"),
        "quality": QualityDecision(
            verdict="blocked", reason_codes=["Q_METHODOLOGY_NO_GO"]
        ),
        "methodology_audit": SimpleNamespace(
            verdict=AuditVerdict.NO_GO,
            plan_fingerprint="sha256:no-go",
        ),
    }

    outcome = derive_final_outcome(state)  # type: ignore[arg-type]

    assert outcome.execution_status == "succeeded"
    assert outcome.scientific_verdict == "NO_GO"
    assert outcome.report_status == "completed"


def _consistent_go_state() -> dict:
    plan = _plan("gap-imbalance", "class imbalance mitigation")
    item = _verified_item(
        evidence_id="ev-imbalance",
        title="Class imbalance mitigation for steel defect detection",
        summary="A class-balanced loss improves rare steel defect detection.",
        gap_id="gap-imbalance",
    )
    _, _, _, _, ledger = build_evidence_ledger(
        request=ResearchRequest(
            question="Improve steel defect detection.", domain_hint="steel defect detection"
        ),
        plan=plan,
        evidence=_identity_bundle(item),
    )
    evidence = apply_ledger_to_bundle(_identity_bundle(item), ledger)
    quality = QualityDecision(verdict="pass", reason_codes=[])
    outcome = FinalOutcome(
        execution_status="succeeded",
        scientific_verdict="GO",
        quality_route="pass",
        report_status="completed",
        evidence_ledger_fingerprint="sha256:ledger",
    )
    report = FinalReport(
        status="completed",
        executive_summary="The evidence contract passed.",
        verified_findings=[
            ReportClaim(text="The gap is supported.", evidence_ids=["ev-imbalance"])
        ],
        inferred_findings=[],
        limitations=["Synthetic fixture only."],
        evidence_ids=["ev-imbalance"],
    )
    route = TraceEvent(
        event_id="event-1",
        run_id="run-1",
        span_id="span-1",
        event_type="route.decided",
        node="quality_gate_node",
        timestamp=_NOW,
        status="decided",
        route="pass",
    )
    return {
        "plan": plan,
        "evidence": evidence,
        "evidence_ledger": ledger,
        "quality": quality,
        "final_outcome": outcome,
        "report": report,
        "trace": [route],
    }


def test_trace_auditor_accepts_consistent_final_artifacts() -> None:
    result = audit_state_consistency(_consistent_go_state())  # type: ignore[arg-type]

    assert result.passed is True
    assert result.error_codes == []


def test_trace_auditor_rejects_unknown_report_evidence_and_coverage_mutation() -> None:
    state = _consistent_go_state()
    report = state["report"]
    state["report"] = report.model_copy(
        update={
            "evidence_ids": ["ev-unknown"],
            "verified_findings": [
                ReportClaim(text="Tampered claim.", evidence_ids=["ev-unknown"])
            ],
        }
    )
    evidence = state["evidence"]
    state["evidence"] = evidence.model_copy(update={"coverage_by_gap": {"gap-imbalance": 9}})

    result = audit_state_consistency(state)  # type: ignore[arg-type]

    assert result.passed is False
    assert "REPORT_REFERENCES_ACCEPTED_EVIDENCE" in result.error_codes
    assert "GAP_COVERAGE_MATCHES_LEDGER" in result.error_codes

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from test_method_design_draft import _draft, _state

from paperagent.academic_methodology import AuditSeverity, AuditVerdict, audit_method_plan
from paperagent.method_design_draft import build_method_proposal
from paperagent.method_evidence import bind_method_evidence
from paperagent.schemas import Claim, EvidenceItem
from paperagent.state import PaperAgentState


def _with_independent_comparator(state: PaperAgentState) -> PaperAgentState:
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    assert evidence is not None
    assert synthesis is not None
    comparator_id = "ev-policy-rt-detr-r18"
    comparator = EvidenceItem(
        evidence_id=comparator_id,
        source_type="paper",
        title="RT-DETR-R18",
        locator="doi:10.1000/policy-rt-detr-r18",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary=(
            "RT-DETR-R18 is an independently retrieved strong-comparison paper with a "
            "verified identity."
        ),
        content_hash="sha256:policy-rt-detr-r18",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/policy-rt-detr-r18",
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.95",
        },
    )
    comparator_claim = Claim(
        claim_id="claim-policy-rt-detr-r18",
        text=(
            "RT-DETR-R18 provides an independently identified strong-comparison paper "
            "for the matched detector evaluation."
        ),
        evidence_ids=[comparator_id],
    )
    return cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, comparator],
                    "accepted_ids": [*evidence.accepted_ids, comparator_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        comparator_id,
                    ],
                    "coverage_by_gap": {
                        **evidence.coverage_by_gap,
                        "baseline_comparison": (
                            evidence.coverage_by_gap.get("baseline_comparison", 0) + 1
                        ),
                    },
                }
            ),
            "synthesis": synthesis.model_copy(
                update={
                    "verified_findings": [
                        *synthesis.verified_findings,
                        comparator_claim,
                    ]
                }
            ),
        },
    )


def _proposal(**updates: object):
    state = _state()
    if updates.get("comparison_readiness_confirmed") is True:
        state = _with_independent_comparator(state)
    proposal = build_method_proposal(state, _draft(**updates))
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    assert evidence is not None
    assert synthesis is not None
    return bind_method_evidence(proposal, evidence, synthesis)


def test_explicit_invalid_evaluation_protocol_is_no_go() -> None:
    audit = audit_method_plan(_proposal(explicit_evaluation_protocol_invalid=True).methodology_plan)
    failed = {item.check_id: item for item in audit.checks if not item.passed}
    assert audit.verdict is AuditVerdict.NO_GO
    assert failed["evaluation-protocol-valid"].severity is AuditSeverity.CRITICAL


def test_repairable_missing_provenance_is_revise_not_no_go() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
    )
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"supported_claims": ()}) for item in plan.evidence)
    audit = audit_method_plan(plan.model_copy(update={"evidence": evidence}))
    failed = {item.check_id: item for item in audit.checks if not item.passed}
    assert audit.verdict is AuditVerdict.REVISE
    assert failed["baseline-provenance"].severity is AuditSeverity.ERROR


def test_explicit_completed_readiness_can_reach_go() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
    )
    audit = audit_method_plan(proposal.methodology_plan)
    assert audit.verdict is AuditVerdict.GO
    assert proposal.methodology_plan.baseline.reproduced is True
    assert proposal.methodology_plan.baseline.baseline_parity_verified is True


def test_missing_license_is_warning_not_blocker() -> None:
    proposal = _proposal(
        baseline_readiness_confirmed=True,
        evaluation_protocol_validated=True,
        comparison_readiness_confirmed=True,
        module_validation_confirmed=True,
        failure_policy_confirmed=True,
    )
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"license": None}) for item in plan.evidence)
    baseline = plan.baseline.model_copy(update={"license": None})
    modules = tuple(item.model_copy(update={"license": None}) for item in plan.modules)
    audit = audit_method_plan(
        plan.model_copy(update={"evidence": evidence, "baseline": baseline, "modules": modules})
    )
    failed = {item.check_id: item for item in audit.checks if not item.passed}
    assert audit.verdict is AuditVerdict.REVISE
    assert failed["baseline-license"].severity is AuditSeverity.WARNING

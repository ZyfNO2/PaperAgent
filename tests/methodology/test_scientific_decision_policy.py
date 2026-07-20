from __future__ import annotations

from test_method_design_draft import _draft, _state

from paperagent.academic_methodology import AuditSeverity, AuditVerdict, audit_method_plan
from paperagent.method_design_draft import build_method_proposal
from paperagent.method_evidence import bind_method_evidence


def _proposal(**updates: object):
    state = _state()
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
    assert audit.verdict is AuditVerdict.GO
    assert failed["baseline-license"].severity is AuditSeverity.WARNING

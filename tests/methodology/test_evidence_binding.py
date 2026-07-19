from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from paperagent.method_evidence import accepted_evidence_ledger, bind_method_evidence
from paperagent.schemas import EvidenceBundle, EvidenceSynthesis, MethodProposal

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures" / "llm" / "v0_1"


def _method() -> MethodProposal:
    return MethodProposal.model_validate_json(
        (FIXTURES / "method_design" / "happy_path__call_0.json").read_text(encoding="utf-8")
    )


def _synthesis() -> EvidenceSynthesis:
    return EvidenceSynthesis.model_validate_json(
        (FIXTURES / "evidence_synthesis" / "happy_path__call_0.json").read_text(encoding="utf-8")
    )


def _evidence() -> EvidenceBundle:
    from datetime import UTC, datetime

    return EvidenceBundle.model_validate(
        {
            "items": [
                {
                    "evidence_id": "ev-support-001",
                    "source_type": "user_material",
                    "title": "Server support title",
                    "locator": "fixture://evidence/ev-support-001",
                    "retrieved_at": datetime(2026, 1, 1, tzinfo=UTC),
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-support"],
                    "summary": "Server support summary",
                    "content_hash": "sha256:server-support",
                    "provider": "fake_search",
                    "metadata": {
                        "license": "MIT",
                        "baseline_reproduced": "true",
                        "baseline_reproduced_metric": "primary_metric=0.50",
                        "baseline_compute_fit": "true",
                        "baseline_parity_verified": "true",
                        "dataset_fingerprint": "sha256:fixture-dataset",
                        "environment_fingerprint": "sha256:fixture-environment",
                    },
                },
                {
                    "evidence_id": "ev-ablation-001",
                    "source_type": "user_material",
                    "title": "Server ablation title",
                    "locator": "fixture://evidence/ev-ablation-001",
                    "retrieved_at": datetime(2026, 1, 1, tzinfo=UTC),
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-ablation"],
                    "summary": "Server ablation summary",
                    "content_hash": "sha256:server-ablation",
                    "provider": "fake_search",
                    "metadata": {"license": "MIT"},
                },
            ],
            "accepted_ids": ["ev-support-001", "ev-ablation-001"],
            "coverage_by_gap": {"gap-support": 1, "gap-ablation": 1},
        }
    )


def test_bind_method_evidence_replaces_model_authored_provenance() -> None:
    method = _method()
    evidence = _evidence()

    bound = bind_method_evidence(method, evidence, _synthesis())
    by_id = {item.evidence_id: item for item in bound.methodology_plan.evidence}

    assert by_id["ev-support-001"].title == "Server support title"
    assert by_id["ev-support-001"].stable_identifier == "fixture://evidence/ev-support-001"
    assert by_id["ev-support-001"].content_hash == "sha256:server-support"
    assert by_id["ev-support-001"].supported_claims == ("Claim support rate is a minimal metric.",)
    assert by_id["ev-support-001"].license == "MIT"
    assert bound.methodology_plan.baseline.license == "MIT"
    assert {module.license for module in bound.methodology_plan.modules} == {"MIT"}


def test_bind_method_evidence_rejects_unknown_canonical_id() -> None:
    method = _method()
    payload = method.model_dump(mode="json")
    payload["evidence_ids"].append("ev-invented")
    payload["methodology_plan"]["evidence"].append(
        {
            "evidence_id": "ev-invented",
            "source_type": "paper",
            "title": "Invented",
            "stable_identifier": "doi:10.0/invented",
            "verified": True,
            "supported_claims": ["Invented claim"],
            "limitations": [],
            "content_hash": "sha256:invented",
            "license": "MIT",
            "repository_ref": None,
        }
    )
    invented = MethodProposal.model_validate(payload)

    with pytest.raises(ValueError, match="not accepted"):
        bind_method_evidence(invented, _evidence(), _synthesis())


def test_accepted_evidence_ledger_exposes_only_server_owned_fields() -> None:
    ledger = accepted_evidence_ledger(_evidence())

    assert [item["evidence_id"] for item in ledger] == [
        "ev-support-001",
        "ev-ablation-001",
    ]
    assert ledger[0]["metadata"] == {
        "license": "MIT",
        "baseline_reproduced": "true",
        "baseline_reproduced_metric": "primary_metric=0.50",
        "baseline_compute_fit": "true",
        "baseline_parity_verified": "true",
        "dataset_fingerprint": "sha256:fixture-dataset",
        "environment_fingerprint": "sha256:fixture-environment",
    }
    assert "verification_status" not in ledger[0]


def test_audit_report_rejects_mismatched_trace_fingerprint() -> None:
    from pydantic import ValidationError

    from paperagent.academic_methodology import MethodAuditReport, audit_method_plan

    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    report = audit_method_plan(bound.methodology_plan)
    payload = report.model_dump(mode="json")
    payload["trace"]["plan_fingerprint"] = "sha256:stale"

    with pytest.raises(ValidationError, match="fingerprints disagree"):
        MethodAuditReport.model_validate(payload)


def test_audit_rejects_license_not_bound_to_evidence() -> None:
    from paperagent.academic_methodology import AuditVerdict, audit_method_plan

    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    changed_plan = bound.methodology_plan.model_copy(
        update={
            "baseline": bound.methodology_plan.baseline.model_copy(update={"license": "Apache-2.0"})
        }
    )
    report = audit_method_plan(changed_plan)

    assert report.verdict is AuditVerdict.NO_GO
    assert "baseline-license" in report.trace.failed_check_ids


def test_quality_gate_recomputes_stale_audit_for_current_method_plan() -> None:
    from paperagent.academic_methodology import audit_method_plan
    from paperagent.nodes.quality_gate import evaluate_quality
    from paperagent.schemas import ExecutionMeta, ResearchPlan, RetrievalState

    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    stale_go_audit = audit_method_plan(bound.methodology_plan)
    changed_plan = bound.methodology_plan.model_copy(
        update={
            "baseline": bound.methodology_plan.baseline.model_copy(
                update={"license": "proprietary-no-reuse"}
            )
        }
    )
    payload = bound.model_dump(mode="json")
    payload["methodology_plan"] = changed_plan.model_dump(mode="json")
    current_method = MethodProposal.model_validate(payload)
    plan = ResearchPlan.model_validate_json(
        (FIXTURES / "planning" / "happy_path__call_0.json").read_text(encoding="utf-8")
    )

    decision = evaluate_quality(
        {
            "plan": plan,
            "retrieval": RetrievalState(round=1),
            "evidence": _evidence(),
            "synthesis": _synthesis(),
            "method": current_method,
            "methodology_audit": stale_go_audit,
            "execution": ExecutionMeta(status="running"),
        }
    )

    assert decision.verdict == "blocked"
    assert "Q_METHODOLOGY_NO_GO" in decision.reason_codes
    assert "Q_METHOD_AUDIT_BASELINE_LICENSE" in decision.reason_codes


def test_bind_method_evidence_clears_model_authored_baseline_execution_facts() -> None:
    evidence = _evidence()
    support = evidence.items[0].model_copy(update={"metadata": {"license": "MIT"}})
    unverified = evidence.model_copy(update={"items": [support, evidence.items[1]]})

    bound = bind_method_evidence(_method(), unverified, _synthesis())
    baseline = bound.methodology_plan.baseline

    assert baseline.reproduced is False
    assert baseline.reproduced_metric is None
    assert baseline.compute_fit is None
    assert baseline.baseline_parity_verified is None
    assert baseline.dataset_fingerprint is None
    assert baseline.environment_fingerprint is None


def test_bind_method_evidence_uses_server_owned_baseline_execution_facts() -> None:
    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    baseline = bound.methodology_plan.baseline

    assert baseline.reproduced is True
    assert baseline.reproduced_metric == "primary_metric=0.50"
    assert baseline.compute_fit is True
    assert baseline.baseline_parity_verified is True
    assert baseline.dataset_fingerprint == "sha256:fixture-dataset"
    assert baseline.environment_fingerprint == "sha256:fixture-environment"


def test_compute_fit_unknown_is_revise_but_explicit_false_is_no_go() -> None:
    from paperagent.academic_methodology import AuditVerdict, audit_method_plan

    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    unknown = bound.methodology_plan.model_copy(
        update={
            "baseline": bound.methodology_plan.baseline.model_copy(update={"compute_fit": None})
        }
    )
    incompatible = bound.methodology_plan.model_copy(
        update={
            "baseline": bound.methodology_plan.baseline.model_copy(update={"compute_fit": False})
        }
    )

    assert audit_method_plan(unknown).verdict is AuditVerdict.REVISE
    assert audit_method_plan(incompatible).verdict is AuditVerdict.NO_GO


def test_forged_go_audit_with_failed_critical_check_is_rejected() -> None:
    from paperagent.academic_methodology import (
        AuditCheck,
        AuditSeverity,
        AuditVerdict,
        ClaimStatus,
        MethodAuditReport,
        MethodAuditTrace,
    )

    checks = (
        AuditCheck(
            check_id="baseline-license",
            passed=False,
            severity=AuditSeverity.CRITICAL,
            status=ClaimStatus.UNKNOWN,
            message="baseline license failed",
        ),
    )
    trace = MethodAuditTrace(
        plan_fingerprint="a" * 64,
        passed_check_ids=(),
        failed_check_ids=("baseline-license",),
        evidence_ids=(),
        module_ids=(),
        experiment_ids=(),
    )
    try:
        MethodAuditReport(
            verdict=AuditVerdict.GO,
            reasons=("forged",),
            baseline_decision="ready",
            checks=checks,
            missing_evidence=(),
            risks=("baseline license failed",),
            implementation_steps=(),
            experiment_matrix=(),
            method_section_outline=(),
            plan_fingerprint="a" * 64,
            trace=trace,
        )
    except ValueError as exc:
        assert "does not match expected" in str(exc)
        assert "NO_GO" in str(exc)
    else:
        raise AssertionError("forged GO audit with failed critical check was accepted")


def test_forged_go_audit_with_failed_error_check_is_rejected() -> None:
    from paperagent.academic_methodology import (
        AuditCheck,
        AuditSeverity,
        AuditVerdict,
        ClaimStatus,
        MethodAuditReport,
        MethodAuditTrace,
    )

    checks = (
        AuditCheck(
            check_id="research-contract-complete",
            passed=False,
            severity=AuditSeverity.ERROR,
            status=ClaimStatus.PROPOSED,
            message="research contract incomplete",
        ),
    )
    trace = MethodAuditTrace(
        plan_fingerprint="b" * 64,
        passed_check_ids=(),
        failed_check_ids=("research-contract-complete",),
        evidence_ids=(),
        module_ids=(),
        experiment_ids=(),
    )
    try:
        MethodAuditReport(
            verdict=AuditVerdict.GO,
            reasons=("forged",),
            baseline_decision="ready",
            checks=checks,
            missing_evidence=(),
            risks=("research contract incomplete",),
            implementation_steps=(),
            experiment_matrix=(),
            method_section_outline=(),
            plan_fingerprint="b" * 64,
            trace=trace,
        )
    except ValueError as exc:
        assert "does not match expected" in str(exc)
        assert "REVISE" in str(exc)
    else:
        raise AssertionError("forged GO audit with failed error check was accepted")


def test_valid_go_audit_with_all_checks_passed_is_accepted() -> None:
    from paperagent.academic_methodology import (
        AuditCheck,
        AuditSeverity,
        AuditVerdict,
        ClaimStatus,
        MethodAuditReport,
        MethodAuditTrace,
    )

    checks = (
        AuditCheck(
            check_id="baseline-license",
            passed=True,
            severity=AuditSeverity.CRITICAL,
            status=ClaimStatus.VERIFIED,
            message="baseline license ok",
        ),
    )
    trace = MethodAuditTrace(
        plan_fingerprint="c" * 64,
        passed_check_ids=("baseline-license",),
        failed_check_ids=(),
        evidence_ids=(),
        module_ids=(),
        experiment_ids=(),
    )
    report = MethodAuditReport(
        verdict=AuditVerdict.GO,
        reasons=("all checks passed",),
        baseline_decision="ready",
        checks=checks,
        missing_evidence=(),
        risks=(),
        implementation_steps=(),
        experiment_matrix=(),
        method_section_outline=(),
        plan_fingerprint="c" * 64,
        trace=trace,
    )
    assert report.verdict is AuditVerdict.GO


@pytest.mark.asyncio
async def test_quality_gate_node_persists_recomputed_audit(fixed_time: datetime) -> None:
    from paperagent.academic_methodology import audit_method_plan, method_plan_fingerprint
    from paperagent.nodes.quality_gate import quality_gate_node
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ExecutionMeta, ResearchPlan, RetrievalState
    from paperagent.testing import FixedClock, SequenceIdFactory

    bound = bind_method_evidence(_method(), _evidence(), _synthesis())
    stale_audit = audit_method_plan(bound.methodology_plan)
    changed_plan = bound.methodology_plan.model_copy(
        update={
            "baseline": bound.methodology_plan.baseline.model_copy(
                update={"license": "proprietary-no-reuse"}
            )
        }
    )
    payload = bound.model_dump(mode="json")
    payload["methodology_plan"] = changed_plan.model_dump(mode="json")
    current_method = MethodProposal.model_validate(payload)
    plan = ResearchPlan.model_validate_json(
        (FIXTURES / "planning" / "happy_path__call_0.json").read_text(encoding="utf-8")
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("quality"),
        InMemoryStateStore(),
    )
    patch = await quality_gate_node(
        {
            "plan": plan,
            "retrieval": RetrievalState(round=1),
            "evidence": _evidence(),
            "synthesis": _synthesis(),
            "method": current_method,
            "methodology_audit": stale_audit,
            "execution": ExecutionMeta(status="running"),
        },
        {"configurable": {"services": services}},
    )

    assert patch["quality"] is not None
    assert patch["quality"].verdict == "blocked"
    assert patch["methodology_audit"] is not None
    assert patch["methodology_audit"].plan_fingerprint == method_plan_fingerprint(changed_plan)
    assert patch["methodology_audit"].plan_fingerprint != stale_audit.plan_fingerprint

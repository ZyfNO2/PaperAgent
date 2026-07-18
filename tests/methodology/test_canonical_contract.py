from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from paperagent.academic_methodology import (
    AuditVerdict,
    MethodPlan,
    audit_method_plan,
    method_plan_fingerprint,
)
from paperagent.academic_tailoring import (
    TailoringDecision,
    TailoringTask,
    compose_tailored_research_proposal,
)
from paperagent.academic_tailoring_fixtures import load_tailoring_task_bundle
from paperagent.plugins.academic_method import AcademicMethodTailoringPlugin
from paperagent.plugins.contracts import PluginRequest
from paperagent.schemas.evidence import EvidenceItem

ROOT = Path(__file__).resolve().parents[2]
GO_PLAN = ROOT / "examples" / "v0_8" / "go-plan.json"
NPC_BUNDLE = ROOT / "evals" / "academic_tailoring" / "npc"


def _go_plan() -> MethodPlan:
    return MethodPlan.model_validate_json(GO_PLAN.read_text(encoding="utf-8"))


def _npc_task() -> TailoringTask:
    return load_tailoring_task_bundle(NPC_BUNDLE)


def test_method_plan_fingerprint_is_stable_and_content_sensitive() -> None:
    plan = _go_plan()
    first = method_plan_fingerprint(plan)
    second = method_plan_fingerprint(
        MethodPlan.model_validate(plan.model_dump(mode="json"))
    )
    changed = plan.model_copy(
        update={
            "research": plan.research.model_copy(
                update={"intended_claim": "A narrower falsifiable claim"}
            )
        }
    )

    assert first == second
    assert first != method_plan_fingerprint(changed)


def test_audit_trace_is_content_free_and_uses_the_same_fingerprint() -> None:
    plan = _go_plan()
    report = audit_method_plan(plan)
    serialized = json.dumps(report.trace.model_dump(mode="json"), sort_keys=True)

    assert report.verdict is AuditVerdict.GO
    assert report.plan_fingerprint == method_plan_fingerprint(plan)
    assert report.trace.plan_fingerprint == report.plan_fingerprint
    assert plan.evidence[0].title not in serialized
    assert plan.evidence[0].supported_claims[0] not in serialized


def test_plugin_audit_is_a_thin_adapter_over_the_canonical_engine() -> None:
    plan = _go_plan()
    direct = audit_method_plan(plan)
    result = AcademicMethodTailoringPlugin().invoke(
        PluginRequest(
            request_id="canonical-parity",
            operation="audit",
            payload=plan.model_dump(mode="json"),
        )
    )

    assert result.output["verdict"] == direct.verdict.value
    assert result.output["plan_fingerprint"] == direct.plan_fingerprint
    assert result.evidence["audit_policy"] == direct.policy_version


def test_proposal_go_requires_canonical_audit_go() -> None:
    proposal = compose_tailored_research_proposal(_npc_task())

    assert proposal.decision is TailoringDecision.GO
    assert proposal.audit_verdict is AuditVerdict.GO
    assert proposal.failed_audit_checks == ()
    assert proposal.plan_fingerprint
    assert proposal.proposal_fingerprint


def test_missing_baseline_parity_forces_revision() -> None:
    task = _npc_task()
    payload = task.model_dump(mode="json")
    payload["reproduction"]["baseline_parity_verified"] = False
    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.decision is TailoringDecision.REVISE
    assert proposal.audit_verdict is AuditVerdict.REVISE
    assert "baseline-parity" in proposal.failed_audit_checks


def test_missing_module_execution_contract_forces_revision() -> None:
    task = _npc_task()
    payload = task.model_dump(mode="json")
    payload["module_intents"][0]["implementation_switch"] = None
    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.decision is TailoringDecision.REVISE
    assert any(
        check_id.startswith("module-contract:")
        for check_id in proposal.failed_audit_checks
    )


def test_missing_strong_comparison_forces_revision() -> None:
    task = _npc_task()
    payload = task.model_dump(mode="json")
    payload["strong_comparisons"] = []
    proposal = compose_tailored_research_proposal(TailoringTask.model_validate(payload))

    assert proposal.decision is TailoringDecision.REVISE
    assert "strong-comparison-arm" in proposal.failed_audit_checks


def test_multi_module_plan_requires_explicit_interaction_analysis() -> None:
    payload = _go_plan().model_dump(mode="json")
    first_module = payload["modules"][0]
    second_module = dict(first_module)
    second_module["name"] = "support-scorer-secondary"
    payload["modules"].append(second_module)

    for experiment in payload["experiments"]:
        if experiment["arm_type"] == "full":
            experiment["included_modules"] = [
                "support-scorer",
                "support-scorer-secondary",
            ]
    common = dict(payload["experiments"][0])
    common.update(
        {
            "name": "support-secondary-only",
            "arm_type": "single_module",
            "included_modules": ["support-scorer-secondary"],
            "purpose": "measure the second module in isolation",
            "contrast": "second module versus frozen baseline",
        }
    )
    payload["experiments"].append(common)
    for omitted, included in (
        ("support-scorer", "support-scorer-secondary"),
        ("support-scorer-secondary", "support-scorer"),
    ):
        leave_one_out = dict(payload["experiments"][0])
        leave_one_out.update(
            {
                "name": f"without-{omitted}",
                "arm_type": "leave_one_out",
                "included_modules": [included],
                "purpose": f"test the plan without {omitted}",
                "contrast": f"full method versus method without {omitted}",
            }
        )
        payload["experiments"].append(leave_one_out)

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert "module-interaction-analysis" in report.trace.failed_check_ids


def test_incompatible_license_is_no_go() -> None:
    plan = _go_plan()
    changed = plan.model_copy(
        update={
            "baseline": plan.baseline.model_copy(
                update={"license": "proprietary-no-reuse"}
            )
        }
    )
    report = audit_method_plan(changed)

    assert report.verdict is AuditVerdict.NO_GO
    assert "baseline-license" in report.trace.failed_check_ids


def test_verified_evidence_preserves_stable_identifier_metadata() -> None:
    item = EvidenceItem(
        evidence_id="ev-doi",
        source_type="paper",
        title="Verified paper",
        locator="https://example.invalid/paper",
        retrieved_at=datetime.now(tz=UTC),
        verification_status="accepted",
        supports_gap_ids=["gap-1"],
        summary="Verified metadata fixture",
        content_hash="sha256:fixture",
        provider="openalex",
        metadata={"doi": "10.1000/verified-fixture"},
    )

    assert item.provider == "openalex"
    assert item.stable_identifier == "doi:10.1000/verified-fixture"

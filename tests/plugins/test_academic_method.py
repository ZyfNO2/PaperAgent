from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from paperagent.plugins import PluginRequest
from paperagent.plugins.academic_method import (
    METHOD_AUDIT_POLICY_VERSION,
    METHOD_PLAN_CONTRACT_VERSION,
    AcademicMethodTailoringPlugin,
    AuditVerdict,
    MethodPlan,
    audit_method_plan,
)

_ROOT = Path(__file__).resolve().parents[2]
_GO_PLAN = _ROOT / "examples" / "v0_8" / "go-plan.json"


def _complete_plan_payload() -> dict[str, object]:
    value = json.loads(_GO_PLAN.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_complete_plan_receives_go_verdict() -> None:
    report = audit_method_plan(MethodPlan.model_validate(_complete_plan_payload()))

    assert report.verdict is AuditVerdict.GO
    assert all(check.passed for check in report.checks)
    assert report.baseline_decision == "verified, reproducible, and parity-checked"
    assert len(report.experiment_matrix) == 4
    assert report.plan_fingerprint == report.trace.plan_fingerprint


def test_unreproduced_baseline_requires_revision() -> None:
    payload = _complete_plan_payload()
    baseline = payload["baseline"]
    assert isinstance(baseline, dict)
    baseline["reproduced"] = False
    baseline["reproduced_metric"] = None

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert any(
        check.check_id == "baseline-reproduced" and not check.passed
        for check in report.checks
    )


def test_compute_incompatible_plan_is_no_go() -> None:
    payload = _complete_plan_payload()
    baseline = payload["baseline"]
    assert isinstance(baseline, dict)
    baseline["compute_fit"] = False

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.NO_GO
    assert any(
        check.check_id == "baseline-compute-fit" and not check.passed
        for check in report.checks
    )


def test_shape_only_module_contract_is_rejected() -> None:
    payload = deepcopy(_complete_plan_payload())
    modules = payload["modules"]
    assert isinstance(modules, list)
    first = modules[0]
    assert isinstance(first, dict)
    first["input_semantics"] = "tensor"

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert any(
        check.check_id == "module-contract:support-scorer" and not check.passed
        for check in report.checks
    )


def test_plugin_template_does_not_invent_research_content() -> None:
    plugin = AcademicMethodTailoringPlugin()

    result = plugin.invoke(
        PluginRequest(request_id="template-1", operation="template", payload={})
    )

    baseline = result.output["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["reproduced"] is False
    assert result.output["contract_version"] == METHOD_PLAN_CONTRACT_VERSION
    assert result.evidence["llm_used"] is False


def test_plugin_audit_returns_stable_metadata() -> None:
    plugin = AcademicMethodTailoringPlugin()

    result = plugin.invoke(
        PluginRequest(
            request_id="audit-1",
            operation="audit",
            payload=_complete_plan_payload(),
        )
    )

    assert result.plugin_name == "academic-method-tailoring"
    assert result.plugin_version == "0.9.0"
    assert result.output["verdict"] == "GO"
    assert result.output["contract_version"] == METHOD_PLAN_CONTRACT_VERSION
    assert result.output["policy_version"] == METHOD_AUDIT_POLICY_VERSION
    assert result.evidence["audit_policy"] == METHOD_AUDIT_POLICY_VERSION
    assert result.evidence["contract_version"] == METHOD_PLAN_CONTRACT_VERSION
    assert result.evidence["network_used"] is False
    assert result.evidence["llm_used"] is False
    assert result.evidence["verdict"] == "GO"
    assert result.evidence["failed_check_count"] == 0
    assert result.evidence["plan_fingerprint"] == result.output["plan_fingerprint"]

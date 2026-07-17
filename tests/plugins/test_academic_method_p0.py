from __future__ import annotations

import json
from pathlib import Path

from paperagent.plugins import MethodPlan, audit_method_plan
from paperagent.plugins.academic_method import AuditVerdict

_EXAMPLE = Path("examples/v0_8/go-plan.json")


def _go_payload() -> dict[str, object]:
    payload = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_empty_module_plan_cannot_receive_go() -> None:
    payload = _go_payload()
    payload["modules"] = []

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert any(
        check.check_id == "proposed-modules-present" and not check.passed
        for check in report.checks
    )


def test_baseline_arm_with_proposed_module_cannot_receive_go() -> None:
    payload = _go_payload()
    experiments = payload["experiments"]
    assert isinstance(experiments, list)
    baseline = next(
        item
        for item in experiments
        if isinstance(item, dict) and item.get("arm_type") == "baseline"
    )
    baseline["included_modules"] = ["support-scorer"]

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert any(
        check.check_id == "experiment-baseline-arm" and not check.passed
        for check in report.checks
    )

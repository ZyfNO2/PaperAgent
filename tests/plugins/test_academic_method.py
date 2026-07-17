from __future__ import annotations

from copy import deepcopy

from paperagent.plugins import PluginRequest
from paperagent.plugins.academic_method import (
    AcademicMethodTailoringPlugin,
    AuditVerdict,
    MethodPlan,
    audit_method_plan,
)


def _complete_plan_payload() -> dict[str, object]:
    shared_experiment = {
        "dataset": "dataset-v1",
        "split": "official-split-v1",
        "preprocessing": "preprocess-v1",
        "tuning_budget": "20 trials per arm",
        "metrics": ["accuracy", "unsupported_claim_rate"],
        "seeds": [1, 2, 3],
        "uncertainty_reporting": "mean and 95% bootstrap interval",
        "resource_measures": ["wall_clock_seconds", "peak_memory_mb"],
        "stopping_criteria": "stop after the fixed budget",
    }

    def arm(
        name: str,
        arm_type: str,
        included_modules: list[str],
    ) -> dict[str, object]:
        return {
            "name": name,
            "arm_type": arm_type,
            "included_modules": included_modules,
            **shared_experiment,
        }

    def module(name: str, evidence_id: str) -> dict[str, object]:
        return {
            "name": name,
            "evidence_id": evidence_id,
            "license": "Apache-2.0",
            "original_role": "evidence scoring",
            "proposed_role": "claim support scoring",
            "input_semantics": "ordered claim and evidence feature sequence",
            "output_semantics": "calibrated support probability per claim",
            "input_shape": "batch x claims x features",
            "output_shape": "batch x claims",
            "normalization": "z-score using training split statistics",
            "masks": "mask padded claims and absent evidence",
            "ordering": "preserve claim order from the report schema",
            "trainable": True,
            "loss_terms": ["binary_cross_entropy"],
            "compute_cost": "less than 10% baseline latency",
            "assumptions": ["evidence identifiers are verified"],
            "predicted_effect": "reduce unsupported claims",
            "failure_mode": "miscalibration under domain shift",
        }

    return {
        "research": {
            "target_problem": "unsupported claims in scientific reports",
            "scientific_setting": "single-user bounded research workflow",
            "success_metric": "unsupported_claim_rate",
            "constraints": ["single machine", "fixed retrieval budget"],
            "intended_claim": "the intervention improves groundedness under fixed cost",
            "observed_problem": "accepted reports contain weakly supported claims",
            "proposed_mechanism": "explicit support scoring filters weak claims",
        },
        "baseline": {
            "name": "paperagent-v0.6",
            "version_or_commit": "abc123",
            "source_evidence_id": "ev-baseline",
            "license": "MIT",
            "dataset": "dataset-v1",
            "split": "official-split-v1",
            "environment": "Python 3.12, CPU",
            "seed_policy": "seeds 1, 2, 3",
            "reproduced": True,
            "reproduced_metric": "unsupported_claim_rate=0.18",
            "compute_fit": True,
        },
        "hypothesis": {
            "condition": "when retrieved evidence is sparse or conflicting",
            "limitation": "the baseline accepts weakly supported claims",
            "mechanism": "claim support is not explicitly calibrated",
            "intervention": "add support scoring and conservative filtering",
            "predicted_metric_change": "unsupported_claim_rate decreases",
            "guardrail": "task success and citation coverage do not decrease",
        },
        "modules": [
            module("support-scorer", "ev-support"),
            module("claim-filter", "ev-filter"),
        ],
        "experiments": [
            arm("baseline", "baseline", []),
            arm("full", "full", ["support-scorer", "claim-filter"]),
            arm("support-only", "single_module", ["support-scorer"]),
            arm("filter-only", "single_module", ["claim-filter"]),
            arm("without-support", "leave_one_out", ["claim-filter"]),
            arm("without-filter", "leave_one_out", ["support-scorer"]),
        ],
        "evidence": [
            {
                "evidence_id": "ev-baseline",
                "source_type": "repository",
                "title": "Frozen baseline implementation",
                "stable_identifier": "commit:abc123",
                "verified": True,
                "supported_claims": ["baseline implementation and metric"],
                "limitations": ["single dataset"],
            },
            {
                "evidence_id": "ev-support",
                "source_type": "paper",
                "title": "Support scoring source",
                "stable_identifier": "doi:10.1000/support",
                "verified": True,
                "supported_claims": ["support scoring mechanism"],
                "limitations": ["domain transfer unknown"],
            },
            {
                "evidence_id": "ev-filter",
                "source_type": "paper",
                "title": "Claim filtering source",
                "stable_identifier": "doi:10.1000/filter",
                "verified": True,
                "supported_claims": ["conservative filtering mechanism"],
                "limitations": ["recall trade-off"],
            },
        ],
        "stop_conditions": [
            "stop if baseline cannot be reproduced",
            "stop if citation coverage decreases by more than 2 percentage points",
        ],
    }


def test_complete_plan_receives_go_verdict() -> None:
    report = audit_method_plan(MethodPlan.model_validate(_complete_plan_payload()))

    assert report.verdict is AuditVerdict.GO
    assert all(check.passed for check in report.checks)
    assert report.baseline_decision == "verified and reproducible"
    assert len(report.experiment_matrix) == 6


def test_unreproduced_baseline_requires_revision() -> None:
    payload = _complete_plan_payload()
    baseline = payload["baseline"]
    assert isinstance(baseline, dict)
    baseline["reproduced"] = False
    baseline["reproduced_metric"] = None

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.REVISE
    assert any(check.check_id == "baseline-reproduced" and not check.passed for check in report.checks)


def test_compute_incompatible_plan_is_no_go() -> None:
    payload = _complete_plan_payload()
    baseline = payload["baseline"]
    assert isinstance(baseline, dict)
    baseline["compute_fit"] = False

    report = audit_method_plan(MethodPlan.model_validate(payload))

    assert report.verdict is AuditVerdict.NO_GO
    assert any(check.check_id == "baseline-compute-fit" and not check.passed for check in report.checks)


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
    assert result.plugin_version == "0.8.0"
    assert result.output["verdict"] == "GO"
    assert result.evidence == {
        "audit_policy": "academic-method-tailoring-v0.8",
        "network_used": False,
        "llm_used": False,
    }

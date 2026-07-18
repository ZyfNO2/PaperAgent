from __future__ import annotations

from typing import Any, cast

from paperagent.academic_tailoring import TailoringTask
from paperagent.academic_tailoring_guard import compose_tailored_research_proposal
from paperagent.plugins import academic_method as _implementation
from paperagent.plugins.academic_method import (
    AcademicMethodTailoringPlugin as _BaseAcademicMethodTailoringPlugin,
)
from paperagent.plugins.academic_method import (
    AuditCheck,
    AuditSeverity,
    AuditVerdict,
    ClaimStatus,
    ExperimentArmType,
    MethodAuditReport,
    MethodPlan,
)
from paperagent.plugins.contracts import (
    PluginError,
    PluginErrorCode,
    PluginRequest,
    PluginResult,
)

_base_audit_method_plan = _implementation.audit_method_plan


def audit_method_plan(plan: MethodPlan) -> MethodAuditReport:
    """Apply release-blocking invariants missing from the original v0.8 audit."""
    report = _base_audit_method_plan(plan)
    checks = list(report.checks)

    checks.append(
        AuditCheck(
            check_id="proposed-modules-present",
            passed=bool(plan.modules),
            severity=AuditSeverity.ERROR,
            status=ClaimStatus.PROPOSED,
            message="method plan proposes at least one attributed intervention module",
        )
    )

    baseline_arms = tuple(
        arm for arm in plan.experiments if arm.arm_type is ExperimentArmType.BASELINE
    )
    clean_baseline = len(baseline_arms) == 1 and not baseline_arms[0].included_modules
    checks = [
        (
            item.model_copy(
                update={
                    "passed": clean_baseline,
                    "message": (
                        "experiment matrix contains exactly one frozen baseline arm "
                        "with no proposed modules"
                    ),
                }
            )
            if item.check_id == "experiment-baseline-arm"
            else item
        )
        for item in checks
    ]

    critical_failures = tuple(
        item for item in checks if not item.passed and item.severity is AuditSeverity.CRITICAL
    )
    failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO

    risks = tuple(item.message for item in failures if item.severity is not AuditSeverity.NOTE)
    reasons = risks or ("all deterministic audit gates passed",)
    return report.model_copy(
        update={
            "verdict": verdict,
            "checks": tuple(checks),
            "risks": risks,
            "reasons": reasons,
        }
    )


class AcademicMethodTailoringPlugin(_BaseAcademicMethodTailoringPlugin):
    _manifest = _BaseAcademicMethodTailoringPlugin._manifest.model_copy(
        update={
            "operations": ("audit", "template", "propose"),
            "description": (
                "Deterministic academic method proposal generation and evidence, "
                "compatibility, novelty, and ablation audit."
            ),
        }
    )

    def invoke(self, request: PluginRequest) -> PluginResult:
        if request.operation != "propose":
            return super().invoke(request)
        try:
            task = TailoringTask.model_validate(request.payload)
            proposal = compose_tailored_research_proposal(task)
        except ValueError as exc:
            raise PluginError(
                PluginErrorCode.INVOCATION_FAILED,
                "academic tailoring task failed validation or proposal generation",
                plugin_name=self.manifest.name,
            ) from exc
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output=cast(dict[str, object], proposal.model_dump(mode="json")),
            evidence={
                "proposal_policy": "academic-method-tailoring-proposal-v1",
                "network_used": False,
                "llm_used": False,
                "result_status": "simulated_or_proposed",
            },
        )


# Keep direct submodule imports, the built-in registry, and the CLI on one policy.
_implementation.audit_method_plan = audit_method_plan
_implementation_dynamic: Any = _implementation
_implementation_dynamic.AcademicMethodTailoringPlugin = AcademicMethodTailoringPlugin

__all__ = ["AcademicMethodTailoringPlugin", "audit_method_plan"]

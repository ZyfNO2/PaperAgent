from __future__ import annotations

from paperagent.plugins import academic_method as _implementation
from paperagent.plugins.academic_method import (
    AcademicMethodTailoringPlugin,
    AuditCheck,
    AuditSeverity,
    AuditVerdict,
    ClaimStatus,
    ExperimentArmType,
    MethodAuditReport,
    MethodPlan,
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


# The package imports this guard before callers reach the implementation submodule.
# Rebinding keeps direct submodule imports, the built-in plugin, and the CLI on one policy.
_implementation.audit_method_plan = audit_method_plan

__all__ = ["AcademicMethodTailoringPlugin", "audit_method_plan"]

from __future__ import annotations

from typing import cast

from paperagent.academic_methodology import (
    METHOD_AUDIT_POLICY_VERSION,
    METHOD_PLAN_CONTRACT_VERSION,
    AuditCheck,
    AuditSeverity,
    AuditVerdict,
    BaselineCard,
    ClaimStatus,
    EvidenceItem,
    ExperimentArmType,
    ExperimentCard,
    ExperimentSummary,
    FalsifiableHypothesis,
    MethodAuditReport,
    MethodAuditTrace,
    MethodPlan,
    ModuleCard,
    ResearchContract,
    audit_method_plan,
    method_plan_fingerprint,
    method_plan_template,
)
from paperagent.academic_tailoring import (
    TailoringTask,
    compose_tailored_research_proposal,
)
from paperagent.plugins.contracts import (
    PluginCapability,
    PluginError,
    PluginErrorCode,
    PluginManifest,
    PluginRequest,
    PluginResult,
)


class AcademicMethodTailoringPlugin:
    """Thin plugin adapter over the canonical academic-methodology domain.

    The plugin owns transport validation and error translation only. Scientific
    contracts, fingerprints, checks, and verdict policy live in
    :mod:`paperagent.academic_methodology`.
    """

    _manifest = PluginManifest(
        name="academic-method-tailoring",
        version="0.9.0",
        description=(
            "Canonical academic method proposal generation and deterministic "
            "evidence, compatibility, novelty, experiment, and provenance audit."
        ),
        capabilities=(PluginCapability.RESEARCH_METHOD, PluginCapability.EVALUATION),
        operations=("audit", "template", "propose"),
        deterministic=True,
        requires_network=False,
        writes_files=False,
    )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def invoke(self, request: PluginRequest) -> PluginResult:
        evidence: dict[str, object] = {
            "contract_version": METHOD_PLAN_CONTRACT_VERSION,
            "audit_policy": METHOD_AUDIT_POLICY_VERSION,
            "network_used": False,
            "llm_used": False,
        }
        if request.operation == "template":
            output = method_plan_template()
        elif request.operation == "audit":
            try:
                plan = MethodPlan.model_validate(request.payload)
            except ValueError as exc:
                raise PluginError(
                    PluginErrorCode.INVOCATION_FAILED,
                    "method plan failed schema validation",
                    plugin_name=self.manifest.name,
                ) from exc
            report = audit_method_plan(plan)
            output = cast(dict[str, object], report.model_dump(mode="json"))
            evidence.update(
                {
                    "plan_fingerprint": report.plan_fingerprint,
                    "verdict": report.verdict.value,
                    "failed_check_count": len(report.trace.failed_check_ids),
                }
            )
        elif request.operation == "propose":
            try:
                task = TailoringTask.model_validate(request.payload)
                proposal = compose_tailored_research_proposal(task)
            except ValueError as exc:
                raise PluginError(
                    PluginErrorCode.INVOCATION_FAILED,
                    "academic tailoring task failed validation or proposal generation",
                    plugin_name=self.manifest.name,
                ) from exc
            output = cast(dict[str, object], proposal.model_dump(mode="json"))
            evidence.update(
                {
                    "proposal_policy": "academic-method-tailoring-proposal-v2",
                    "result_status": "simulated_or_proposed",
                    "evidence_scope": proposal.evidence_scope.value,
                    "readiness": proposal.readiness.value,
                    "scientific_release_ready": proposal.scientific_release_ready,
                    "proposal_fingerprint": getattr(proposal, "proposal_fingerprint", None),
                    "plan_fingerprint": getattr(proposal, "plan_fingerprint", None),
                    "audit_verdict": getattr(proposal, "audit_verdict", None),
                }
            )
        else:
            raise PluginError(
                PluginErrorCode.OPERATION_UNSUPPORTED,
                f"unsupported academic method operation: {request.operation}",
                plugin_name=self.manifest.name,
            )
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output=output,
            evidence=evidence,
        )


__all__ = [
    "METHOD_AUDIT_POLICY_VERSION",
    "METHOD_PLAN_CONTRACT_VERSION",
    "AcademicMethodTailoringPlugin",
    "AuditCheck",
    "AuditSeverity",
    "AuditVerdict",
    "BaselineCard",
    "ClaimStatus",
    "EvidenceItem",
    "ExperimentArmType",
    "ExperimentCard",
    "ExperimentSummary",
    "FalsifiableHypothesis",
    "MethodAuditReport",
    "MethodAuditTrace",
    "MethodPlan",
    "ModuleCard",
    "ResearchContract",
    "audit_method_plan",
    "method_plan_fingerprint",
    "method_plan_template",
]

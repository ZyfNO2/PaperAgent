from __future__ import annotations

from enum import StrEnum
from typing import cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paperagent.plugins.contracts import (
    PluginCapability,
    PluginError,
    PluginErrorCode,
    PluginManifest,
    PluginRequest,
    PluginResult,
)


class AuditVerdict(StrEnum):
    GO = "GO"
    REVISE = "REVISE"
    NO_GO = "NO_GO"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    PROPOSED = "proposed"
    UNKNOWN = "unknown"


class AuditSeverity(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class ExperimentArmType(StrEnum):
    BASELINE = "baseline"
    FULL = "full"
    SINGLE_MODULE = "single_module"
    LEAVE_ONE_OUT = "leave_one_out"
    OTHER = "other"


class ResearchContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_problem: str | None = None
    scientific_setting: str | None = None
    success_metric: str | None = None
    constraints: tuple[str, ...] = ()
    intended_claim: str | None = None
    observed_problem: str | None = None
    proposed_mechanism: str | None = None


class BaselineCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    version_or_commit: str | None = None
    source_evidence_id: str | None = None
    license: str | None = None
    dataset: str | None = None
    split: str | None = None
    environment: str | None = None
    seed_policy: str | None = None
    reproduced: bool = False
    reproduced_metric: str | None = None
    compute_fit: bool | None = None


class FalsifiableHypothesis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    condition: str | None = None
    limitation: str | None = None
    mechanism: str | None = None
    intervention: str | None = None
    predicted_metric_change: str | None = None
    guardrail: str | None = None


class ModuleCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    evidence_id: str | None = None
    license: str | None = None
    original_role: str | None = None
    proposed_role: str | None = None
    input_semantics: str | None = None
    output_semantics: str | None = None
    input_shape: str | None = None
    output_shape: str | None = None
    normalization: str | None = None
    masks: str | None = None
    ordering: str | None = None
    trainable: bool | None = None
    loss_terms: tuple[str, ...] = ()
    compute_cost: str | None = None
    assumptions: tuple[str, ...] = ()
    predicted_effect: str | None = None
    failure_mode: str | None = None


class ExperimentCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    arm_type: ExperimentArmType
    included_modules: tuple[str, ...] = ()
    dataset: str | None = None
    split: str | None = None
    preprocessing: str | None = None
    tuning_budget: str | None = None
    metrics: tuple[str, ...] = ()
    seeds: tuple[int, ...] = ()
    uncertainty_reporting: str | None = None
    resource_measures: tuple[str, ...] = ()
    stopping_criteria: str | None = None


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    stable_identifier: str | None = None
    verified: bool = False
    supported_claims: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class MethodPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    research: ResearchContract
    baseline: BaselineCard
    hypothesis: FalsifiableHypothesis
    modules: tuple[ModuleCard, ...] = ()
    experiments: tuple[ExperimentCard, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    stop_conditions: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_unique_identifiers(self) -> MethodPlan:
        for label, values in (
            ("module", tuple(item.name for item in self.modules)),
            ("experiment", tuple(item.name for item in self.experiments)),
            ("evidence", tuple(item.evidence_id for item in self.evidence)),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {label} identifier")
        return self


class AuditCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str
    passed: bool
    severity: AuditSeverity
    status: ClaimStatus
    message: str
    evidence_ids: tuple[str, ...] = ()


class ExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    arm_type: ExperimentArmType
    included_modules: tuple[str, ...]
    data_signature: str


class MethodAuditReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: AuditVerdict
    reasons: tuple[str, ...]
    baseline_decision: str
    checks: tuple[AuditCheck, ...]
    missing_evidence: tuple[str, ...]
    risks: tuple[str, ...]
    implementation_steps: tuple[str, ...]
    experiment_matrix: tuple[ExperimentSummary, ...]
    method_section_outline: tuple[str, ...]


def _present(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def _license_is_acceptable(value: str | None) -> bool:
    if not _present(value):
        return False
    assert value is not None
    return value.strip().lower() not in {"unknown", "missing", "unverified", "incompatible"}


def _check(
    check_id: str,
    passed: bool,
    severity: AuditSeverity,
    message: str,
    *,
    evidence_ids: tuple[str, ...] = (),
    status: ClaimStatus | None = None,
) -> AuditCheck:
    resolved_status = status or (ClaimStatus.VERIFIED if passed else ClaimStatus.UNKNOWN)
    return AuditCheck(
        check_id=check_id,
        passed=passed,
        severity=severity,
        status=resolved_status,
        message=message,
        evidence_ids=evidence_ids,
    )


def _data_signature(experiment: ExperimentCard) -> str:
    return "|".join(
        (
            experiment.dataset or "<missing-dataset>",
            experiment.split or "<missing-split>",
            experiment.preprocessing or "<missing-preprocessing>",
        )
    )


def audit_method_plan(plan: MethodPlan) -> MethodAuditReport:
    checks: list[AuditCheck] = []
    evidence_by_id = {item.evidence_id: item for item in plan.evidence}

    research_fields = (
        plan.research.target_problem,
        plan.research.scientific_setting,
        plan.research.success_metric,
        plan.research.intended_claim,
        plan.research.observed_problem,
        plan.research.proposed_mechanism,
    )
    checks.append(
        _check(
            "research-contract-complete",
            all(_present(value) for value in research_fields) and bool(plan.research.constraints),
            AuditSeverity.ERROR,
            (
                "research contract includes problem, setting, metric, constraints, "
                "claim, observation, and mechanism"
            ),
            status=ClaimStatus.PROPOSED,
        )
    )

    baseline = plan.baseline
    baseline_fields = (
        baseline.version_or_commit,
        baseline.source_evidence_id,
        baseline.license,
        baseline.dataset,
        baseline.split,
        baseline.environment,
        baseline.seed_policy,
    )
    checks.append(
        _check(
            "baseline-card-complete",
            all(_present(value) for value in baseline_fields),
            AuditSeverity.ERROR,
            (
                "baseline card records source, version, license, data split, "
                "environment, and seed policy"
            ),
            evidence_ids=(baseline.source_evidence_id,) if baseline.source_evidence_id else (),
        )
    )
    checks.append(
        _check(
            "baseline-reproduced",
            baseline.reproduced and _present(baseline.reproduced_metric),
            AuditSeverity.ERROR,
            "baseline is reproduced with a recorded metric",
            evidence_ids=(baseline.source_evidence_id,) if baseline.source_evidence_id else (),
        )
    )
    checks.append(
        _check(
            "baseline-compute-fit",
            baseline.compute_fit is True,
            AuditSeverity.CRITICAL,
            "baseline fits the declared compute constraints",
            status=ClaimStatus.VERIFIED if baseline.compute_fit is True else ClaimStatus.UNKNOWN,
        )
    )
    checks.append(
        _check(
            "baseline-license",
            _license_is_acceptable(baseline.license),
            AuditSeverity.CRITICAL,
            "baseline license is present and not marked incompatible or unknown",
        )
    )

    baseline_evidence = (
        evidence_by_id.get(baseline.source_evidence_id) if baseline.source_evidence_id else None
    )
    checks.append(
        _check(
            "baseline-provenance",
            baseline_evidence is not None and baseline_evidence.verified,
            AuditSeverity.CRITICAL,
            "baseline provenance references a verified evidence item",
            evidence_ids=(baseline.source_evidence_id,) if baseline.source_evidence_id else (),
        )
    )

    hypothesis_values = (
        plan.hypothesis.condition,
        plan.hypothesis.limitation,
        plan.hypothesis.mechanism,
        plan.hypothesis.intervention,
        plan.hypothesis.predicted_metric_change,
        plan.hypothesis.guardrail,
    )
    checks.append(
        _check(
            "falsifiable-hypothesis",
            all(_present(value) for value in hypothesis_values),
            AuditSeverity.ERROR,
            (
                "hypothesis states condition, limitation, mechanism, intervention, "
                "metric change, and guardrail"
            ),
            status=ClaimStatus.PROPOSED,
        )
    )

    for module in plan.modules:
        semantic_values = (
            module.original_role,
            module.proposed_role,
            module.input_semantics,
            module.output_semantics,
            module.normalization,
            module.masks,
            module.ordering,
            module.compute_cost,
            module.predicted_effect,
            module.failure_mode,
        )
        semantics_complete = all(_present(value) for value in semantic_values)
        shape_only = (module.input_semantics or "").strip().lower() in {
            "tensor",
            "shape-only",
            "shape only",
            "unknown",
        } or (module.output_semantics or "").strip().lower() in {
            "tensor",
            "shape-only",
            "shape only",
            "unknown",
        }
        checks.append(
            _check(
                f"module-contract:{module.name}",
                semantics_complete
                and _present(module.input_shape)
                and _present(module.output_shape)
                and module.trainable is not None
                and bool(module.assumptions)
                and not shape_only,
                AuditSeverity.ERROR,
                (
                    f"module {module.name} has semantic, shape, ordering, training, "
                    "cost, effect, assumption, and failure contracts"
                ),
                evidence_ids=(module.evidence_id,) if module.evidence_id else (),
                status=ClaimStatus.PROPOSED,
            )
        )
        checks.append(
            _check(
                f"module-license:{module.name}",
                _license_is_acceptable(module.license),
                AuditSeverity.CRITICAL,
                f"module {module.name} license is present and compatible",
                evidence_ids=(module.evidence_id,) if module.evidence_id else (),
            )
        )
        module_evidence = evidence_by_id.get(module.evidence_id) if module.evidence_id else None
        checks.append(
            _check(
                f"module-provenance:{module.name}",
                module_evidence is not None and module_evidence.verified,
                AuditSeverity.CRITICAL,
                f"module {module.name} references verified provenance",
                evidence_ids=(module.evidence_id,) if module.evidence_id else (),
            )
        )

    module_names = tuple(module.name for module in plan.modules)
    module_name_set = set(module_names)
    baseline_arms = tuple(
        arm for arm in plan.experiments if arm.arm_type is ExperimentArmType.BASELINE
    )
    full_arms = tuple(arm for arm in plan.experiments if arm.arm_type is ExperimentArmType.FULL)
    checks.append(
        _check(
            "experiment-baseline-arm",
            len(baseline_arms) == 1,
            AuditSeverity.ERROR,
            "experiment matrix contains exactly one frozen baseline arm",
            status=ClaimStatus.PROPOSED,
        )
    )
    checks.append(
        _check(
            "experiment-full-arm",
            len(full_arms) == 1 and set(full_arms[0].included_modules) == module_name_set,
            AuditSeverity.ERROR,
            "experiment matrix contains one full-method arm with every proposed module",
            status=ClaimStatus.PROPOSED,
        )
    )

    for module_name in module_names:
        single_present = any(
            arm.arm_type is ExperimentArmType.SINGLE_MODULE
            and tuple(arm.included_modules) == (module_name,)
            for arm in plan.experiments
        )
        checks.append(
            _check(
                f"single-module-ablation:{module_name}",
                single_present,
                AuditSeverity.ERROR,
                f"single-module arm exists for {module_name}",
                status=ClaimStatus.PROPOSED,
            )
        )
        if len(module_names) > 1:
            expected = module_name_set - {module_name}
            leave_one_out_present = any(
                arm.arm_type is ExperimentArmType.LEAVE_ONE_OUT
                and set(arm.included_modules) == expected
                for arm in plan.experiments
            )
            checks.append(
                _check(
                    f"leave-one-out:{module_name}",
                    leave_one_out_present,
                    AuditSeverity.ERROR,
                    f"leave-one-out arm exists without {module_name}",
                    status=ClaimStatus.PROPOSED,
                )
            )

    reference_signature = _data_signature(baseline_arms[0]) if len(baseline_arms) == 1 else None
    fair_experiments = bool(plan.experiments) and reference_signature is not None
    for experiment in plan.experiments:
        complete = (
            _present(experiment.dataset)
            and _present(experiment.split)
            and _present(experiment.preprocessing)
            and _present(experiment.tuning_budget)
            and bool(experiment.metrics)
            and bool(experiment.seeds)
            and _present(experiment.uncertainty_reporting)
            and bool(experiment.resource_measures)
            and _present(experiment.stopping_criteria)
        )
        fair_experiments = fair_experiments and complete
        if reference_signature is not None:
            fair_experiments = (
                fair_experiments and _data_signature(experiment) == reference_signature
            )
    checks.append(
        _check(
            "experiment-fairness",
            fair_experiments,
            AuditSeverity.ERROR,
            (
                "all comparison arms share data and preprocessing and define tuning, "
                "metrics, seeds, uncertainty, resources, and stopping criteria"
            ),
            status=ClaimStatus.PROPOSED,
        )
    )
    checks.append(
        _check(
            "stop-conditions",
            bool(plan.stop_conditions),
            AuditSeverity.ERROR,
            "plan defines explicit stop conditions",
            status=ClaimStatus.PROPOSED,
        )
    )

    critical_failures = tuple(
        item for item in checks if not item.passed and item.severity is AuditSeverity.CRITICAL
    )
    other_failures = tuple(item for item in checks if not item.passed)
    if critical_failures:
        verdict = AuditVerdict.NO_GO
    elif other_failures:
        verdict = AuditVerdict.REVISE
    else:
        verdict = AuditVerdict.GO

    missing_evidence = tuple(
        sorted(
            {
                evidence_id
                for item in checks
                if not item.passed
                for evidence_id in item.evidence_ids
                if evidence_id not in evidence_by_id or not evidence_by_id[evidence_id].verified
            }
        )
    )
    risks = tuple(item.message for item in other_failures if item.severity != AuditSeverity.NOTE)
    reasons = risks or ("all deterministic audit gates passed",)
    baseline_decision = (
        "verified and reproducible"
        if all(item.passed for item in checks if item.check_id.startswith("baseline-"))
        else "not ready for modification"
    )
    matrix = tuple(
        ExperimentSummary(
            name=experiment.name,
            arm_type=experiment.arm_type,
            included_modules=experiment.included_modules,
            data_signature=_data_signature(experiment),
        )
        for experiment in sorted(plan.experiments, key=lambda item: item.name)
    )
    return MethodAuditReport(
        verdict=verdict,
        reasons=reasons,
        baseline_decision=baseline_decision,
        checks=tuple(checks),
        missing_evidence=missing_evidence,
        risks=risks,
        implementation_steps=(
            "freeze and reproduce the attributed baseline",
            "draw and validate module integration contracts",
            "implement one module at a time behind configuration switches",
            "verify shape, semantics, loss scale, gradients, and tiny-batch behavior",
            "run baseline, full, single-module, leave-one-out, and interaction comparisons",
            "decide GO, REVISE, or NO_GO before writing performance or novelty claims",
        ),
        experiment_matrix=matrix,
        method_section_outline=(
            "problem formulation and notation",
            "system overview and data flow",
            "frozen baseline and inherited components",
            "proposed modules and integration contracts",
            "objectives, losses, and training procedure",
            "complexity and implementation details",
            "explicit differences from attributed sources",
        ),
    )


def method_plan_template() -> dict[str, object]:
    return {
        "research": {
            "target_problem": "",
            "scientific_setting": "",
            "success_metric": "",
            "constraints": [],
            "intended_claim": "",
            "observed_problem": "",
            "proposed_mechanism": "",
        },
        "baseline": {
            "name": "",
            "version_or_commit": "",
            "source_evidence_id": "",
            "license": "",
            "dataset": "",
            "split": "",
            "environment": "",
            "seed_policy": "",
            "reproduced": False,
            "reproduced_metric": None,
            "compute_fit": None,
        },
        "hypothesis": {
            "condition": "",
            "limitation": "",
            "mechanism": "",
            "intervention": "",
            "predicted_metric_change": "",
            "guardrail": "",
        },
        "modules": [],
        "experiments": [],
        "evidence": [],
        "stop_conditions": [],
    }


class AcademicMethodTailoringPlugin:
    _manifest = PluginManifest(
        name="academic-method-tailoring",
        version="0.8.0",
        description=(
            "Deterministic evidence, compatibility, and ablation audit for method proposals."
        ),
        capabilities=(PluginCapability.RESEARCH_METHOD, PluginCapability.EVALUATION),
        operations=("audit", "template"),
        deterministic=True,
        requires_network=False,
        writes_files=False,
    )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def invoke(self, request: PluginRequest) -> PluginResult:
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
            evidence={
                "audit_policy": "academic-method-tailoring-v0.8",
                "network_used": False,
                "llm_used": False,
            },
        )

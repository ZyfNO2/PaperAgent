from __future__ import annotations

import hashlib
import json
import math
import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paperagent.academic_methodology import (
    METHOD_AUDIT_POLICY_VERSION,
    METHOD_PLAN_CONTRACT_VERSION,
    AuditVerdict,
    BaselineCard,
    EvidenceItem,
    ExperimentArmType,
    ExperimentCard,
    FalsifiableHypothesis,
    MethodPlan,
    ModuleCard,
    ResearchContract,
    audit_method_plan,
)

PROPOSAL_POLICY_VERSION = "paperagent.tailoring-proposal.v0.9"


class TailoringDecision(StrEnum):
    GO = "GO"
    REVISE = "REVISE"
    NO_GO = "NO_GO"


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    SYNTHETIC_FIXTURE = "synthetic_fixture"
    UNVERIFIED = "unverified"


class ResultStatus(StrEnum):
    PROPOSED = "proposed"
    OBSERVED = "observed"


class EvidenceScope(StrEnum):
    REAL_VERIFIED = "real_verified"
    SYNTHETIC_EVALUATION = "synthetic_evaluation"
    MIXED_OR_UNVERIFIED = "mixed_or_unverified"


class ProposalReadiness(StrEnum):
    READY_FOR_CONTROLLED_EXPERIMENT = "ready_for_controlled_experiment"
    SYNTHETIC_EVALUATION_ONLY = "synthetic_evaluation_only"
    BLOCKED = "blocked"


class StrEnumDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


class PaperMethodCard(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paper_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    stable_identifier: str = Field(min_length=1)
    evidence_state: EvidenceState
    license: str = Field(min_length=1)
    method_name: str = Field(min_length=1)
    original_problem: str = Field(min_length=1)
    method_summary: str = Field(min_length=1)
    reusable_component: str = Field(min_length=1)
    input_semantics: str = Field(min_length=1)
    output_semantics: str = Field(min_length=1)
    compute_cost: str = Field(min_length=1)
    limitations: tuple[str, ...] = ()
    content_hash: str | None = None
    repository_ref: str | None = None


class BaselineReproduction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    baseline_paper_id: str = Field(min_length=1)
    implementation_ref: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    dataset: str = Field(min_length=1)
    split: str = Field(min_length=1)
    seed_policy: str = Field(min_length=1)
    reproduced: bool
    reproduced_metrics: dict[str, float] = Field(default_factory=dict)
    acceptance_tolerance: str = Field(min_length=1)
    notes: tuple[str, ...] = ()
    version_or_commit: str | None = None
    compute_fit: bool | None = None
    baseline_parity_verified: bool | None = None
    dataset_fingerprint: str | None = None
    environment_fingerprint: str | None = None

    @model_validator(mode="after")
    def require_finite_reproduced_metrics(self) -> BaselineReproduction:
        for name, value in self.reproduced_metrics.items():
            if not name.strip():
                raise ValueError("reproduced metric names must be non-empty")
            if not math.isfinite(value):
                raise ValueError(f"reproduced metric {name!r} must be finite")
        return self


class ModuleIntent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_paper_id: str = Field(min_length=1)
    insertion_point: str = Field(min_length=1)
    proposed_role: str = Field(min_length=1)
    host_input_semantics: str = Field(min_length=1)
    host_output_semantics: str = Field(min_length=1)
    semantic_mapping: str = Field(min_length=1)
    adapter: str = Field(min_length=1)
    predicted_effect: str = Field(min_length=1)
    failure_mode: str = Field(min_length=1)
    input_shape: str | None = None
    output_shape: str | None = None
    normalization: str | None = None
    masks: str | None = None
    ordering: str | None = None
    trainable: bool | None = None
    loss_terms: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    implementation_switch: str | None = None
    gradient_expectation: str | None = None
    parameter_update_scope: str | None = None
    loss_scale: str | None = None
    baseline_parity_behavior: str | None = None


class StrongComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    source_paper_id: str = Field(min_length=1)
    comparator: str = Field(min_length=1)
    contrast: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    included_modules: tuple[str, ...] = ()


class ExpectedMetricTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(min_length=1)
    baseline_value: float = Field(allow_inf_nan=False)
    direction: StrEnumDirection
    target_value: float = Field(allow_inf_nan=False)
    guardrail: str = Field(min_length=1)


class TailoringTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    idea_id: str = Field(min_length=1)
    target_problem: str = Field(min_length=1)
    scientific_setting: str = Field(min_length=1)
    intended_claim: str = Field(min_length=1)
    observed_failure: str = Field(min_length=1)
    mechanism_hypothesis: str = Field(min_length=1)
    novelty_thesis: str = Field(min_length=1)
    why_not_simple_splice: str = Field(min_length=1)
    constraints: tuple[str, ...] = ()
    papers: tuple[PaperMethodCard, ...]
    reproduction: BaselineReproduction
    module_intents: tuple[ModuleIntent, ...]
    strong_comparisons: tuple[StrongComparison, ...] = ()
    expected_results: tuple[ExpectedMetricTarget, ...]
    preprocessing: str = Field(min_length=1)
    tuning_budget: str = Field(min_length=1)
    seeds: tuple[int, ...]
    uncertainty_reporting: str = Field(min_length=1)
    resource_measures: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    @model_validator(mode="after")
    def require_stable_unique_contracts(self) -> TailoringTask:
        if not self.papers:
            raise ValueError("at least one paper card is required")
        paper_ids = tuple(item.paper_id for item in self.papers)
        if len(set(paper_ids)) != len(paper_ids):
            raise ValueError("duplicate paper identifier")
        stable_identifiers = tuple(item.stable_identifier for item in self.papers)
        if len(set(stable_identifiers)) != len(stable_identifiers):
            raise ValueError("duplicate stable paper identifier")
        module_ids = tuple(item.source_paper_id for item in self.module_intents)
        if len(set(module_ids)) != len(module_ids):
            raise ValueError("duplicate module source paper")
        comparison_names = tuple(item.name for item in self.strong_comparisons)
        if len(set(comparison_names)) != len(comparison_names):
            raise ValueError("duplicate strong comparison name")
        known_papers = set(paper_ids)
        unknown_comparisons = {
            item.source_paper_id for item in self.strong_comparisons
        } - known_papers
        if unknown_comparisons:
            raise ValueError(
                f"strong comparisons reference unknown papers: {sorted(unknown_comparisons)}"
            )
        metric_names = tuple(item.metric for item in self.expected_results)
        if not metric_names:
            raise ValueError("at least one expected metric target is required")
        if len(set(metric_names)) != len(metric_names):
            raise ValueError("duplicate expected metric target")
        if not self.seeds or len(set(self.seeds)) != len(self.seeds):
            raise ValueError("seeds must be non-empty and unique")
        if not self.resource_measures or len(set(self.resource_measures)) != len(
            self.resource_measures
        ):
            raise ValueError("resource measures must be non-empty and unique")
        if not self.stop_conditions:
            raise ValueError("at least one stop condition is required")
        return self


class ProposalReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paper_id: str
    title: str
    stable_identifier: str
    evidence_state: EvidenceState
    license: str
    method_used: str
    borrowed_component: str
    use_in_proposal: str


class BaselineProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    paper_id: str
    method_name: str
    implementation_ref: str
    version_or_commit: str | None
    dataset: str
    split: str
    seed_policy: str
    environment: str
    reproduced: bool
    reproduced_metrics: dict[str, float]
    acceptance_tolerance: str
    compute_fit: bool | None
    baseline_parity_verified: bool | None
    dataset_fingerprint: str | None
    environment_fingerprint: str | None
    decision: str


class ProposalModule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    module_id: str
    source_paper_id: str
    source_title: str
    method_used: str
    borrowed_component: str
    insertion_point: str
    proposed_role: str
    source_input_semantics: str
    source_output_semantics: str
    host_input_semantics: str
    host_output_semantics: str
    semantic_mapping: str
    adapter: str
    input_shape: str | None
    output_shape: str | None
    normalization: str | None
    masks: str | None
    ordering: str | None
    trainable: bool | None
    loss_terms: tuple[str, ...]
    assumptions: tuple[str, ...]
    implementation_switch: str | None
    gradient_expectation: str | None
    parameter_update_scope: str | None
    loss_scale: str | None
    baseline_parity_behavior: str | None
    compatibility_status: str
    compatibility_reason: str
    predicted_effect: str
    failure_mode: str


class InnovationPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contribution: str
    why_not_simple_splice: str
    falsifiable_test: str
    status: str = "proposed"


class AcademicStory(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    problem: str
    baseline_evidence: str
    gap: str
    mechanism: str
    intervention: str
    expected_observation: str
    implication: str


class ProposalExperiment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    arm_type: ExperimentArmType
    included_modules: tuple[str, ...]
    purpose: str
    dataset: str
    split: str
    preprocessing: str
    tuning_budget: str
    metrics: tuple[str, ...]
    seeds: tuple[int, ...]
    uncertainty_reporting: str
    resource_measures: tuple[str, ...]
    stopping_criteria: str
    comparator: str | None = None
    contrast: str | None = None
    source_evidence_id: str | None = None


class ProposalExpectedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    baseline_value: float = Field(allow_inf_nan=False)
    direction: StrEnumDirection
    target_value: float = Field(allow_inf_nan=False)
    guardrail: str
    status: ResultStatus = ResultStatus.PROPOSED
    evidence_id: str | None = None


class TailoredResearchProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    idea_id: str
    decision: TailoringDecision
    strongest_reason: str
    baseline: BaselineProposal
    references: tuple[ProposalReference, ...]
    modules: tuple[ProposalModule, ...]
    innovation_points: tuple[InnovationPoint, ...]
    academic_story: AcademicStory
    experiment_matrix: tuple[ProposalExperiment, ...]
    expected_results: tuple[ProposalExpectedResult, ...]
    risks: tuple[str, ...]
    blockers: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_scope: EvidenceScope
    readiness: ProposalReadiness
    scientific_release_ready: bool
    release_conditions: tuple[str, ...]
    contract_version: str
    audit_policy_version: str
    proposal_policy_version: str
    plan_fingerprint: str
    proposal_fingerprint: str
    audit_verdict: AuditVerdict
    audit_reasons: tuple[str, ...]
    failed_audit_checks: tuple[str, ...]


def _license_is_acceptable(value: str) -> bool:
    return value.strip().lower() not in {
        "unknown",
        "missing",
        "unverified",
        "incompatible",
        "proprietary-no-reuse",
    }


def _is_shape_only(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {
        "shape-only",
        "shape only",
        "same shape",
        "reshape",
        "projection only",
        "tensor",
    }


def _format_metric_summary(values: dict[str, float]) -> str:
    if not values:
        return "no reproduced metric was recorded"
    return ", ".join(f"{name}={value:g}" for name, value in sorted(values.items()))


def _normalized_words(value: str) -> str:
    return " ".join(re.sub(r"[^\w\u4e00-\u9fff]+", " ", value.lower()).split())


def _is_weak_novelty(value: str) -> bool:
    normalized = _normalized_words(value)
    composition_signals = (
        "combine",
        "combination",
        "add",
        "stack",
        "splice",
        "concatenate",
        "组合",
        "拼接",
        "堆叠",
        "结合",
    )
    component_signals = ("module", "component", "模块", "组件")
    mechanism_signals = (
        "because",
        "through",
        "condition",
        "trigger",
        "gating",
        "mechanism",
        "causal",
        "hypothesis",
        "uncertainty",
        "when",
        "if",
        "机制",
        "条件",
        "触发",
        "门控",
        "因果",
        "假设",
        "不确定性",
    )
    has_composition = any(signal in normalized for signal in composition_signals)
    has_component = any(signal in normalized for signal in component_signals)
    has_mechanism = any(signal in normalized for signal in mechanism_signals)
    return has_composition and has_component and not has_mechanism


def _evidence_scope(papers: tuple[PaperMethodCard, ...]) -> EvidenceScope:
    states = {paper.evidence_state for paper in papers}
    if states == {EvidenceState.VERIFIED}:
        return EvidenceScope.REAL_VERIFIED
    if states == {EvidenceState.SYNTHETIC_FIXTURE}:
        return EvidenceScope.SYNTHETIC_EVALUATION
    return EvidenceScope.MIXED_OR_UNVERIFIED


def _canonical_fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _module_contract_complete(intent: ModuleIntent) -> bool:
    values = (
        intent.input_shape,
        intent.output_shape,
        intent.normalization,
        intent.masks,
        intent.ordering,
        intent.implementation_switch,
        intent.gradient_expectation,
        intent.parameter_update_scope,
        intent.loss_scale,
        intent.baseline_parity_behavior,
    )
    return (
        all(value is not None and value.strip() for value in values)
        and intent.trainable is not None
        and (intent.trainable is False or bool(intent.loss_terms))
        and bool(intent.assumptions)
    )


def _common_experiment(task: TailoringTask) -> dict[str, object]:
    return {
        "dataset": task.reproduction.dataset,
        "split": task.reproduction.split,
        "preprocessing": task.preprocessing,
        "tuning_budget": task.tuning_budget,
        "metrics": tuple(item.metric for item in task.expected_results),
        "seeds": task.seeds,
        "uncertainty_reporting": task.uncertainty_reporting,
        "resource_measures": task.resource_measures,
        "stopping_criteria": "; ".join(task.stop_conditions),
    }


def _to_method_plan(
    task: TailoringTask,
    baseline_paper: PaperMethodCard,
    modules: tuple[ProposalModule, ...],
    experiments: tuple[ProposalExperiment, ...],
) -> MethodPlan:
    reproduced_metric = _format_metric_summary(task.reproduction.reproduced_metrics)
    evidence = tuple(
        EvidenceItem(
            evidence_id=paper.paper_id,
            source_type="paper",
            title=paper.title,
            stable_identifier=paper.stable_identifier,
            verified=paper.evidence_state is not EvidenceState.UNVERIFIED,
            supported_claims=(paper.method_summary, paper.reusable_component),
            limitations=paper.limitations,
            content_hash=paper.content_hash,
            license=paper.license,
            repository_ref=paper.repository_ref,
        )
        for paper in task.papers
    )
    return MethodPlan(
        research=ResearchContract(
            target_problem=task.target_problem,
            scientific_setting=task.scientific_setting,
            success_metric=", ".join(item.metric for item in task.expected_results),
            constraints=task.constraints,
            intended_claim=task.intended_claim,
            observed_problem=task.observed_failure,
            proposed_mechanism=task.mechanism_hypothesis,
        ),
        baseline=BaselineCard(
            name=baseline_paper.method_name,
            version_or_commit=task.reproduction.version_or_commit,
            source_evidence_id=baseline_paper.paper_id,
            license=baseline_paper.license,
            dataset=task.reproduction.dataset,
            split=task.reproduction.split,
            environment=task.reproduction.environment,
            seed_policy=task.reproduction.seed_policy,
            reproduced=task.reproduction.reproduced,
            reproduced_metric=reproduced_metric,
            compute_fit=task.reproduction.compute_fit,
            baseline_parity_verified=task.reproduction.baseline_parity_verified,
            dataset_fingerprint=task.reproduction.dataset_fingerprint,
            environment_fingerprint=task.reproduction.environment_fingerprint,
        ),
        hypothesis=FalsifiableHypothesis(
            condition=task.scientific_setting,
            limitation=task.observed_failure,
            mechanism=task.mechanism_hypothesis,
            intervention=task.novelty_thesis,
            predicted_metric_change="; ".join(
                f"{item.metric} {item.direction.value} toward {item.target_value:g}"
                for item in task.expected_results
            ),
            guardrail="; ".join(item.guardrail for item in task.expected_results),
        ),
        modules=tuple(
            ModuleCard(
                name=module.module_id,
                evidence_id=module.source_paper_id,
                license=next(
                    paper.license
                    for paper in task.papers
                    if paper.paper_id == module.source_paper_id
                ),
                original_role=module.borrowed_component,
                proposed_role=module.proposed_role,
                input_semantics=module.host_input_semantics,
                output_semantics=module.host_output_semantics,
                input_shape=module.input_shape,
                output_shape=module.output_shape,
                normalization=module.normalization,
                masks=module.masks,
                ordering=module.ordering,
                trainable=module.trainable,
                loss_terms=module.loss_terms,
                compute_cost=next(
                    paper.compute_cost
                    for paper in task.papers
                    if paper.paper_id == module.source_paper_id
                ),
                assumptions=module.assumptions,
                predicted_effect=module.predicted_effect,
                failure_mode=module.failure_mode,
                implementation_switch=module.implementation_switch,
                gradient_expectation=module.gradient_expectation,
                parameter_update_scope=module.parameter_update_scope,
                loss_scale=module.loss_scale,
                baseline_parity_behavior=module.baseline_parity_behavior,
            )
            for module in modules
        ),
        experiments=tuple(
            ExperimentCard(
                name=experiment.name,
                arm_type=experiment.arm_type,
                included_modules=experiment.included_modules,
                dataset=experiment.dataset,
                split=experiment.split,
                preprocessing=experiment.preprocessing,
                tuning_budget=experiment.tuning_budget,
                metrics=experiment.metrics,
                seeds=experiment.seeds,
                uncertainty_reporting=experiment.uncertainty_reporting,
                resource_measures=experiment.resource_measures,
                stopping_criteria=experiment.stopping_criteria,
                purpose=experiment.purpose,
                comparator=experiment.comparator,
                contrast=experiment.contrast,
                source_evidence_id=experiment.source_evidence_id,
            )
            for experiment in experiments
        ),
        evidence=evidence,
        stop_conditions=task.stop_conditions,
    )


def _decision_from_audit(
    blockers: list[str],
    risks: list[str],
    verdict: AuditVerdict,
) -> tuple[TailoringDecision, str]:
    if blockers or verdict is AuditVerdict.NO_GO:
        reason = blockers[0] if blockers else "canonical methodology audit returned NO_GO"
        return TailoringDecision.NO_GO, reason
    if risks or verdict is AuditVerdict.REVISE:
        reason = risks[0] if risks else "canonical methodology audit requires revision"
        return TailoringDecision.REVISE, reason
    return (
        TailoringDecision.GO,
        (
            "baseline, provenance, compatibility, hypothesis, comparisons, "
            "interaction analysis, and fair experiments passed the canonical audit"
        ),
    )


def compose_tailored_research_proposal(task: TailoringTask) -> TailoredResearchProposal:
    papers = {paper.paper_id: paper for paper in task.papers}
    blockers: list[str] = []
    risks: list[str] = []

    baseline_paper = papers.get(task.reproduction.baseline_paper_id)
    if baseline_paper is None:
        raise ValueError("baseline paper is not present in the evidence set")
    if baseline_paper.evidence_state is EvidenceState.UNVERIFIED:
        blockers.append("baseline source is unverified")
    if not _license_is_acceptable(baseline_paper.license):
        blockers.append("baseline license does not permit the proposed reuse")
    if not task.reproduction.reproduced or not task.reproduction.reproduced_metrics:
        blockers.append("baseline was not reproduced with a recorded metric")

    references_by_id: dict[str, ProposalReference] = {
        baseline_paper.paper_id: ProposalReference(
            paper_id=baseline_paper.paper_id,
            title=baseline_paper.title,
            stable_identifier=baseline_paper.stable_identifier,
            evidence_state=baseline_paper.evidence_state,
            license=baseline_paper.license,
            method_used=baseline_paper.method_name,
            borrowed_component=baseline_paper.reusable_component,
            use_in_proposal="frozen baseline to reproduce before any modification",
        )
    }
    modules: list[ProposalModule] = []
    for index, intent in enumerate(task.module_intents, start=1):
        source = papers.get(intent.source_paper_id)
        if source is None:
            blockers.append(f"module source {intent.source_paper_id} is missing")
            continue
        if source.evidence_state is EvidenceState.UNVERIFIED:
            blockers.append(f"module source {source.paper_id} is unverified")
        if not _license_is_acceptable(source.license):
            blockers.append(f"module source {source.paper_id} has an incompatible license")
        shape_only = _is_shape_only(intent.semantic_mapping) or _is_shape_only(intent.adapter)
        complete_contract = _module_contract_complete(intent)
        compatibility_status = "compatible" if not shape_only and complete_contract else "blocked"
        if shape_only:
            blockers.append(
                f"module {source.paper_id} is justified only by shape or an unexplained adapter"
            )
        elif not complete_contract:
            risks.append(
                f"module {source.paper_id} lacks a complete training, gradient, "
                "switch, or parity contract"
            )
        compatibility_reason = (
            (
                "semantic, shape, ordering, switch, gradient, update, loss-scale, "
                "and failure contracts are explicit"
            )
            if compatibility_status == "compatible"
            else "semantic or executable compatibility is incomplete"
        )
        module_id = f"module-{index}-{source.method_name.lower().replace(' ', '-')}"
        modules.append(
            ProposalModule(
                module_id=module_id,
                source_paper_id=source.paper_id,
                source_title=source.title,
                method_used=source.method_name,
                borrowed_component=source.reusable_component,
                insertion_point=intent.insertion_point,
                proposed_role=intent.proposed_role,
                source_input_semantics=source.input_semantics,
                source_output_semantics=source.output_semantics,
                host_input_semantics=intent.host_input_semantics,
                host_output_semantics=intent.host_output_semantics,
                semantic_mapping=intent.semantic_mapping,
                adapter=intent.adapter,
                input_shape=intent.input_shape,
                output_shape=intent.output_shape,
                normalization=intent.normalization,
                masks=intent.masks,
                ordering=intent.ordering,
                trainable=intent.trainable,
                loss_terms=intent.loss_terms,
                assumptions=intent.assumptions,
                implementation_switch=intent.implementation_switch,
                gradient_expectation=intent.gradient_expectation,
                parameter_update_scope=intent.parameter_update_scope,
                loss_scale=intent.loss_scale,
                baseline_parity_behavior=intent.baseline_parity_behavior,
                compatibility_status=compatibility_status,
                compatibility_reason=compatibility_reason,
                predicted_effect=intent.predicted_effect,
                failure_mode=intent.failure_mode,
            )
        )
        references_by_id[source.paper_id] = ProposalReference(
            paper_id=source.paper_id,
            title=source.title,
            stable_identifier=source.stable_identifier,
            evidence_state=source.evidence_state,
            license=source.license,
            method_used=source.method_name,
            borrowed_component=source.reusable_component,
            use_in_proposal=f"inserted at {intent.insertion_point} as {intent.proposed_role}",
        )

    if not modules:
        blockers.append("no attributed intervention module was selected")
    weak_novelty = _is_weak_novelty(task.novelty_thesis) or _is_weak_novelty(
        task.why_not_simple_splice
    )
    if weak_novelty:
        risks.append(
            "novelty is stated as module composition rather than a falsifiable "
            "problem-method-insight contribution"
        )

    common = _common_experiment(task)
    module_ids = tuple(module.module_id for module in modules)
    experiments: list[ProposalExperiment] = [
        ProposalExperiment(
            name="frozen-baseline",
            arm_type=ExperimentArmType.BASELINE,
            included_modules=(),
            purpose=(
                "reconfirm the reproduced baseline and modules-disabled parity "
                "under fixed evaluation code"
            ),
            **common,
        )
    ]
    for module in modules:
        experiments.append(
            ProposalExperiment(
                name=f"single-{module.module_id}",
                arm_type=ExperimentArmType.SINGLE_MODULE,
                included_modules=(module.module_id,),
                purpose=f"measure the isolated contribution of {module.method_used}",
                contrast=f"single {module.module_id} versus frozen baseline",
                **common,
            )
        )
    experiments.append(
        ProposalExperiment(
            name="full-method",
            arm_type=ExperimentArmType.FULL,
            included_modules=module_ids,
            purpose="test the complete mechanism while holding data and budget fixed",
            contrast="full method versus frozen baseline and strongest comparison",
            **common,
        )
    )
    if len(modules) > 1:
        for module in modules:
            experiments.append(
                ProposalExperiment(
                    name=f"without-{module.module_id}",
                    arm_type=ExperimentArmType.LEAVE_ONE_OUT,
                    included_modules=tuple(
                        candidate.module_id for candidate in modules if candidate != module
                    ),
                    purpose=f"test whether the story still holds without {module.method_used}",
                    contrast=f"full method versus method without {module.module_id}",
                    **common,
                )
            )
        experiments.append(
            ProposalExperiment(
                name="module-interaction",
                arm_type=ExperimentArmType.INTERACTION,
                included_modules=module_ids,
                purpose="estimate whether the combined effect exceeds isolated module effects",
                contrast="full - baseline versus the sum of single-module improvements",
                **common,
            )
        )

    for comparison in task.strong_comparisons:
        source = papers[comparison.source_paper_id]
        references_by_id[source.paper_id] = ProposalReference(
            paper_id=source.paper_id,
            title=source.title,
            stable_identifier=source.stable_identifier,
            evidence_state=source.evidence_state,
            license=source.license,
            method_used=source.method_name,
            borrowed_component=source.reusable_component,
            use_in_proposal=f"strong comparison: {comparison.comparator}",
        )
        experiments.append(
            ProposalExperiment(
                name=comparison.name,
                arm_type=ExperimentArmType.STRONG_COMPARISON,
                included_modules=comparison.included_modules,
                purpose=comparison.purpose,
                comparator=comparison.comparator,
                contrast=comparison.contrast,
                source_evidence_id=comparison.source_paper_id,
                **common,
            )
        )

    expected_results = tuple(
        ProposalExpectedResult(
            metric=item.metric,
            baseline_value=item.baseline_value,
            direction=item.direction,
            target_value=item.target_value,
            guardrail=item.guardrail,
        )
        for item in task.expected_results
    )
    expected_observation = "; ".join(
        (
            f"{item.metric} should {item.direction.value} from "
            f"{item.baseline_value:g} toward {item.target_value:g}"
        )
        for item in expected_results
    )
    method_names = ", ".join(module.method_used for module in modules) or "no module"
    innovation_points = (
        InnovationPoint(
            contribution=task.novelty_thesis,
            why_not_simple_splice=task.why_not_simple_splice,
            falsifiable_test=(
                "the contribution is unsupported if the full arm does not "
                "outperform the frozen baseline and strong comparison, or if "
                "single-module, leave-one-out, and interaction contrasts do not "
                "support the proposed mechanism"
            ),
        ),
    )
    metric_summary = _format_metric_summary(task.reproduction.reproduced_metrics)
    story = AcademicStory(
        problem=f"{task.target_problem}: {task.observed_failure}",
        baseline_evidence=(
            f"{baseline_paper.title} was reproduced as {metric_summary} within "
            f"{task.reproduction.acceptance_tolerance}"
        ),
        gap=(
            "the baseline does not explicitly address "
            f"{task.mechanism_hypothesis} under {task.scientific_setting}"
        ),
        mechanism=task.mechanism_hypothesis,
        intervention=f"compose {method_names} at explicit semantic and training boundaries",
        expected_observation=expected_observation,
        implication=task.intended_claim,
    )

    module_tuple = tuple(modules)
    experiment_tuple = tuple(experiments)
    plan = _to_method_plan(task, baseline_paper, module_tuple, experiment_tuple)
    audit = audit_method_plan(plan)
    decision, strongest_reason = _decision_from_audit(
        blockers,
        risks,
        audit.verdict,
    )

    limitations = tuple(
        limitation
        for reference in references_by_id.values()
        for limitation in papers[reference.paper_id].limitations
    )
    baseline_decision = (
        "reproduced, parity-checked, and frozen for proposal evaluation"
        if task.reproduction.reproduced
        and task.reproduction.reproduced_metrics
        and task.reproduction.baseline_parity_verified is True
        else "not ready for modification"
    )
    evidence_scope = _evidence_scope(task.papers)
    if decision is not TailoringDecision.GO:
        readiness = ProposalReadiness.BLOCKED
    elif evidence_scope is EvidenceScope.REAL_VERIFIED:
        readiness = ProposalReadiness.READY_FOR_CONTROLLED_EXPERIMENT
    else:
        readiness = ProposalReadiness.SYNTHETIC_EVALUATION_ONLY
    release_conditions: list[str] = []
    if decision is not TailoringDecision.GO:
        release_conditions.append("resolve all canonical audit failures and proposal risks")
    if evidence_scope is not EvidenceScope.REAL_VERIFIED:
        release_conditions.append(
            "replace synthetic or unverified source cards with verified real-world evidence"
        )
    release_conditions.extend(
        (
            (
                "run the fixed baseline, strong comparison, single-module, full, "
                "leave-one-out, interaction, and efficiency experiments"
            ),
            "attach immutable evidence to every result represented as observed",
            "complete domain-expert review before making scientific or novelty claims",
        )
    )
    proposal_fingerprint = _canonical_fingerprint(
        {
            "proposal_policy_version": PROPOSAL_POLICY_VERSION,
            "plan_fingerprint": audit.plan_fingerprint,
            "idea_id": task.idea_id,
            "decision": decision.value,
            "references": sorted(references_by_id),
            "modules": sorted(module.module_id for module in modules),
            "experiments": sorted(experiment.name for experiment in experiments),
            "failed_checks": list(audit.trace.failed_check_ids),
        }
    )
    return TailoredResearchProposal(
        idea_id=task.idea_id,
        decision=decision,
        strongest_reason=strongest_reason,
        baseline=BaselineProposal(
            paper_id=baseline_paper.paper_id,
            method_name=baseline_paper.method_name,
            implementation_ref=task.reproduction.implementation_ref,
            version_or_commit=task.reproduction.version_or_commit,
            dataset=task.reproduction.dataset,
            split=task.reproduction.split,
            seed_policy=task.reproduction.seed_policy,
            environment=task.reproduction.environment,
            reproduced=task.reproduction.reproduced,
            reproduced_metrics=task.reproduction.reproduced_metrics,
            acceptance_tolerance=task.reproduction.acceptance_tolerance,
            compute_fit=task.reproduction.compute_fit,
            baseline_parity_verified=task.reproduction.baseline_parity_verified,
            dataset_fingerprint=task.reproduction.dataset_fingerprint,
            environment_fingerprint=task.reproduction.environment_fingerprint,
            decision=baseline_decision,
        ),
        references=tuple(references_by_id.values()),
        modules=module_tuple,
        innovation_points=innovation_points,
        academic_story=story,
        experiment_matrix=experiment_tuple,
        expected_results=expected_results,
        risks=tuple(dict.fromkeys([*risks, *audit.risks])),
        blockers=tuple(dict.fromkeys(blockers)),
        stop_conditions=task.stop_conditions,
        limitations=limitations,
        evidence_scope=evidence_scope,
        readiness=readiness,
        scientific_release_ready=False,
        release_conditions=tuple(release_conditions),
        contract_version=METHOD_PLAN_CONTRACT_VERSION,
        audit_policy_version=METHOD_AUDIT_POLICY_VERSION,
        proposal_policy_version=PROPOSAL_POLICY_VERSION,
        plan_fingerprint=audit.plan_fingerprint,
        proposal_fingerprint=proposal_fingerprint,
        audit_verdict=audit.verdict,
        audit_reasons=audit.reasons,
        failed_audit_checks=audit.trace.failed_check_ids,
    )


__all__ = [
    "PROPOSAL_POLICY_VERSION",
    "AcademicStory",
    "BaselineProposal",
    "BaselineReproduction",
    "EvidenceScope",
    "EvidenceState",
    "ExpectedMetricTarget",
    "InnovationPoint",
    "ModuleIntent",
    "PaperMethodCard",
    "ProposalExpectedResult",
    "ProposalExperiment",
    "ProposalModule",
    "ProposalReadiness",
    "ProposalReference",
    "ResultStatus",
    "StrEnumDirection",
    "StrongComparison",
    "TailoredResearchProposal",
    "TailoringDecision",
    "TailoringTask",
    "compose_tailored_research_proposal",
]

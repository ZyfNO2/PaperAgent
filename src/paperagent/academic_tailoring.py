from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class ExpectedMetricTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str = Field(min_length=1)
    baseline_value: float
    direction: StrEnumDirection
    target_value: float
    guardrail: str = Field(min_length=1)


class StrEnumDirection(StrEnum):
    INCREASE = "increase"
    DECREASE = "decrease"
    HOLD = "hold"


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
    expected_results: tuple[ExpectedMetricTarget, ...]
    preprocessing: str = Field(min_length=1)
    tuning_budget: str = Field(min_length=1)
    seeds: tuple[int, ...]
    uncertainty_reporting: str = Field(min_length=1)
    resource_measures: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    @model_validator(mode="after")
    def require_unique_papers_and_modules(self) -> TailoringTask:
        paper_ids = tuple(item.paper_id for item in self.papers)
        if len(set(paper_ids)) != len(paper_ids):
            raise ValueError("duplicate paper identifier")
        module_ids = tuple(item.source_paper_id for item in self.module_intents)
        if len(set(module_ids)) != len(module_ids):
            raise ValueError("duplicate module source paper")
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
    dataset: str
    split: str
    seed_policy: str
    environment: str
    reproduced: bool
    reproduced_metrics: dict[str, float]
    acceptance_tolerance: str
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
    arm_type: str
    included_modules: tuple[str, ...]
    purpose: str
    dataset: str
    split: str
    preprocessing: str
    tuning_budget: str
    seeds: tuple[int, ...]
    uncertainty_reporting: str
    resource_measures: tuple[str, ...]


class ProposalExpectedResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    metric: str
    baseline_value: float
    direction: StrEnumDirection
    target_value: float
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

    references: list[ProposalReference] = [
        ProposalReference(
            paper_id=baseline_paper.paper_id,
            title=baseline_paper.title,
            stable_identifier=baseline_paper.stable_identifier,
            evidence_state=baseline_paper.evidence_state,
            license=baseline_paper.license,
            method_used=baseline_paper.method_name,
            borrowed_component=baseline_paper.reusable_component,
            use_in_proposal="frozen baseline to reproduce before any modification",
        )
    ]
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
        compatibility_status = "blocked" if shape_only else "compatible"
        if shape_only:
            blockers.append(
                f"module {source.paper_id} is justified only by shape or an unexplained adapter"
            )
        compatibility_reason = (
            "semantic mapping, insertion point, adapter, and failure mode are explicit"
            if not shape_only
            else "semantic compatibility is not demonstrated beyond shape conversion"
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
                compatibility_status=compatibility_status,
                compatibility_reason=compatibility_reason,
                predicted_effect=intent.predicted_effect,
                failure_mode=intent.failure_mode,
            )
        )
        references.append(
            ProposalReference(
                paper_id=source.paper_id,
                title=source.title,
                stable_identifier=source.stable_identifier,
                evidence_state=source.evidence_state,
                license=source.license,
                method_used=source.method_name,
                borrowed_component=source.reusable_component,
                use_in_proposal=(
                    f"inserted at {intent.insertion_point} as {intent.proposed_role}"
                ),
            )
        )

    if not modules:
        blockers.append("no attributed intervention module was selected")
    if not task.novelty_thesis.strip() or not task.why_not_simple_splice.strip():
        risks.append("the novelty claim is not separated from module composition")

    module_ids = tuple(module.module_id for module in modules)
    experiment_matrix: list[ProposalExperiment] = [
        ProposalExperiment(
            name="frozen-baseline",
            arm_type="baseline",
            included_modules=(),
            purpose="reconfirm the reproduced baseline under the fixed evaluation code",
            dataset=task.reproduction.dataset,
            split=task.reproduction.split,
            preprocessing=task.preprocessing,
            tuning_budget=task.tuning_budget,
            seeds=task.seeds,
            uncertainty_reporting=task.uncertainty_reporting,
            resource_measures=task.resource_measures,
        )
    ]
    for module in modules:
        experiment_matrix.append(
            ProposalExperiment(
                name=f"single-{module.module_id}",
                arm_type="single_module",
                included_modules=(module.module_id,),
                purpose=f"measure the isolated contribution of {module.method_used}",
                dataset=task.reproduction.dataset,
                split=task.reproduction.split,
                preprocessing=task.preprocessing,
                tuning_budget=task.tuning_budget,
                seeds=task.seeds,
                uncertainty_reporting=task.uncertainty_reporting,
                resource_measures=task.resource_measures,
            )
        )
    experiment_matrix.append(
        ProposalExperiment(
            name="full-method",
            arm_type="full",
            included_modules=module_ids,
            purpose="test the complete mechanism while holding data and budget fixed",
            dataset=task.reproduction.dataset,
            split=task.reproduction.split,
            preprocessing=task.preprocessing,
            tuning_budget=task.tuning_budget,
            seeds=task.seeds,
            uncertainty_reporting=task.uncertainty_reporting,
            resource_measures=task.resource_measures,
        )
    )
    if len(modules) > 1:
        for module in modules:
            experiment_matrix.append(
                ProposalExperiment(
                    name=f"without-{module.module_id}",
                    arm_type="leave_one_out",
                    included_modules=tuple(
                        candidate.module_id for candidate in modules if candidate != module
                    ),
                    purpose=f"test whether the story still holds without {module.method_used}",
                    dataset=task.reproduction.dataset,
                    split=task.reproduction.split,
                    preprocessing=task.preprocessing,
                    tuning_budget=task.tuning_budget,
                    seeds=task.seeds,
                    uncertainty_reporting=task.uncertainty_reporting,
                    resource_measures=task.resource_measures,
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
            f"{item.metric} should {item.direction.value} from {item.baseline_value:g} "
            f"toward {item.target_value:g}"
        )
        for item in expected_results
    )
    method_names = ", ".join(module.method_used for module in modules) or "no module"
    innovation_points = (
        InnovationPoint(
            contribution=task.novelty_thesis,
            why_not_simple_splice=task.why_not_simple_splice,
            falsifiable_test=(
                "the contribution is unsupported if the full arm does not outperform the frozen "
                "baseline and the required single-module or leave-one-out comparisons"
            ),
        ),
    )
    story = AcademicStory(
        problem=f"{task.target_problem}: {task.observed_failure}",
        baseline_evidence=(
            f"{baseline_paper.title} was reproduced as {_format_metric_summary(task.reproduction.reproduced_metrics)} "
            f"within {task.reproduction.acceptance_tolerance}"
        ),
        gap=(
            f"the baseline does not explicitly address {task.mechanism_hypothesis} under "
            f"{task.scientific_setting}"
        ),
        mechanism=task.mechanism_hypothesis,
        intervention=f"compose {method_names} at explicit semantic boundaries",
        expected_observation=expected_observation,
        implication=task.intended_claim,
    )

    if blockers:
        decision = TailoringDecision.NO_GO
        strongest_reason = blockers[0]
    elif risks:
        decision = TailoringDecision.REVISE
        strongest_reason = risks[0]
    else:
        decision = TailoringDecision.GO
        strongest_reason = "baseline, provenance, compatibility, novelty, and fair experiments are explicit"

    limitations = tuple(
        limitation
        for reference in references
        for paper in (papers[reference.paper_id],)
        for limitation in paper.limitations
    )
    baseline_decision = (
        "verified and frozen for modification"
        if task.reproduction.reproduced and task.reproduction.reproduced_metrics
        else "not ready for modification"
    )
    return TailoredResearchProposal(
        idea_id=task.idea_id,
        decision=decision,
        strongest_reason=strongest_reason,
        baseline=BaselineProposal(
            paper_id=baseline_paper.paper_id,
            method_name=baseline_paper.method_name,
            implementation_ref=task.reproduction.implementation_ref,
            dataset=task.reproduction.dataset,
            split=task.reproduction.split,
            seed_policy=task.reproduction.seed_policy,
            environment=task.reproduction.environment,
            reproduced=task.reproduction.reproduced,
            reproduced_metrics=task.reproduction.reproduced_metrics,
            acceptance_tolerance=task.reproduction.acceptance_tolerance,
            decision=baseline_decision,
        ),
        references=tuple(references),
        modules=tuple(modules),
        innovation_points=innovation_points,
        academic_story=story,
        experiment_matrix=tuple(experiment_matrix),
        expected_results=expected_results,
        risks=tuple(risks),
        blockers=tuple(blockers),
        stop_conditions=task.stop_conditions,
        limitations=limitations,
    )

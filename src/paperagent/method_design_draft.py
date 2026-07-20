from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from paperagent.academic_methodology import (
    BaselineCard,
    ExperimentArmType,
    ExperimentCard,
    FalsifiableHypothesis,
    MethodPlan,
    ModuleCard,
    ResearchContract,
)
from paperagent.academic_methodology import (
    EvidenceItem as MethodEvidenceItem,
)
from paperagent.schemas.base import FrozenModel
from paperagent.schemas.evidence import EvidenceItem
from paperagent.schemas.method import (
    AblationPlan,
    BaselineProposal,
    ExperimentPlan,
    IntegrationContract,
    MethodModule,
    MethodProposal,
)
from paperagent.scientific_readiness import derive_scientific_readiness
from paperagent.state import PaperAgentState


class MethodDesignDraft(FrozenModel):
    """Low-nesting LLM surface for method design.

    Provenance, experiment fairness, implementation switches, baseline parity,
    and duplicated legacy fields are created by the server after validation.
    """

    problem_method_insight: str = Field(min_length=10)
    proposed_method_summary: str = Field(min_length=10)
    condition: str = Field(min_length=5)
    limitation: str = Field(min_length=5)
    mechanism: str = Field(min_length=5)
    intervention: str = Field(min_length=5)
    predicted_metric_change: str = Field(min_length=5)
    guardrail: str = Field(min_length=5)
    module_name: str = Field(min_length=2, max_length=120)
    module_original_role: str = Field(min_length=3)
    module_proposed_role: str = Field(min_length=3)
    input_semantics: str = Field(min_length=5)
    output_semantics: str = Field(min_length=5)
    predicted_effect: str = Field(min_length=5)
    failure_mode: str = Field(min_length=5)
    compute_cost: str = Field(min_length=3)
    primary_metric: str = Field(min_length=2, max_length=80)
    resource_measures: list[str] = Field(min_length=1, max_length=8)
    stopping_criteria: str = Field(min_length=5)
    reported_dataset: str | None = None
    reported_comparator: str | None = None
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in output:
            output.append(value)
    return tuple(output)


def _dedupe_list(values: Iterable[str]) -> list[str]:
    return list(_dedupe(values))


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    return normalized[:48] or "candidate_module"


def _evidence_text(state: PaperAgentState) -> str:
    evidence = state.get("evidence")
    if evidence is None:
        return ""
    return "\n".join(f"{item.title}\n{item.summary}" for item in evidence.accepted_items())


def _grounded_optional(value: str | None, evidence_text: str) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized if normalized.casefold() in evidence_text.casefold() else None


def _grounded_evidence_id(value: str | None, accepted: tuple[EvidenceItem, ...]) -> str | None:
    if value is None:
        return None
    normalized = value.strip().casefold()
    if not normalized:
        return None
    for item in accepted:
        title = getattr(item, "title", "")
        summary = getattr(item, "summary", "")
        if normalized in f"{title}\n{summary}".casefold():
            return item.evidence_id
    return None


def _metadata_text(metadata: dict[str, str], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _is_review_evidence(title: str, summary: str) -> bool:
    text = f"{title} {summary}".casefold()
    return any(cue in text for cue in ("review", "survey", "taxonomy"))


def _hypothesis_sentence(draft: MethodDesignDraft) -> str:
    return (
        f"Under {draft.condition}, {draft.intervention} should "
        f"{draft.predicted_metric_change} because {draft.mechanism} addresses "
        f"{draft.limitation}, while {draft.guardrail}."
    )


def _canonical_evidence(state: PaperAgentState) -> tuple[MethodEvidenceItem, ...]:
    evidence = state.get("evidence")
    if evidence is None:
        return ()
    return tuple(
        MethodEvidenceItem(
            evidence_id=item.evidence_id,
            source_type=item.source_type,
            title=item.title,
            stable_identifier=item.stable_identifier,
            verified=True,
            supported_claims=(item.summary,),
            limitations=(),
            content_hash=item.content_hash,
            license=_metadata_text(item.metadata, "license"),
            repository_ref=_metadata_text(item.metadata, "repository_ref"),
        )
        for item in evidence.accepted_items()
    )


def _experiment(
    *,
    name: str,
    arm_type: ExperimentArmType,
    included_modules: tuple[str, ...],
    source_evidence_id: str,
    comparator: str,
    purpose: str,
    contrast: str,
    dataset: str,
    metrics: tuple[str, ...],
    resource_measures: tuple[str, ...],
    stopping_criteria: str,
) -> ExperimentCard:
    return ExperimentCard(
        name=name,
        arm_type=arm_type,
        included_modules=included_modules,
        source_evidence_id=source_evidence_id,
        comparator=comparator,
        dataset=dataset,
        split="freeze the official or documented train/validation/test split before the pilot",
        preprocessing=(
            "match input construction, preprocessing, normalization, post-processing, "
            "and inference precision across arms"
        ),
        tuning_budget=(
            "match epochs or steps, optimizer search space, input budget, early stopping, "
            "and total compute"
        ),
        metrics=metrics,
        seeds=(1, 2, 3),
        uncertainty_reporting="report mean, standard deviation, and confidence intervals",
        resource_measures=resource_measures,
        purpose=purpose,
        contrast=contrast,
        stopping_criteria=stopping_criteria,
    )


def build_method_proposal(
    state: PaperAgentState,
    draft: MethodDesignDraft,
) -> MethodProposal:
    request = state.get("request")
    plan = state.get("plan")
    evidence_bundle = state.get("evidence")
    if request is None or plan is None or evidence_bundle is None:
        raise ValueError("request, research plan, and evidence are required")

    explicit = derive_scientific_readiness(request.question)
    invalid_protocol = (
        draft.explicit_evaluation_protocol_invalid or explicit.explicit_evaluation_protocol_invalid
    )
    draft = draft.model_copy(
        update={
            "baseline_readiness_confirmed": (
                draft.baseline_readiness_confirmed or explicit.baseline_readiness_confirmed
            ),
            "evaluation_protocol_validated": (
                (draft.evaluation_protocol_validated or explicit.evaluation_protocol_validated)
                and not invalid_protocol
            ),
            "comparison_readiness_confirmed": (
                draft.comparison_readiness_confirmed or explicit.comparison_readiness_confirmed
            ),
            "module_validation_confirmed": (
                draft.module_validation_confirmed or explicit.module_validation_confirmed
            ),
            "failure_policy_confirmed": (
                draft.failure_policy_confirmed or explicit.failure_policy_confirmed
            ),
            "explicit_evaluation_protocol_invalid": invalid_protocol,
        }
    )

    accepted = tuple(evidence_bundle.accepted_items())
    if not accepted:
        raise ValueError("method canonicalization requires accepted methodology evidence")
    attributed = tuple(
        item for item in accepted if not _is_review_evidence(item.title, item.summary)
    )
    primary = attributed[0] if attributed else accepted[0]
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    grounded_comparator = _grounded_optional(draft.reported_comparator, evidence_text)
    comparator_evidence_id = _grounded_evidence_id(grounded_comparator, accepted)
    if draft.comparison_readiness_confirmed and (
        grounded_comparator is None or comparator_evidence_id is None
    ):
        for item in attributed:
            if item.evidence_id == primary.evidence_id:
                continue
            grounded_comparator = item.title
            comparator_evidence_id = item.evidence_id
            break

    readiness_confirmed = (
        draft.baseline_readiness_confirmed
        and draft.evaluation_protocol_validated
        and not draft.explicit_evaluation_protocol_invalid
    )
    dataset = grounded_dataset or (
        "user-declared frozen dataset; preserve the exact identifier and fingerprint"
        if readiness_confirmed
        else (
            "unresolved task-matched public dataset; select and freeze the dataset, split, "
            "and data fingerprint before the pilot"
        )
    )
    review_primary = _is_review_evidence(primary.title, primary.summary)
    baseline_name = (
        "unresolved task-matched baseline selected from accepted review evidence"
        if review_primary
        else primary.title
    )
    comparator = grounded_comparator if comparator_evidence_id is not None else None
    module_name = draft.module_name.strip()
    module_switch = f"enable_{_slug(module_name)}"
    plan_risks = tuple(plan.risks)

    contract = ResearchContract(
        target_problem=request.question,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=_dedupe((*request.required_constraints, *plan_risks)),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
        baseline_readiness_confirmed=draft.baseline_readiness_confirmed,
        evaluation_protocol_validated=draft.evaluation_protocol_validated,
        comparison_readiness_confirmed=draft.comparison_readiness_confirmed,
        module_validation_confirmed=draft.module_validation_confirmed,
        failure_policy_confirmed=draft.failure_policy_confirmed,
        explicit_evaluation_protocol_invalid=draft.explicit_evaluation_protocol_invalid,
    )
    baseline = BaselineCard(
        name=baseline_name,
        version_or_commit=(
            "user-declared frozen implementation; preserve the exact version or commit"
            if readiness_confirmed
            else (
                f"review source {primary.stable_identifier}; implementation baseline unresolved"
                if review_primary
                else (
                    f"published source {primary.stable_identifier}; "
                    "implementation commit unresolved"
                )
            )
        ),
        source_evidence_id=primary.evidence_id,
        license=_metadata_text(primary.metadata, "license"),
        dataset=dataset,
        split=(
            "user-declared frozen independent split; preserve the exact split manifest"
            if readiness_confirmed
            else "not yet frozen; preserve the documented benchmark split and record data hashes"
        ),
        environment=(
            "user-declared frozen execution environment; preserve the exact environment manifest"
            if readiness_confirmed
            else (
                "not yet frozen; record hardware, framework, precision, export path, "
                "and dependency lock"
            )
        ),
        seed_policy="three fixed seeds (1, 2, 3) for all pilot comparisons",
        reproduced=readiness_confirmed,
        reproduced_metric=(
            f"user-declared reproduced {draft.primary_metric}; preserve the exact numeric result"
            if readiness_confirmed
            else None
        ),
        compute_fit=True if readiness_confirmed else None,
        baseline_parity_verified=(readiness_confirmed and draft.module_validation_confirmed),
        dataset_fingerprint=(
            "user-declared frozen dataset fingerprint; preserve the exact digest"
            if readiness_confirmed
            else None
        ),
        environment_fingerprint=(
            "user-declared frozen environment fingerprint; preserve the exact digest"
            if readiness_confirmed
            else None
        ),
    )
    hypothesis = FalsifiableHypothesis(
        condition=draft.condition,
        limitation=draft.limitation,
        mechanism=draft.mechanism,
        intervention=draft.intervention,
        predicted_metric_change=draft.predicted_metric_change,
        guardrail=draft.guardrail,
    )
    module = ModuleCard(
        name=module_name,
        evidence_id=primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=_metadata_text(primary.metadata, "license"),
        input_semantics=draft.input_semantics,
        output_semantics=draft.output_semantics,
        input_shape=(
            "task-specific representation at the selected insertion point; exact dimensions "
            "are resolved after the baseline is frozen"
        ),
        output_shape="representation contract required by the downstream baseline stage",
        normalization="inherit and freeze the baseline normalization contract",
        masks=(
            "inherit baseline target and padding masks; introduce no new mask semantics initially"
        ),
        ordering="insert one independently switchable module at the selected representation stage",
        trainable=True,
        loss_terms=("inherit baseline task losses and weights for the first pilot",),
        gradient_expectation=(
            "verify non-zero finite gradients in the module and connected baseline path"
        ),
        parameter_update_scope=(
            "train the candidate module and matched baseline parameters under the same budget"
        ),
        loss_scale=(
            "keep baseline loss scaling unchanged unless a documented pilot failure requires repair"
        ),
        compute_cost=draft.compute_cost,
        assumptions=_dedupe(
            (*plan_risks, "the selected insertion point preserves representation semantics")
        ),
        predicted_effect=draft.predicted_effect,
        failure_mode=draft.failure_mode,
        implementation_switch=module_switch,
        baseline_parity_behavior=(
            "when disabled, the module contributes no parameters, operations, "
            "preprocessing, or loss terms"
        ),
    )
    metrics = _dedupe((draft.primary_metric, "latency"))
    resources = _dedupe((*draft.resource_measures, "parameters", "memory", "latency"))
    experiments = [
        _experiment(
            name="E0-frozen-baseline",
            arm_type=ExperimentArmType.BASELINE,
            included_modules=(),
            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="establish a reproducible task-matched baseline under frozen settings",
            contrast="baseline only",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
        _experiment(
            name="E1-single-module",
            arm_type=ExperimentArmType.SINGLE_MODULE,
            included_modules=(module_name,),
            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="isolate the causal contribution of the proposed module",
            contrast=f"{module_name} enabled versus the frozen baseline",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
        _experiment(
            name="E2-full-method",
            arm_type=ExperimentArmType.FULL,
            included_modules=(module_name,),
            source_evidence_id=primary.evidence_id,
            comparator=baseline_name,
            purpose="measure the complete minimal method under the same evaluation contract",
            contrast="full minimal method versus baseline",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
    ]
    if comparator is not None and comparator_evidence_id is not None:
        experiments.append(
            _experiment(
                name="E3-strong-comparison",
                arm_type=ExperimentArmType.STRONG_COMPARISON,
                included_modules=(),
                source_evidence_id=comparator_evidence_id,
                comparator=comparator,
                purpose="test whether the contribution survives a stronger matched comparator",
                contrast="full method versus the evidence-bound strong comparison",
                dataset=dataset,
                metrics=metrics,
                resource_measures=resources,
                stopping_criteria=draft.stopping_criteria,
            )
        )
    stop_conditions = _dedupe(
        (
            draft.stopping_criteria,
            "stop if the target gain disappears under matched data and tuning",
            "revise if latency, memory, or compute guardrails fail on the selected device",
            "do not claim novelty if a stronger comparison implements the same mechanism",
        )
    )
    methodology_plan = MethodPlan(
        research=contract,
        evidence=_canonical_evidence(state),
        baseline=baseline,
        hypothesis=hypothesis,
        modules=(module,),
        experiments=tuple(experiments),
        stop_conditions=stop_conditions,
    )
    risks = _dedupe_list(
        (
            *plan_risks,
            plan.clarification_question or "",
            "baseline reproduction and disabled-module parity are not yet verified",
            "implementation and evidence licenses must be resolved before code reuse",
        )
    )
    hypothesis_text = _hypothesis_sentence(draft)
    evidence_ids = [item.evidence_id for item in accepted]

    return MethodProposal(
        baseline=BaselineProposal(
            name=baseline_name,
            description=(
                "Accepted evidence constrains baseline selection; implementation version, "
                "reproduction, and deployment fit remain pilot gates."
            ),
        ),
        modules=[
            MethodModule(
                module_id=module_name,
                name=module_name,
                purpose=draft.module_proposed_role,
            )
        ],
        integration_contracts=[
            IntegrationContract(
                from_module="frozen_baseline_representation_stage",
                to_module=module_name,
                input=draft.input_semantics,
                output=draft.output_semantics,
            )
        ],
        problem_method_insight=draft.problem_method_insight,
        falsifiable_hypothesis=hypothesis_text,
        minimum_key_experiment=ExperimentPlan(
            name="matched frozen-baseline pilot",
            conditions=[
                "run the frozen baseline with the module disabled",
                f"run the same configuration with {module_switch}=true",
                "hold data, preprocessing, tuning budget, seeds, precision, and hardware fixed",
            ],
            metrics=list(metrics),
            baseline=baseline_name,
            success_threshold=draft.stopping_criteria,
        ),
        ablations=[
            AblationPlan(
                name="module-off parity",
                change=f"set {module_switch}=false",
                expected_observation="recover the unchanged frozen baseline path",
            ),
            AblationPlan(
                name="single-module causal test",
                change=f"enable only {module_name} under the matched budget",
                expected_observation=draft.predicted_effect,
            ),
        ],
        risks=risks,
        stop_conditions=list(stop_conditions),
        evidence_ids=evidence_ids,
        methodology_plan=methodology_plan,
    )


__all__ = ["MethodDesignDraft", "build_method_proposal"]

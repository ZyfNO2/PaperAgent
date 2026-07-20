from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import Field

from paperagent.academic_methodology import (
    BaselineSpec,
    ExperimentArm,
    ExperimentArmType,
    FalsifiableHypothesis,
    MethodPlan,
    ProposedModule,
    ResearchContract,
)
from paperagent.method_evidence import canonical_methodology_evidence
from paperagent.schemas.base import FrozenModel
from paperagent.schemas.method import MethodProposal, MethodVariables
from paperagent.state import PaperAgentState


class MethodDesignDraft(FrozenModel):
    """Low-nesting LLM surface for method design.

    Provenance, experiment fairness, implementation switches, baseline parity, and all duplicated
    legacy summary fields are created by the server after this draft validates.
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


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in output:
            output.append(value)
    return tuple(output)


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


def _hypothesis_sentence(draft: MethodDesignDraft) -> str:
    return (
        f"Under {draft.condition}, {draft.intervention} should {draft.predicted_metric_change} "
        f"because {draft.mechanism} addresses {draft.limitation}, while {draft.guardrail}."
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
) -> ExperimentArm:
    return ExperimentArm(
        name=name,
        arm_type=arm_type,
        included_modules=included_modules,
        source_evidence_id=source_evidence_id,
        comparator=comparator,
        dataset=dataset,
        split="freeze the official or documented train/validation/test split before the pilot",
        preprocessing=(
            "match image resolution, augmentation, normalization, tiling, post-processing, "
            "and inference precision across arms"
        ),
        tuning_budget=(
            "match epochs, optimizer search space, image size, early stopping, and total compute"
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
    if request is None or plan is None:
        raise ValueError("request and research plan are required for method canonicalization")

    evidence = canonical_methodology_evidence(state)
    accepted = tuple(item for item in evidence if item.verified and item.relevance_passed)
    if not accepted:
        raise ValueError("method canonicalization requires accepted methodology evidence")
    primary = accepted[0]
    evidence_text = _evidence_text(state)
    grounded_dataset = _grounded_optional(draft.reported_dataset, evidence_text)
    grounded_comparator = _grounded_optional(draft.reported_comparator, evidence_text)

    dataset = grounded_dataset or (
        "unresolved task-matched dataset; select and freeze a public UAV small-object benchmark "
        "before the pilot"
    )
    baseline_name = primary.title
    comparator = grounded_comparator or (
        "strong comparison selected from the accepted evidence set before the pilot"
    )
    module_name = draft.module_name.strip()
    module_switch = f"enable_{_slug(module_name)}"
    plan_risks = tuple(plan.risks)
    unresolved = _dedupe(
        (
            plan.clarification_question or "",
            *plan_risks,
            "exact baseline implementation version, dataset split, and deployment device remain unresolved",
        )
    )

    contract = ResearchContract(
        target_problem=request.question,
        scientific_setting=plan.scope,
        success_metric=draft.primary_metric,
        constraints=_dedupe((*request.required_constraints, *plan_risks)),
        intended_claim=draft.proposed_method_summary,
        observed_problem=draft.limitation,
        proposed_mechanism=draft.mechanism,
    )
    baseline = BaselineSpec(
        name=baseline_name,
        version_or_commit=f"published artifact {primary.stable_identifier}; implementation commit unresolved",
        source_evidence_id=primary.evidence_id,
        license=primary.license,
        repository_ref=primary.repository_ref,
        dataset=dataset,
        split="not yet frozen; preserve the documented benchmark split and record data hashes",
        environment=(
            "not yet frozen; record hardware, framework, precision, export path, and dependency lock"
        ),
        seed_policy="three fixed seeds (1, 2, 3) for all pilot comparisons",
        reproduced=False,
        reproduced_metric=None,
        disabled_module_parity_path=(
            f"set {module_switch}=false and execute the unchanged baseline graph and preprocessing"
        ),
        baseline_parity_verified=False,
        compute_fit=None,
        weight_fingerprint=None,
        config_fingerprint=None,
        dataset_fingerprint=None,
    )
    hypothesis = FalsifiableHypothesis(
        condition=draft.condition,
        limitation=draft.limitation,
        mechanism=draft.mechanism,
        intervention=draft.intervention,
        predicted_metric_change=draft.predicted_metric_change,
        guardrail=draft.guardrail,
    )
    module = ProposedModule(
        name=module_name,
        evidence_id=primary.evidence_id,
        original_role=draft.module_original_role,
        proposed_role=draft.module_proposed_role,
        license=primary.license,
        input_semantics=draft.input_semantics,
        output_semantics=draft.output_semantics,
        input_shape=(
            "shape-preserving detector feature map at the selected insertion point; exact channels "
            "are resolved after the baseline is frozen"
        ),
        output_shape="same spatial and channel contract required by the downstream baseline stage",
        normalization="inherit and freeze the baseline normalization contract",
        masks="inherit baseline target and padding masks; introduce no new mask semantics initially",
        ordering=(
            "insert one independently switchable module at the evidence-motivated feature stage"
        ),
        trainable=True,
        loss_terms=("inherit baseline detection losses and weights for the first pilot",),
        gradient_expectation=(
            "verify non-zero finite gradients in the module and connected detector path"
        ),
        parameter_update_scope=(
            "train the candidate module and matched baseline parameters under the same budget"
        ),
        loss_scale="keep baseline loss scaling unchanged unless a documented pilot failure requires repair",
        compute_cost=draft.compute_cost,
        assumptions=_dedupe((*plan_risks, "the selected insertion point preserves tensor semantics")),
        predicted_effect=draft.predicted_effect,
        failure_mode=draft.failure_mode,
        implementation_switch=module_switch,
        baseline_parity_behavior=(
            "when disabled, the module contributes no parameters, operations, preprocessing, or loss terms"
        ),
    )
    metrics = _dedupe((draft.primary_metric, "AP_small", "latency"))
    resources = _dedupe((*draft.resource_measures, "parameters", "memory", "latency"))
    experiments = (
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
        _experiment(
            name="E3-strong-comparison",
            arm_type=ExperimentArmType.STRONG_COMPARISON,
            included_modules=(),
            source_evidence_id=primary.evidence_id,
            comparator=comparator,
            purpose="test whether the proposed contribution survives a stronger matched comparator",
            contrast="full method versus accepted-evidence strong comparison",
            dataset=dataset,
            metrics=metrics,
            resource_measures=resources,
            stopping_criteria=draft.stopping_criteria,
        ),
    )
    methodology_plan = MethodPlan(
        research_contract=contract,
        evidence=evidence,
        baseline=baseline,
        hypothesis=hypothesis,
        modules=(module,),
        experiments=experiments,
        stop_conditions=_dedupe(
            (
                draft.stopping_criteria,
                "stop if the target gain disappears under matched data, preprocessing, and tuning",
                "revise if latency, memory, or compute guardrails fail on the selected device",
                "do not claim novelty if an accepted stronger comparison implements the same mechanism",
            )
        ),
        unresolved_questions=unresolved,
    )
    hypothesis_text = _hypothesis_sentence(draft)
    reproducibility_risks = _dedupe(
        (
            *plan_risks,
            "baseline reproduction and disabled-module parity have not yet been verified",
            "implementation and evidence licenses must be resolved before code reuse",
        )
    )
    return MethodProposal(
        problem_method_insight=draft.problem_method_insight,
        proposed_method_summary=draft.proposed_method_summary,
        falsifiable_hypothesis=hypothesis_text,
        variables=MethodVariables(
            independent=(module_switch,),
            dependent=metrics,
            controlled=(
                "dataset split",
                "preprocessing",
                "training and tuning budget",
                "random seeds",
                "inference precision and hardware",
            ),
        ),
        ablations=tuple(item.name for item in experiments),
        reproducibility_risks=reproducibility_risks,
        evidence_ids=tuple(item.evidence_id for item in accepted),
        methodology_plan=methodology_plan,
    )


__all__ = ["MethodDesignDraft", "build_method_proposal"]

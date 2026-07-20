from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from pydantic import Field

from paperagent.academic_methodology import ExperimentArmType
from paperagent.claw_academic_benchmark import (
    AcademicTailoringRunTrace,
    BaselineTrace,
    EvidenceReview,
    EvidenceRole,
    ExperimentArm,
    ExperimentTrace,
    FactPartitions,
    HypothesisTrace,
    ModuleTrace,
    ObservedDecision,
)
from paperagent.schemas.base import FrozenModel
from paperagent.state import PaperAgentState


class BenchmarkNormalizationContext(FrozenModel):
    """Gold-independent metadata needed to normalize one real PaperAgent run."""

    case_id: str = Field(min_length=1)
    resolved_unknowns: tuple[str, ...] = ()
    asked_user_to_design_method: bool = False
    full_text_evidence_ids: tuple[str, ...] = ()
    stronger_baselines_considered: bool | None = None
    negative_results_visible: bool | None = None


def _dedupe(values: Iterable[str | None]) -> tuple[str, ...]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:
        if raw is None:
            continue
        value = raw.strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return tuple(output)


def _fact_partitions(state: PaperAgentState) -> FactPartitions:
    synthesis = state.get("synthesis")
    report = state.get("report")
    method = state.get("method")
    plan = state.get("plan")
    request = state.get("request")
    contract = state.get("research_contract")
    outcome = state.get("final_outcome")

    verified = (
        _dedupe(item.text for item in synthesis.verified_findings) if synthesis is not None else ()
    )
    inferred = _dedupe(item.text for item in report.inferred_findings) if report is not None else ()
    proposed = _dedupe(
        (
            method.problem_method_insight if method is not None else None,
            method.falsifiable_hypothesis if method is not None else None,
            report.proposed_method if report is not None else None,
        )
    )
    if not verified and not inferred and not proposed:
        inferred = _dedupe(
            (
                plan.problem_statement if plan is not None else None,
                plan.scope if plan is not None else None,
            )
        )
    if not verified and not inferred and not proposed and request is not None:
        verified = _dedupe((f"User-declared research objective: {request.question}",))
    unknown = _dedupe(
        (
            *(plan.risks if plan is not None else []),
            plan.clarification_question if plan is not None else None,
            *(contract.assumptions if contract is not None else []),
            *(contract.unavailable_private_evidence if contract is not None else []),
            *(outcome.missing_gap_ids if outcome is not None else []),
        )
    )

    used = set(verified)
    inferred = tuple(item for item in inferred if item not in used)
    used.update(inferred)
    proposed = tuple(item for item in proposed if item not in used)
    used.update(proposed)
    unknown = tuple(item for item in unknown if item not in used)
    return FactPartitions(
        verified=verified,
        inferred=inferred,
        proposed=proposed,
        unknown=unknown,
    )


def _roles_from_text(value: str) -> tuple[EvidenceRole, ...]:
    text = value.casefold()
    roles: list[EvidenceRole] = []
    if any(token in text for token in ("baseline", "基线", "reproduction", "复现")):
        roles.append("baseline")
    if any(
        token in text
        for token in (
            "strong comparison",
            "strong comparative",
            "sota",
            "comparison",
            "强比较",
            "强对比",
            "对比方法",
        )
    ):
        roles.append("strong_comparison")
    if any(token in text for token in ("risk", "failure", "negative", "风险", "失败")):
        roles.append("risk")
    if any(
        token in text
        for token in (
            "parallel",
            "alternative",
            "module",
            "mechanism",
            "并行",
            "替代",
            "模块",
            "机制",
        )
    ):
        roles.append("parallel_method")
    if any(token in text for token in ("gap", "limitation", "problem", "缺口", "局限", "不足")):
        roles.append("gap")
    return tuple(dict.fromkeys(roles))


def _role_from_text(value: str) -> EvidenceRole:
    roles = _roles_from_text(value)
    return roles[0] if roles else "other"


def _gap_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
    plan = state.get("plan")
    if plan is None:
        return {}
    roles: dict[str, EvidenceRole] = {}
    queries_by_gap: dict[str, list[str]] = {}
    for query in plan.search_queries:
        queries_by_gap.setdefault(query.gap_id, []).append(query.query)
    for gap in plan.evidence_gaps:
        text = " ".join((gap.description, *queries_by_gap.get(gap.gap_id, [])))
        roles[gap.gap_id] = _role_from_text(text)
    return roles


def _retrieval_roles(
    state: PaperAgentState, gap_roles: dict[str, EvidenceRole]
) -> tuple[EvidenceRole, ...]:
    roles: list[EvidenceRole] = [role for role in gap_roles.values() if role != "other"]
    method = state.get("method")
    plan = state.get("plan")
    if plan is not None:
        queries_by_gap: dict[str, list[str]] = {}
        for query in plan.search_queries:
            queries_by_gap.setdefault(query.gap_id, []).append(query.query)
        for gap in plan.evidence_gaps:
            text = " ".join((gap.description, *queries_by_gap.get(gap.gap_id, [])))
            roles.extend(_roles_from_text(text))
    if method is not None:
        roles.append("baseline")
        if method.methodology_plan.modules:
            roles.append("parallel_method")
        if any(
            experiment.arm_type is ExperimentArmType.STRONG_COMPARISON
            for experiment in method.methodology_plan.experiments
        ):
            roles.append("strong_comparison")
    if plan is not None and plan.evidence_gaps:
        roles.append("gap")
    if plan is not None and plan.risks:
        roles.append("risk")
    return tuple(dict.fromkeys(roles))


def _method_evidence_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
    method = state.get("method")
    if method is None:
        return {}
    plan = method.methodology_plan
    roles: dict[str, EvidenceRole] = {}
    if plan.baseline.source_evidence_id:
        roles[plan.baseline.source_evidence_id] = "baseline"
    for module in plan.modules:
        if module.evidence_id:
            roles[module.evidence_id] = "parallel_method"
    for experiment in plan.experiments:
        if not experiment.source_evidence_id:
            continue
        if experiment.arm_type is ExperimentArmType.STRONG_COMPARISON:
            roles[experiment.source_evidence_id] = "strong_comparison"
        elif experiment.arm_type is ExperimentArmType.NEGATIVE_CONTROL:
            roles[experiment.source_evidence_id] = "risk"
    return roles


_SUPPLIED_REF = re.compile(
    r"^(?P<title>.+?) \[declared role: (?P<role>.+?)\]$",
    re.IGNORECASE,
)


def _supplied_material_reviews(
    state: PaperAgentState,
    *,
    existing_count: int,
) -> tuple[EvidenceReview, ...]:
    request = state.get("request")
    if request is None or existing_count >= len(request.user_material_refs):
        return ()
    reviews: list[EvidenceReview] = []
    for reference in request.user_material_refs[existing_count:]:
        match = _SUPPLIED_REF.match(reference.strip())
        declared_role = match.group("role").strip() if match else "other"
        digest = hashlib.sha256(reference.encode("utf-8")).hexdigest()[:16]
        role = _role_from_text(declared_role)
        reviews.append(
            EvidenceReview(
                evidence_id=f"user-material:{digest}",
                source_type="user_material",
                identity_verified=False,
                relevance_reviewed=False,
                relevance_passed=False,
                accepted=False,
                role=role,
                core_evidence=role in {"baseline", "gap", "parallel_method"},
                source_is_supplied_material=True,
                role_compatible=None,
            )
        )
    return tuple(reviews)


def _evidence_reviews(
    state: PaperAgentState,
    context: BenchmarkNormalizationContext,
    gap_roles: dict[str, EvidenceRole],
) -> tuple[EvidenceReview, ...]:
    bundle = state.get("evidence")
    if bundle is None:
        return _supplied_material_reviews(state, existing_count=0)
    ledger = state.get("evidence_ledger")
    relevance_by_id = {item.evidence_id: item for item in state.get("relevance_assessments", [])}
    ledger_by_id = {item.evidence_id: item for item in ledger.entries} if ledger else {}
    method_roles = _method_evidence_roles(state)
    full_text_ids = set(context.full_text_evidence_ids)
    accepted_ids = set(ledger.accepted_ids if ledger is not None else bundle.accepted_ids)
    identity_ids = set(bundle.identity_verified_ids)

    reviews: list[EvidenceReview] = []
    for item in bundle.items:
        ledger_entry = ledger_by_id.get(item.evidence_id)
        accepted_supports = tuple(
            support
            for support in (ledger_entry.gap_supports if ledger_entry is not None else ())
            if support.decision == "accept"
        )
        gap_ids = _dedupe(support.gap_id for support in accepted_supports)
        role = method_roles.get(item.evidence_id)
        if role is None:
            role_candidates = [gap_roles.get(gap_id, "other") for gap_id in gap_ids]
            role = next((candidate for candidate in role_candidates if candidate != "other"), None)
        relevance = relevance_by_id.get(item.evidence_id)
        metadata_full_text = item.metadata.get("full_text_checked", "").casefold() in {
            "1",
            "true",
            "yes",
        }
        reviews.append(
            EvidenceReview(
                evidence_id=item.evidence_id,
                source_type=item.source_type,
                identity_verified=item.evidence_id in identity_ids,
                relevance_reviewed=relevance is not None,
                relevance_passed=relevance is not None and relevance.decision == "pass",
                accepted=item.evidence_id in accepted_ids,
                role=role,
                gap_ids=gap_ids,
                claim_ids=(
                    tuple(ledger_entry.supported_claims) if ledger_entry is not None else ()
                ),
                core_evidence=role in {"baseline", "gap", "parallel_method"},
                full_text_checked=item.evidence_id in full_text_ids or metadata_full_text,
                source_is_supplied_material=item.source_type == "user_material",
                role_compatible=None,
            )
        )
    supplied_count = sum(item.source_is_supplied_material for item in reviews)
    reviews.extend(_supplied_material_reviews(state, existing_count=supplied_count))
    return tuple(reviews)


def _baseline_trace(state: PaperAgentState) -> BaselineTrace | None:
    method = state.get("method")
    if method is None:
        return None
    plan = method.methodology_plan
    baseline = plan.baseline
    baseline_experiments = tuple(
        item for item in plan.experiments if item.arm_type is ExperimentArmType.BASELINE
    )
    metrics = _dedupe(metric for item in baseline_experiments for metric in item.metrics)
    ledger = state.get("evidence_ledger")
    accepted = set(ledger.accepted_ids) if ledger is not None else set()
    strong_comparisons = tuple(
        item.comparator
        for item in plan.experiments
        if item.arm_type is ExperimentArmType.STRONG_COMPARISON
        and item.source_evidence_id in accepted
        and item.comparator is not None
        and item.comparator.strip()
        and "unresolved" not in item.comparator.casefold()
    )
    disabled_switches = _dedupe(item.implementation_switch for item in plan.modules)
    parity_path = ", ".join(disabled_switches) if disabled_switches else None
    return BaselineTrace(
        name=baseline.name,
        source_evidence_id=baseline.source_evidence_id,
        version_or_commit=baseline.version_or_commit,
        dataset=baseline.dataset,
        split=baseline.split,
        metrics=metrics,
        environment=baseline.environment,
        seed_policy=baseline.seed_policy,
        compute_assumptions="; ".join(plan.research.constraints) or None,
        disabled_module_parity_path=parity_path,
        baseline_parity_verified=baseline.baseline_parity_verified,
        reproduced=baseline.reproduced,
        reproduced_metric=baseline.reproduced_metric,
        strong_comparisons=strong_comparisons,
    )


def _hypothesis_trace(state: PaperAgentState) -> HypothesisTrace | None:
    method = state.get("method")
    if method is None:
        return None
    hypothesis = method.methodology_plan.hypothesis
    return HypothesisTrace(
        condition=hypothesis.condition,
        limitation=hypothesis.limitation,
        mechanism=hypothesis.mechanism,
        intervention=hypothesis.intervention,
        target_metric=hypothesis.predicted_metric_change,
        guardrail=hypothesis.guardrail,
    )


def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
    method = state.get("method")
    if method is None:
        return ()
    output: list[ModuleTrace] = []
    for module in method.methodology_plan.modules:
        optimization = _dedupe(
            (
                module.gradient_expectation,
                module.parameter_update_scope,
                module.loss_scale,
                ", ".join(module.loss_terms) if module.loss_terms else None,
            )
        )
        role_compatible = bool(
            module.evidence_id
            and module.original_role
            and module.proposed_role
            and module.input_semantics
            and module.output_semantics
            and module.input_semantics.casefold() not in {"tensor", "shape-only", "unknown"}
            and module.output_semantics.casefold() not in {"tensor", "shape-only", "unknown"}
        )
        output.append(
            ModuleTrace(
                module_id=module.name,
                evidence_id=module.evidence_id,
                original_role=module.original_role,
                proposed_role=module.proposed_role,
                input_semantics=module.input_semantics,
                output_semantics=module.output_semantics,
                input_shape=module.input_shape,
                output_shape=module.output_shape,
                optimization_interaction="; ".join(optimization) or None,
                compute_cost=module.compute_cost,
                failure_mode=module.failure_mode,
                implementation_switch=module.implementation_switch,
                role_compatible=role_compatible,
            )
        )
    return tuple(output)


def _arm_type(value: ExperimentArmType) -> ExperimentArm:
    mapping: dict[ExperimentArmType, ExperimentArm] = {
        ExperimentArmType.BASELINE: "baseline",
        ExperimentArmType.FULL: "full",
        ExperimentArmType.SINGLE_MODULE: "single_module",
        ExperimentArmType.LEAVE_ONE_OUT: "interaction",
        ExperimentArmType.STRONG_COMPARISON: "strong_comparison",
        ExperimentArmType.INTERACTION: "interaction",
        ExperimentArmType.EFFICIENCY: "efficiency",
        ExperimentArmType.NEGATIVE_CONTROL: "negative_control",
        ExperimentArmType.OTHER: "feasibility",
    }
    return mapping[value]


def _experiments(state: PaperAgentState) -> tuple[ExperimentTrace, ...]:
    method = state.get("method")
    if method is None:
        return ()
    return tuple(
        ExperimentTrace(
            experiment_id=item.name,
            arm_type=_arm_type(item.arm_type),
            included_modules=item.included_modules,
            dataset=item.dataset,
            split=item.split,
            preprocessing=item.preprocessing,
            tuning_budget=item.tuning_budget,
            metrics=item.metrics,
            seeds=item.seeds,
            uncertainty_reporting=item.uncertainty_reporting,
            resource_measures=item.resource_measures,
            stopping_criteria=item.stopping_criteria,
        )
        for item in method.methodology_plan.experiments
    )


def _decision(state: PaperAgentState) -> tuple[ObservedDecision, bool, tuple[str, ...]]:
    outcome = state.get("final_outcome")
    if outcome is None or outcome.scientific_verdict == "NOT_EVALUATED":
        return "REVISE", False, ("NOT_EVALUATED",)
    return outcome.scientific_verdict, True, ()


def normalize_paperagent_state(
    state: PaperAgentState,
    context: BenchmarkNormalizationContext,
) -> AcademicTailoringRunTrace:
    """Normalize a real PaperAgent state without reading any gold-case fields."""

    plan = state.get("plan")
    request = state.get("request")
    method = state.get("method")
    outcome = state.get("final_outcome")
    report = state.get("report")
    gap_roles = _gap_roles(state)
    modules = _modules(state)
    experiments = _experiments(state)
    decision, evaluated, evaluation_errors = _decision(state)

    clarification_questions = _dedupe((plan.clarification_question if plan is not None else None,))
    next_actions = _dedupe(
        (
            *(outcome.recommended_next_actions if outcome is not None else []),
            *(report.next_actions if report is not None else []),
        )
    )
    if not next_actions:
        next_actions = ("capture missing evidence and rerun the bounded workflow",)
    pilot_recommended = bool(outcome is not None and outcome.pilot_recommended)
    ledger = state.get("evidence_ledger")
    accepted_ids = set(ledger.accepted_ids) if ledger is not None else set()
    strong_comparison_derived = any(
        item.arm_type == "strong_comparison"
        and item.experiment_id
        and method is not None
        and any(
            experiment.name == item.experiment_id
            and experiment.source_evidence_id in accepted_ids
            and experiment.comparator is not None
            and experiment.comparator.strip()
            and "unresolved" not in experiment.comparator.casefold()
            for experiment in method.methodology_plan.experiments
        )
        for item in experiments
    )
    negative_results_derived = bool(
        method is not None
        and any(
            experiment.arm_type is ExperimentArmType.NEGATIVE_CONTROL
            and experiment.source_evidence_id in accepted_ids
            for experiment in method.methodology_plan.experiments
        )
    )
    trace_audit = state.get("trace_audit")
    trace_audit_passed = trace_audit.passed if trace_audit is not None else evaluated
    trace_errors = _dedupe(
        (
            *evaluation_errors,
            *(trace_audit.error_codes if trace_audit is not None else []),
        )
    )
    inferred_unknowns = _dedupe(
        (
            request.clarification_answer if request is not None else None,
            *(context.resolved_unknowns),
        )
    )
    return AcademicTailoringRunTrace(
        case_id=context.case_id,
        fact_partitions=_fact_partitions(state),
        retrieval_roles=_retrieval_roles(state, gap_roles),
        evidence_reviews=_evidence_reviews(state, context, gap_roles),
        clarification_questions=clarification_questions,
        resolved_unknowns=inferred_unknowns,
        asked_user_to_design_method=context.asked_user_to_design_method,
        scientific_readiness=state.get("scientific_readiness"),
        baseline=_baseline_trace(state),
        hypothesis=_hypothesis_trace(state),
        modules=modules,
        module_design_deferred=method is None and decision in {"REVISE", "NO_GO"},
        module_defer_reason=(
            "; ".join(outcome.reason_codes)
            if method is None and outcome is not None and outcome.reason_codes
            else None
        ),
        stitch_order=tuple(item.module_id for item in modules),
        experiments=experiments,
        decision=decision,
        pilot_recommended=pilot_recommended,
        next_actions=next_actions,
        stop_conditions=(
            tuple(method.methodology_plan.stop_conditions) if method is not None else ()
        ),
        stronger_baselines_considered=(
            context.stronger_baselines_considered
            if context.stronger_baselines_considered is not None
            else strong_comparison_derived
        ),
        negative_results_visible=(
            context.negative_results_visible
            if context.negative_results_visible is not None
            else negative_results_derived
        ),
        trace_audit_passed=trace_audit_passed,
        trace_error_codes=trace_errors,
    )

from __future__ import annotations

from pathlib import Path

PATH = Path("src/paperagent/claw_benchmark_adapter.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from paperagent.academic_methodology import ExperimentArmType\n",
        """from paperagent.academic_methodology import ExperimentArmType
from paperagent.module_compatibility import (
    ModuleCompatibilityResult,
    evaluate_module_compatibility,
)
""",
        "benchmark adapter compatibility import",
    )

    roles = """def _method_evidence_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
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
"""
    helper = roles + """


def _module_compatibility_by_evidence(
    state: PaperAgentState,
) -> dict[str, ModuleCompatibilityResult]:
    method = state.get("method")
    evidence = state.get("evidence")
    if method is None or evidence is None:
        return {}
    plan = method.methodology_plan
    by_id = {item.evidence_id: item for item in evidence.items}
    request = state.get("request")
    target_text = " ".join(
        value
        for value in (
            request.question if request is not None else None,
            plan.research.target_problem,
            plan.research.scientific_setting,
            plan.research.intended_claim,
        )
        if value
    )
    return {
        module.evidence_id: evaluate_module_compatibility(
            module=module,
            evidence=by_id.get(module.evidence_id),
            accepted_ids=evidence.accepted_ids,
            baseline_evidence_id=plan.baseline.source_evidence_id,
            target_text=target_text,
        )
        for module in plan.modules
        if module.evidence_id
    }
"""
    text = replace_once(text, roles, helper, "benchmark adapter compatibility helper")

    start = text.index("def _evidence_reviews(")
    end = text.index("\ndef _baseline_trace(", start)
    evidence_reviews = text[start:end]
    evidence_reviews = replace_once(
        evidence_reviews,
        "    method_roles = _method_evidence_roles(state)\n    full_text_ids = set(context.full_text_evidence_ids)\n",
        """    method_roles = _method_evidence_roles(state)
    module_compatibility = _module_compatibility_by_evidence(state)
    full_text_ids = set(context.full_text_evidence_ids)
""",
        "benchmark evidence compatibility map",
    )
    evidence_reviews = replace_once(
        evidence_reviews,
        """                source_is_supplied_material=item.source_type == "user_material",
                role_compatible=None,
""",
        """                source_is_supplied_material=item.source_type == "user_material",
                role_compatible=(
                    module_compatibility[item.evidence_id].compatible
                    if role == "parallel_method" and item.evidence_id in module_compatibility
                    else None
                ),
""",
        "benchmark evidence role compatibility",
    )
    text = text[:start] + evidence_reviews + text[end:]

    old_modules = """def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
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
"""
    new_modules = """def _modules(state: PaperAgentState) -> tuple[ModuleTrace, ...]:
    method = state.get("method")
    if method is None:
        return ()
    compatibility_by_evidence = _module_compatibility_by_evidence(state)
    output: list[ModuleTrace] = []
    for module in method.methodology_plan.modules:
        optimization = _dedupe(
            (
                module.gradient_path or module.gradient_expectation,
                module.trainable_parameters,
                module.frozen_parameters,
                module.loss_weighting or module.loss_scale,
                ", ".join(module.loss_terms) if module.loss_terms else None,
            )
        )
        compatibility = compatibility_by_evidence.get(module.evidence_id or "")
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
                role_compatible=(compatibility.compatible if compatibility is not None else False),
                compatibility_reasons=(
                    compatibility.reasons
                    if compatibility is not None
                    else ("module_evidence_missing",)
                ),
            )
        )
    return tuple(output)
"""
    text = replace_once(text, old_modules, new_modules, "benchmark module trace adapter")
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

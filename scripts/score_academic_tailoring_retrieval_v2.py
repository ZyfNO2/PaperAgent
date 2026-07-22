from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace

_LEGACY_PATH = Path(__file__).with_name("score_academic_tailoring_retrieval_v1.py")
_SPEC = importlib.util.spec_from_file_location("paperagent_retrieval_scorer_v1", _LEGACY_PATH)
if _SPEC is None or _SPEC.loader is None:  # pragma: no cover - import machinery guard
    raise RuntimeError(f"cannot load legacy scorer from {_LEGACY_PATH}")
legacy = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(legacy)
_LEGACY_SCORE_CASE = legacy._score_case

_MODULE_ROLE_CUES = (
    "module",
    "parallel",
    "adaptation",
    "imputation",
    "attention",
    "fusion",
    "augmentation",
    "mechanism",
    "few-shot",
    "representation",
    "adapter",
)
_REVIEW_CUES = (
    "review",
    "survey",
    "methods and metrics",
    "overview",
    "systematic literature",
)
_GENERIC_PROTOCOL_CUES = (
    "unresolved",
    "not yet",
    "unknown",
    "select and freeze",
    "preserve the documented",
    "freeze the official or documented",
    "match input construction",
    "match epochs or steps",
    "same as baseline",
    "task-specific representation",
    "selected insertion point",
    "待确定",
    "未确定",
    "未知",
)
_GENERIC_CONTRACT_CUES = (
    "selected insertion point",
    "task-specific representation",
    "verify exact",
    "inherit baseline",
    "inherit and freeze",
    "match the source evidence",
    "preserve baseline semantics",
)


def _paper_role(asset: dict[str, Any]) -> str:
    role = str(asset.get("role", "")).casefold()
    if "baseline" in role:
        return "baseline"
    if "comparison" in role or "comparator" in role:
        return "strong_comparison"
    if any(cue in role for cue in _MODULE_ROLE_CUES):
        return "module"
    return "other"


def _review_like(item: dict[str, Any] | None) -> bool:
    if item is None:
        return False
    text = f"{item.get('title', '')}\n{item.get('summary', '')}".casefold()
    return any(cue in text for cue in _REVIEW_CUES)


def _specific_text(value: str | None, *, generic_cues: tuple[str, ...]) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    folded = value.casefold()
    return not any(cue in folded for cue in generic_cues)


def _module_contract_complete(module: Any) -> bool:
    values = (
        module.input_semantics,
        module.output_semantics,
        module.input_shape,
        module.output_shape,
        module.optimization_interaction,
        module.failure_mode,
        module.implementation_switch,
    )
    return all(_specific_text(value, generic_cues=_GENERIC_CONTRACT_CUES) for value in values)


def _protocol_specific(experiment: Any) -> bool:
    return all(
        _specific_text(value, generic_cues=_GENERIC_PROTOCOL_CUES)
        for value in (
            experiment.dataset,
            experiment.split,
            experiment.preprocessing,
            experiment.tuning_budget,
        )
    )


def _strict_baseline_identity_status(
    case: dict[str, Any],
    *,
    baseline_name: str | None,
    baseline_source_item: dict[str, Any] | None,
    baseline_targets: list[str],
    accepted_items: list[dict[str, Any]],
) -> str:
    status = legacy._baseline_identity_status(
        case,
        baseline_name=baseline_name,
        baseline_source_item=baseline_source_item,
        baseline_targets=baseline_targets,
        accepted_items=accepted_items,
    )
    if status != "evidence_bound_alternative":
        return status
    if baseline_source_item is None or _review_like(baseline_source_item):
        return "mismatch"
    metadata = baseline_source_item.get("metadata", {})
    relation = metadata.get("relation") if isinstance(metadata, dict) else None
    if relation not in {"direct_query", "baseline_role_query", "parallel_via_dataset"}:
        return "mismatch"
    if not legacy._has_author_linked_repository(baseline_source_item, accepted_items):
        return "mismatch"
    return status


def _role_bound_paper_matches(
    paper_assets: list[dict[str, Any]],
    *,
    accepted_papers: list[dict[str, Any]],
    baseline_source_item: dict[str, Any] | None,
    module_source_items: list[dict[str, Any]],
    comparison_source_items: list[dict[str, Any]],
) -> int:
    matched = 0
    for asset in paper_assets:
        role = _paper_role(asset)
        candidates = {
            "baseline": [baseline_source_item] if baseline_source_item is not None else [],
            "module": module_source_items,
            "strong_comparison": comparison_source_items,
            "other": accepted_papers,
        }[role]
        if any(legacy._asset_matches_item(asset, item) for item in candidates):
            matched += 1
    return matched


def _score_case(
    case: dict[str, Any],
    state: dict[str, Any] | None,
    trace: AcademicTailoringRunTrace | None,
    *,
    prompt_leakage: bool,
    minimum_score: int,
) -> dict[str, Any]:
    result = _LEGACY_SCORE_CASE(
        case,
        state,
        trace,
        prompt_leakage=prompt_leakage,
        minimum_score=minimum_score,
    )
    if state is None or trace is None:
        return result

    gold = case["gold"]
    expected_assets = [item for item in gold.get("expected_assets", []) if isinstance(item, dict)]
    paper_assets = [item for item in expected_assets if item.get("kind") == "paper"]

    accepted_items = legacy._accepted_verified_items(state, trace)
    accepted_items_by_id = {
        str(item["evidence_id"]): item for item in accepted_items if item.get("evidence_id")
    }
    accepted_papers = [item for item in accepted_items if item.get("source_type") == "paper"]
    accepted_review_by_id = {
        review.evidence_id: review
        for review in trace.evidence_reviews
        if review.accepted and review.identity_verified and review.relevance_passed
    }

    baseline = trace.baseline
    baseline_source_id = baseline.source_evidence_id if baseline is not None else None
    baseline_source_item = (
        accepted_items_by_id.get(baseline_source_id) if baseline_source_id else None
    )
    baseline_targets = legacy._baseline_target_titles(case)
    baseline_identity_status = _strict_baseline_identity_status(
        case,
        baseline_name=baseline.name if baseline is not None else None,
        baseline_source_item=baseline_source_item,
        baseline_targets=baseline_targets,
        accepted_items=accepted_items,
    )
    baseline_target_match = baseline_identity_status == "exact_target"
    baseline_identity_acceptable = baseline_identity_status in {
        "exact_target",
        "evidence_bound_alternative",
    }

    role_bound_modules = []
    for module in trace.modules:
        review = accepted_review_by_id.get(module.evidence_id)
        if (
            module.evidence_id
            and module.evidence_id != baseline_source_id
            and module.evidence_id in accepted_items_by_id
            and review is not None
            and review.role == "parallel_method"
        ):
            role_bound_modules.append(module)
    module_source_ids = {module.evidence_id for module in role_bound_modules}
    module_source_items = [
        accepted_items_by_id[evidence_id]
        for evidence_id in module_source_ids
        if evidence_id in accepted_items_by_id
    ]
    comparison_source_items = [
        accepted_items_by_id[evidence_id]
        for evidence_id, review in accepted_review_by_id.items()
        if review.role == "strong_comparison" and evidence_id in accepted_items_by_id
    ]
    matched_papers = _role_bound_paper_matches(
        paper_assets,
        accepted_papers=accepted_papers,
        baseline_source_item=baseline_source_item,
        module_source_items=module_source_items,
        comparison_source_items=comparison_source_items,
    )

    verified_contract_modules = []
    for module in role_bound_modules:
        review = accepted_review_by_id[module.evidence_id]
        if (
            _module_contract_complete(module)
            and review.role_compatible is True
            and module.role_compatible is not False
        ):
            verified_contract_modules.append(module)

    identity_score = 5 if accepted_papers else 0
    identity_score += round(10 * matched_papers / len(paper_assets)) if paper_assets else 10
    identity_score = min(15, identity_score)

    baseline_score = 0
    if baseline is not None and baseline_source_item is not None and baseline_identity_acceptable:
        baseline_score += 10 if baseline_target_match else 7
        baseline_score += 2 if baseline.source_evidence_id else 0
        baseline_score += 3 if baseline.version_or_commit else 0
    baseline_score = min(15, baseline_score)

    if trace.modules:
        module_role_count = sum(
            bool(module.original_role and module.proposed_role) for module in role_bound_modules
        )
        module_score = round(7 * len(role_bound_modules) / len(trace.modules))
        module_score += round(3 * module_role_count / len(trace.modules))
        compatibility_score = round(15 * len(verified_contract_modules) / len(trace.modules))
    elif trace.module_design_deferred and trace.module_defer_reason:
        module_score = 4
        compatibility_score = 3
    else:
        module_score = 0
        compatibility_score = 0
    module_score = min(10, module_score)
    compatibility_score = min(15, compatibility_score)

    hypothesis_score = 0
    if legacy._complete_hypothesis(trace) and baseline_identity_acceptable and role_bound_modules:
        hypothesis_score = 5

    arm_types = {item.arm_type for item in trace.experiments}
    experiment_score = 0
    if "baseline" in arm_types:
        experiment_score += 2
    if arm_types & {"full", "single_module", "interaction"} and role_bound_modules:
        experiment_score += 2
    if "strong_comparison" in arm_types:
        experiment_score += 1
    if any(item.metrics for item in trace.experiments):
        experiment_score += 1
    if any(len(item.seeds) >= 3 or item.uncertainty_reporting for item in trace.experiments):
        experiment_score += 1
    if trace.stop_conditions or any(item.stopping_criteria for item in trace.experiments):
        experiment_score += 1
    if trace.experiments and all(_protocol_specific(item) for item in trace.experiments):
        experiment_score += 2
    experiment_score = min(10, experiment_score)

    dimensions = dict(result["dimensions"])
    dimensions.update(
        {
            "paper_identity_and_citation_truth": identity_score,
            "baseline_selection": baseline_score,
            "module_provenance_and_role": module_score,
            "semantic_and_interface_compatibility": compatibility_score,
            "falsifiable_hypothesis": hypothesis_score,
            "experiment_and_ablation_design": experiment_score,
        }
    )

    hard_failures = set(result["hard_failures"])
    hard_failures.discard("unsupported_acceptance")
    if baseline_identity_status == "mismatch":
        hard_failures.add("wrong_paper_identity")
    if baseline is None and baseline_targets:
        hard_failures.add("missing_required_baseline")
    if baseline_source_id and any(
        module.evidence_id == baseline_source_id for module in trace.modules
    ):
        hard_failures.add("baseline_reused_as_module_evidence")
    if any(
        module.evidence_id in accepted_items_by_id
        and (
            accepted_review_by_id.get(module.evidence_id) is None
            or accepted_review_by_id[module.evidence_id].role != "parallel_method"
        )
        for module in trace.modules
    ):
        hard_failures.add("module_evidence_role_mismatch")
    if trace.modules and len(verified_contract_modules) != len(trace.modules):
        hard_failures.add("module_compatibility_not_independently_verified")
    if _review_like(baseline_source_item):
        hard_failures.add("review_used_as_executable_baseline")
    if trace.decision == "GO" and (
        hard_failures
        or not baseline_identity_acceptable
        or not role_bound_modules
        or len(verified_contract_modules) != len(trace.modules)
        or dimensions.get("dataset_truth_and_task_fit", 0) < 5
        or dimensions.get("repository_truth_and_relation", 0) < 3
        or experiment_score < 7
    ):
        hard_failures.add("unsupported_go_decision")

    score = sum(dimensions.values())
    result.update(
        {
            "score": score,
            "status": "passed" if score >= minimum_score and not hard_failures else "failed",
            "dimensions": dimensions,
            "matched_assets": {
                **result["matched_assets"],
                "papers": [matched_papers, len(paper_assets)],
            },
            "hard_failures": sorted(hard_failures),
            "scoring_policy": "role_bound_semantic_v2",
        }
    )
    audit = dict(result.get("scoring_audit", {}))
    audit.update(
        {
            "baseline_identity_status": baseline_identity_status,
            "baseline_target_match": baseline_target_match,
            "role_bound_paper_asset_matches": matched_papers,
            "role_bound_module_evidence_ids": sorted(module_source_ids),
            "verified_module_contract_count": len(verified_contract_modules),
            "task_specific_experiment_count": sum(
                _protocol_specific(item) for item in trace.experiments
            ),
        }
    )
    result["scoring_audit"] = audit
    return result


legacy._score_case = _score_case


def main() -> int:
    return legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())

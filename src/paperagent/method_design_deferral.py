from __future__ import annotations

SCIENTIFIC_METHOD_DEFERRAL_CODES = frozenset(
    {
        "insufficient_independent_evidence",
        "parallel_module_identity_missing",
        "semantic_incompatibility",
        "objective_incompatibility",
    }
)


def classify_method_design_deferral(message: str) -> str | None:
    """Map explicit method-contract deferrals to scientific rejection reasons."""

    normalized = " ".join(message.casefold().split())
    prefix = "module_design_deferred:"
    if not normalized.startswith(prefix):
        return None
    detail = normalized.removeprefix(prefix).strip()

    if "no independent accepted module evidence" in detail:
        return "insufficient_independent_evidence"

    identity_markers = (
        "module_evidence_missing",
        "module_evidence_not_accepted",
        "module_evidence_same_as_baseline",
        "module_relation_not_independent",
        "module_candidate_marker_missing",
        "module_evidence_is_review",
        "module_relevance_below_threshold",
        "module_identity_not_supported",
    )
    if any(marker in detail for marker in identity_markers):
        return "parallel_module_identity_missing"

    objective_markers = (
        "gradient_path_missing_or_generic",
        "trainable_parameters_missing_or_generic",
        "frozen_parameters_missing_or_generic",
        "loss_weighting_missing_or_generic",
        "loss_terms_missing_or_generic",
    )
    if any(marker in detail for marker in objective_markers):
        return "objective_incompatibility"

    semantic_markers = (
        "proposed_role_not_task_bound",
        "generic_insertion_point",
        "input_shape_missing_or_generic",
        "output_shape_missing_or_generic",
        "normalization_contract_missing_or_generic",
        "masking_contract_missing_or_generic",
        "shape_rank_not_explicit_or_projected",
    )
    if any(marker in detail for marker in semantic_markers):
        return "semantic_incompatibility"

    return "semantic_incompatibility"


__all__ = ["SCIENTIFIC_METHOD_DEFERRAL_CODES", "classify_method_design_deferral"]

from __future__ import annotations

import re
from collections.abc import Iterable

from paperagent.academic_methodology import ModuleCard
from paperagent.schemas import EvidenceItem
from paperagent.schemas.base import FrozenModel

MODULE_EVIDENCE_RELATIONS = frozenset(
    {
        "module_role_query",
        "parallel_method_query",
        "module_linked_by_focused_retrieval",
    }
)
_REVIEW_CUES = ("review", "survey", "taxonomy", "systematic review", "meta-analysis")
_GENERIC_CONTRACT_CUES = (
    "selected representation stage",
    "task-specific representation",
    "representation contract required",
    "inherit baseline",
    "inherit and freeze the baseline",
    "use the numeric normalization declared",
    "selected insertion point",
    "downstream baseline stage",
    "exact dimensions are resolved",
)
_GENERIC_TOKENS = frozenset(
    {
        "a",
        "an",
        "and",
        "at",
        "baseline",
        "candidate",
        "for",
        "from",
        "in",
        "method",
        "model",
        "module",
        "of",
        "paper",
        "proposed",
        "the",
        "to",
        "with",
    }
)


class ModuleCompatibilityResult(FrozenModel):
    compatible: bool
    reasons: tuple[str, ...] = ()


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", value.casefold()))


def _informative_tokens(value: str) -> set[str]:
    return {token for token in _tokens(value) if len(token) >= 3 and token not in _GENERIC_TOKENS}


def _specific(value: str | None) -> bool:
    if value is None or not value.strip():
        return False
    folded = value.casefold()
    return not any(cue in folded for cue in _GENERIC_CONTRACT_CUES)


def _metadata_float(item: EvidenceItem, key: str) -> float | None:
    raw = item.metadata.get(key)
    if raw is None or not raw.strip():
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _module_identity_supported(module: ModuleCard, evidence: EvidenceItem) -> bool:
    evidence_tokens = _informative_tokens(
        " ".join(
            (
                evidence.title,
                evidence.summary,
                evidence.metadata.get("module_aliases", ""),
                evidence.metadata.get("query_text", ""),
            )
        )
    )
    identity_tokens = _informative_tokens(f"{module.name} {module.original_role or ''}")
    if not identity_tokens:
        return False
    overlap = identity_tokens & evidence_tokens
    return bool(overlap) and (len(overlap) >= 2 or any(len(token) >= 4 for token in overlap))


def _task_role_supported(module: ModuleCard, target_text: str) -> bool:
    target_tokens = _informative_tokens(target_text)
    role_tokens = _informative_tokens(
        f"{module.proposed_role or ''} {module.input_semantics or ''} "
        f"{module.output_semantics or ''}"
    )
    return bool(target_tokens & role_tokens)


def _shape_rank(value: str | None) -> int | None:
    if value is None:
        return None
    match = re.search(r"\[([^\]]+)\]", value)
    if match is None:
        return None
    axes = [axis.strip() for axis in match.group(1).split(",") if axis.strip()]
    return len(axes) or None


def _shape_contract_supported(module: ModuleCard) -> bool:
    input_rank = _shape_rank(module.input_shape)
    output_rank = _shape_rank(module.output_shape)
    if input_rank is not None and output_rank is not None and input_rank == output_rank:
        return True
    shape_text = f"{module.input_shape or ''} {module.output_shape or ''}".casefold()
    return any(
        cue in shape_text
        for cue in ("projection", "project", "reshape", "pool", "upsample", "downsample")
    )


def evaluate_module_compatibility(
    *,
    module: ModuleCard,
    evidence: EvidenceItem | None,
    accepted_ids: Iterable[str],
    baseline_evidence_id: str | None,
    target_text: str,
) -> ModuleCompatibilityResult:
    reasons: list[str] = []
    accepted = set(accepted_ids)
    if evidence is None:
        reasons.append("module_evidence_missing")
    else:
        if evidence.evidence_id not in accepted:
            reasons.append("module_evidence_not_accepted")
        if baseline_evidence_id and evidence.evidence_id == baseline_evidence_id:
            reasons.append("module_evidence_reuses_baseline")
        relation = evidence.metadata.get("relation", "")
        if relation not in MODULE_EVIDENCE_RELATIONS:
            reasons.append("module_relation_not_independent")
        marker = evidence.metadata.get("module_candidate", "").casefold()
        if marker not in {"true", "1", "yes", "declared", "inferred"}:
            reasons.append("module_candidate_marker_missing")
        evidence_text = f"{evidence.title} {evidence.summary}".casefold()
        if any(cue in evidence_text for cue in _REVIEW_CUES):
            reasons.append("module_evidence_is_review")
        relevance = _metadata_float(evidence, "relevance_score")
        rank_score = _metadata_float(evidence, "rank_score")
        if relevance is None or relevance < 0.25 or rank_score is None or rank_score < 0.50:
            reasons.append("module_relevance_below_threshold")
        if not _module_identity_supported(module, evidence):
            reasons.append("module_identity_not_supported")

    if not _task_role_supported(module, target_text):
        reasons.append("proposed_role_not_task_bound")

    contract_fields = {
        "generic_insertion_point": module.insertion_point or module.ordering,
        "input_semantics_missing_or_generic": module.input_semantics,
        "output_semantics_missing_or_generic": module.output_semantics,
        "input_shape_missing_or_generic": module.input_shape,
        "output_shape_missing_or_generic": module.output_shape,
        "normalization_contract_missing_or_generic": (
            module.normalization_contract or module.normalization
        ),
        "masking_contract_missing_or_generic": module.masking_contract or module.masks,
        "gradient_path_missing_or_generic": module.gradient_path or module.gradient_expectation,
        "trainable_parameters_missing_or_generic": module.trainable_parameters,
        "frozen_parameters_missing_or_generic": module.frozen_parameters,
        "loss_weighting_missing_or_generic": module.loss_weighting or module.loss_scale,
    }
    for reason, value in contract_fields.items():
        if not _specific(value):
            reasons.append(reason)
    if not module.loss_terms or not all(_specific(term) for term in module.loss_terms):
        reasons.append("loss_terms_missing_or_generic")
    if not _shape_contract_supported(module):
        reasons.append("shape_rank_not_explicit_or_projected")

    deduped = tuple(dict.fromkeys(reasons))
    return ModuleCompatibilityResult(compatible=not deduped, reasons=deduped)


__all__ = [
    "MODULE_EVIDENCE_RELATIONS",
    "ModuleCompatibilityResult",
    "evaluate_module_compatibility",
]

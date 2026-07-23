from __future__ import annotations

import re
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from paperagent.academic_methodology import ModuleCard
from paperagent.schemas.evidence import EvidenceItem

_MODULE_RELATIONS = frozenset(
    {
        "module_role_query",
        "parallel_method_query",
        "module_linked_by_focused_retrieval",
    }
)
_GENERIC_TEMPLATES = (
    "selected representation stage",
    "task-specific representation",
    "representation contract required",
    "inherit baseline target and padding masks",
    "inherit and freeze the baseline normalization contract",
    "use the numeric normalization declared by the module source",
    "selected insertion point",
    "downstream baseline stage",
    "exact dimensions are resolved",
)


class ModuleCompatibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    compatible: bool
    reasons: tuple[str, ...]


def _score(item: EvidenceItem, key: str) -> float:
    try:
        return float(item.metadata.get(key, "0"))
    except (TypeError, ValueError):
        return 0.0


def _generic(value: str | None) -> bool:
    if not value or not value.strip():
        return True
    folded = value.casefold()
    return any(template in folded for template in _GENERIC_TEMPLATES)


def _identity_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _identity_supported(module: ModuleCard, evidence: EvidenceItem) -> bool:
    aliases = evidence.metadata.get("module_aliases", "")
    haystack = _identity_text(
        " ".join((evidence.title, evidence.summary, aliases, *evidence.metadata.values()))
    )
    identities = (_identity_text(module.name), _identity_text(module.original_role or ""))
    return any(value and value in haystack for value in identities)


def _shape_rank(value: str | None) -> int | None:
    if not value:
        return None
    bracketed = re.search(r"\[([^\]]+)\]|\(([^\)]+)\)", value)
    if bracketed:
        content = next(group for group in bracketed.groups() if group is not None)
        return len([part for part in content.split(",") if part.strip()])
    match = re.search(r"\b([1-9])\s*[- ]?(?:d|dimensional|rank)\b", value, re.I)
    return int(match.group(1)) if match else None


def evaluate_module_compatibility(
    module: ModuleCard,
    *,
    module_evidence: EvidenceItem | None,
    accepted_evidence_ids: Iterable[str],
    baseline_evidence_id: str | None,
    task: str,
) -> ModuleCompatibilityResult:
    reasons: list[str] = []
    accepted = set(accepted_evidence_ids)
    if module_evidence is None:
        reasons.append("module_evidence_missing")
    else:
        if module_evidence.evidence_id not in accepted:
            reasons.append("module_evidence_not_accepted")
        if module_evidence.evidence_id == baseline_evidence_id:
            reasons.append("module_evidence_same_as_baseline")
        if module_evidence.metadata.get("relation") not in _MODULE_RELATIONS:
            reasons.append("module_relation_not_independent")
        if not module_evidence.metadata.get("module_candidate"):
            reasons.append("module_candidate_marker_missing")
        text = f"{module_evidence.title} {module_evidence.summary}".casefold()
        if any(cue in text for cue in ("review", "survey", "taxonomy", "meta-analysis")):
            reasons.append("module_evidence_is_review")
        if (
            _score(module_evidence, "relevance_score") < 0.25
            or _score(module_evidence, "rank_score") < 0.50
        ):
            reasons.append("module_relevance_below_threshold")
        if not _identity_supported(module, module_evidence):
            reasons.append("module_identity_not_supported")

    task_context = task
    if module_evidence is not None:
        task_context = f"{task_context} {module_evidence.title} {module_evidence.summary}"
    task_tokens = set(re.findall(r"[a-z0-9\u4e00-\u9fff]+", task_context.casefold()))
    role_tokens = set(
        re.findall(r"[a-z0-9\u4e00-\u9fff]+", (module.proposed_role or "").casefold())
    )
    if not task_tokens.intersection(role_tokens):
        reasons.append("proposed_role_not_task_bound")

    fields = {
        "generic_insertion_point": module.insertion_point or module.ordering,
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
    reasons.extend(code for code, value in fields.items() if _generic(value))
    if not module.loss_terms or any(_generic(term) for term in module.loss_terms):
        reasons.append("loss_terms_missing_or_generic")

    input_rank = _shape_rank(module.input_shape)
    output_rank = _shape_rank(module.output_shape)
    shape_text = f"{module.input_shape or ''} {module.output_shape or ''}".casefold()
    projected = any(word in shape_text for word in ("projection", "reshape", "pooling"))
    if input_rank is None or output_rank is None or (input_rank != output_rank and not projected):
        reasons.append("shape_rank_not_explicit_or_projected")

    return ModuleCompatibilityResult(
        compatible=not reasons,
        reasons=tuple(dict.fromkeys(reasons)),
    )


__all__ = ["ModuleCompatibilityResult", "evaluate_module_compatibility"]

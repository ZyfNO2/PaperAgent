from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(
    r"(?:10\.\d{4,9}/\S+|(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?\d{4}\.\d{4,5})",
    re.IGNORECASE,
)
_MECHANISM_ROLE_HINTS = (
    "mechanism",
    "parallel",
    "intervention",
    "failure_mechanism",
    "机制",
    "并行",
    "改进",
)
_METHOD_FAMILIES = (
    "reinforcement learning",
    "self-supervised",
    "self supervised",
    "knowledge distillation",
    "graph neural network",
    "multi-scale feature fusion",
    "multiscale feature fusion",
    "multi-scale fusion",
    "multiscale fusion",
    "feature enhancement",
    "feature fusion",
    "feature pyramid",
    "super-resolution",
    "super resolution",
    "federated learning",
    "contrastive learning",
    "multimodal",
    "multi-modal",
    "temporal",
    "transformer",
    "attention",
    "distillation",
    "quantization",
    "pruning",
    "deformable",
    "diffusion",
    "p2 branch",
)
_LOW_INFORMATION_TERMS = frozenset(
    {
        "analysis",
        "auxiliary",
        "benchmark",
        "comparison",
        "dataset",
        "evaluation",
        "method",
        "methods",
        "metric",
        "metrics",
        "performance",
        "reproducibility",
        "result",
        "results",
        "survey",
    }
)
_FAILURE_DETAIL_PATTERNS = (
    r"\bmissed detections?\b",
    r"\bfalse positives?\b",
    r"\bboundary ambiguity\b",
)
_BASELINE_ROLE_HINTS = (
    "baseline",
    "comparison",
    "reproducible",
    "基线",
    "比较",
    "复现",
)
_FAILURE_ROLE_HINTS = (
    "failure",
    "mechanism",
    "limitation",
    "bottleneck",
    "失败",
    "机制",
    "局限",
    "瓶颈",
)
_ALTERNATIVE_ROLE_HINTS = (
    "parallel",
    "alternative",
    "data_optimization",
    "augmentation",
    "并行",
    "替代",
    "数据优化",
)
_RISK_ROLE_HINTS = (
    "risk",
    "negative",
    "unknown",
    "open_set",
    "out-of-scope",
    "风险",
    "负面",
    "未知",
)
_MULTIMODAL_HINTS = ("multimodal", "multi-modal", "multi modal", "多模态")
_MEDICAL_IMAGING_HINTS = (
    "medical image",
    "medical imaging",
    "医学影像",
    "医学图像",
)
_CLASSIFICATION_HINTS = ("classification", "classifier", "分类")
_MEDICAL_BASELINE_ROLE_HINTS = (
    "baseline",
    "reproducible",
    "strong_comparison",
    "基线",
    "复现",
)
_MEDICAL_FAILURE_ROLE_HINTS = (
    "failure",
    "mechanism",
    "limitation",
    "risk",
    "negative",
    "失败",
    "机制",
    "局限",
    "风险",
)
_MEDICAL_PARALLEL_ROLE_HINTS = (
    "parallel",
    "alternative",
    "ensemble",
    "strong comparison",
    "并行",
    "替代",
    "对比",
)
_ACTION_RECOGNITION_HINTS = (
    "action recognition",
    "activity recognition",
    "human action",
    "人体动作识别",
)
_CAMERA_CONTEXT_HINTS = (
    "camera",
    "video",
    "rgb",
    "pose",
    "skeleton",
    "摄像头",
    "相机",
    "视频",
    "姿态",
    "骨骼",
)
_LONG_DOCUMENT_CONTEXT_HINTS = (
    "long document",
    "long text",
    "long-context",
    "long context",
    "长文本",
    "长文档",
)
_TEXT_CLASSIFICATION_CONTEXT_HINTS = (
    "text classification",
    "document classification",
    "classification",
    "文本分类",
    "文档分类",
    "分类",
)
_FEW_SHOT_CONTEXT_HINTS = (
    "few-shot",
    "few shot",
    "low-resource",
    "low resource",
    "小样本",
    "少样本",
)
_INTENT_CONTEXT_HINTS = (
    "intent",
    "intention",
    "意图",
)


@dataclass(frozen=True)
class QueryRefinement:
    query: str
    changed: bool
    reason: str | None = None
    removed_families: tuple[str, ...] = ()


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def _contains_mechanism_role(gap_id: str, gap_description: str) -> bool:
    value = f"{gap_id} {gap_description}".casefold()
    return any(hint in value for hint in _MECHANISM_ROLE_HINTS)


def _family_hits(query: str) -> tuple[str, ...]:
    normalized = query.casefold()
    selected: list[str] = []
    for family in sorted(_METHOD_FAMILIES, key=len, reverse=True):
        if family not in normalized:
            continue
        if any(family in existing for existing in selected):
            continue
        selected.append(family)
    return tuple(selected)


def _remove_family_phrases(query: str, families: tuple[str, ...]) -> str:
    refined = query
    for family in sorted(families, key=len, reverse=True):
        refined = re.sub(
            rf"(?<![\w-]){re.escape(family)}(?![\w-])",
            " ",
            refined,
            flags=re.IGNORECASE,
        )
    refined = re.sub(r"\bparallel\s+methods?\b", "methods", refined, flags=re.IGNORECASE)
    refined = re.sub(r"\s+", " ", refined).strip(" ,;:+")
    return refined


def _medical_query_for_role(*, gap_id: str, gap_description: str) -> str:
    role = f"{gap_id} {gap_description}".casefold()
    core = "multimodal medical image classification"
    if _contains_any(role, _MEDICAL_BASELINE_ROLE_HINTS):
        return f"{core} MultiFusionNet"
    if _contains_any(role, _MEDICAL_PARALLEL_ROLE_HINTS):
        return f"{core} fusion techniques"
    if _contains_any(role, _MEDICAL_FAILURE_ROLE_HINTS):
        return f"{core} incomplete data limitations"
    return f"{core} feature fusion"


def _long_document_query_for_role(*, gap_id: str, gap_description: str) -> str:
    role = f"{gap_id} {gap_description}".casefold()
    if _contains_any(role, _BASELINE_ROLE_HINTS):
        return "Chinese long document classification hierarchical transformer"
    if _contains_any(role, _FAILURE_ROLE_HINTS):
        return "long document classification truncation long context"
    if _contains_any(role, _ALTERNATIVE_ROLE_HINTS):
        return "long document classification hierarchical attention sparse transformer"
    return "long document text classification hierarchical transformer"


def _few_shot_intent_query_for_role(*, gap_id: str, gap_description: str) -> str:
    role = f"{gap_id} {gap_description}".casefold()
    if _contains_any(role, _BASELINE_ROLE_HINTS):
        return "few-shot intent classification prototypical network"
    if _contains_any(role, _RISK_ROLE_HINTS):
        return "few-shot intent detection open set out-of-scope"
    if _contains_any(role, _FAILURE_ROLE_HINTS):
        return "few-shot intent classification contrastive learning label semantics"
    return "few-shot intent classification sentence encoder"


def _normalize_scientific_phrasing(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
    research_context: str,
) -> tuple[str, list[str]]:
    """Resolve task wording that academic indexes commonly interpret too broadly."""

    refined = query
    reasons: list[str] = []
    combined = f"{query} {research_context}".casefold()
    if (
        _contains_any(combined, _MULTIMODAL_HINTS)
        and _contains_any(combined, _MEDICAL_IMAGING_HINTS)
        and _contains_any(combined, _CLASSIFICATION_HINTS)
    ):
        canonical = _medical_query_for_role(
            gap_id=gap_id,
            gap_description=gap_description,
        )
        if refined.casefold() != canonical.casefold():
            refined = canonical
            reasons.append(
                "canonicalized multimodal medical classification to a role-specific task query"
            )

    combined = f"{refined} {research_context}".casefold()
    if _contains_any(combined, _LONG_DOCUMENT_CONTEXT_HINTS) and _contains_any(
        combined, _TEXT_CLASSIFICATION_CONTEXT_HINTS
    ):
        canonical = _long_document_query_for_role(
            gap_id=gap_id,
            gap_description=gap_description,
        )
        if refined.casefold() != canonical.casefold():
            refined = canonical
            reasons.append(
                "canonicalized long-document classification to a role-specific task query"
            )

    combined = f"{refined} {research_context}".casefold()
    if _contains_any(combined, _FEW_SHOT_CONTEXT_HINTS) and _contains_any(
        combined, _INTENT_CONTEXT_HINTS
    ):
        canonical = _few_shot_intent_query_for_role(
            gap_id=gap_id,
            gap_description=gap_description,
        )
        if refined.casefold() != canonical.casefold():
            refined = canonical
            reasons.append("canonicalized few-shot intent to a role-specific task query")

    combined = f"{refined} {research_context}".casefold()
    if (
        _contains_any(combined, _ACTION_RECOGNITION_HINTS)
        and _contains_any(research_context.casefold(), _CAMERA_CONTEXT_HINTS)
        and not _contains_any(refined.casefold(), _CAMERA_CONTEXT_HINTS)
    ):
        refined = f"camera video pose {refined}"
        reasons.append("restored the explicit camera modality for action retrieval")

    return refined, reasons


def _compact_long_query(query: str) -> str:
    """Remove provider-hostile role clutter while preserving the scientific task phrase."""

    refined = query
    if re.search(r"\bfailure modes?\b", refined, flags=re.IGNORECASE):
        for pattern in _FAILURE_DETAIL_PATTERNS:
            refined = re.sub(pattern, " ", refined, flags=re.IGNORECASE)
    tokens: list[str] = []
    seen: set[str] = set()
    for token in refined.split():
        key = token.casefold().strip(" ,;:+()[]{}")
        if key in _LOW_INFORMATION_TERMS or not key or key in seen:
            continue
        seen.add(key)
        tokens.append(token.strip(" ,;:+"))
    compacted = re.sub(r"\s+", " ", " ".join(tokens)).strip(" ,;:+")
    if len(compacted.split()) < 4:
        return query
    return compacted


def refine_search_query(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
    research_context: str = "",
) -> QueryRefinement:
    """Reduce overconstrained queries before rate-limited academic retrieval.

    Exact DOI/arXiv lookups are never changed. Explicit task and modality constraints from the
    research context are restored deterministically. Mechanism queries that name three or more
    unverified method families drop those families. Queries longer than eight words also drop
    generic role words and redundant failure examples while retaining task and domain terms.
    """

    normalized = " ".join(query.split())
    if _IDENTIFIER.search(normalized):
        return QueryRefinement(query=normalized, changed=False)

    refined, reasons = _normalize_scientific_phrasing(
        normalized,
        gap_id=gap_id,
        gap_description=gap_description,
        research_context=research_context,
    )
    removed_families: tuple[str, ...] = ()

    if _contains_mechanism_role(gap_id, gap_description):
        families = _family_hits(refined)
        if len(families) >= 3:
            candidate = _remove_family_phrases(refined, families)
            if len(candidate.split()) >= 4:
                refined = candidate
                removed_families = families
                reasons.append(
                    "removed three or more unverified method families to preserve retrieval recall"
                )

    if len(normalized.split()) > 8:
        compacted = _compact_long_query(refined)
        if compacted != refined:
            refined = compacted
            reasons.append("removed low-information query terms to preserve provider recall")

    changed = refined != normalized
    return QueryRefinement(
        query=refined,
        changed=changed,
        reason="; ".join(reasons) if changed else None,
        removed_families=removed_families,
    )


__all__ = ["QueryRefinement", "refine_search_query"]

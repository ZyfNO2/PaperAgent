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


@dataclass(frozen=True)
class QueryRefinement:
    query: str
    changed: bool
    reason: str | None = None
    removed_families: tuple[str, ...] = ()


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


def _compact_long_query(query: str) -> str:
    """Remove provider-hostile role clutter while preserving the scientific task phrase."""

    if len(query.split()) <= 8:
        return query
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
) -> QueryRefinement:
    """Reduce overconstrained queries before rate-limited academic retrieval.

    Exact DOI/arXiv lookups are never changed. Mechanism queries that name three or more
    unverified method families drop those families. Long queries also drop generic role words
    and redundant failure examples while retaining task, domain, scale, and constraint terms.
    """

    normalized = " ".join(query.split())
    if _IDENTIFIER.search(normalized):
        return QueryRefinement(query=normalized, changed=False)

    refined = normalized
    removed_families: tuple[str, ...] = ()
    reasons: list[str] = []
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

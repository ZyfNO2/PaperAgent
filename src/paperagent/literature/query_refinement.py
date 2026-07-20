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
    return tuple(family for family in _METHOD_FAMILIES if family in normalized)


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


def refine_search_query(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
) -> QueryRefinement:
    """Reduce technique-family conjunctions before rate-limited retrieval.

    A mechanism query may name one or two plausible families. Three or more families usually
    encode an unverified method stack and sharply reduce recall, so the families are removed while
    the task, scene, and failure-mode terms are preserved. Exact DOI/arXiv lookups are never changed.
    """

    normalized = " ".join(query.split())
    if _IDENTIFIER.search(normalized):
        return QueryRefinement(query=normalized, changed=False)
    if not _contains_mechanism_role(gap_id, gap_description):
        return QueryRefinement(query=normalized, changed=False)

    families = _family_hits(normalized)
    if len(families) < 3:
        return QueryRefinement(query=normalized, changed=False)

    refined = _remove_family_phrases(normalized, families)
    if len(refined.split()) < 4:
        return QueryRefinement(query=normalized, changed=False)
    return QueryRefinement(
        query=refined,
        changed=refined != normalized,
        reason="removed three or more unverified method families to preserve retrieval recall",
        removed_families=families,
    )


__all__ = ["QueryRefinement", "refine_search_query"]

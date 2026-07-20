from __future__ import annotations

import re
from dataclasses import dataclass

_IDENTIFIER = re.compile(
    r"(?:10\.\d{4,9}/\S+|(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?\d{4}\.\d{4,5})",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"\S+")
_LOW_INFORMATION_TERMS = frozenset(
    {
        "analysis",
        "benchmark",
        "comparison",
        "dataset",
        "datasets",
        "evaluation",
        "evidence",
        "literature",
        "method",
        "methods",
        "metric",
        "metrics",
        "paper",
        "papers",
        "performance",
        "research",
        "result",
        "results",
        "review",
        "study",
        "survey",
    }
)


@dataclass(frozen=True)
class QueryRefinement:
    query: str
    changed: bool
    reason: str | None = None
    removed_families: tuple[str, ...] = ()


def _clean_token(value: str) -> str:
    return value.casefold().strip(" ,;:+()[]{}")


def _compact_query(query: str) -> str:
    """Remove generic retrieval clutter while preserving user-supplied concepts.

    No model, dataset, domain, language, task, or evaluator-role ontology is used here.
    The operation is intentionally conservative: it only deduplicates tokens and removes
    generic research nouns from long queries.
    """

    output: list[str] = []
    seen: set[str] = set()
    for raw in _TOKEN.findall(query):
        key = _clean_token(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        if key in _LOW_INFORMATION_TERMS:
            continue
        output.append(raw.strip(" ,;:+"))
    compacted = re.sub(r"\s+", " ", " ".join(output)).strip(" ,;:+")
    return compacted if len(compacted.split()) >= 3 else query


def refine_search_query(
    query: str,
    *,
    gap_id: str,
    gap_description: str,
    research_context: str = "",
) -> QueryRefinement:
    """Apply domain-independent provider hygiene to a planned search query.

    Exact DOI/arXiv lookups are immutable. Other queries retain all domain-bearing terms,
    model names, task constraints, and modalities supplied by the planner. For long queries,
    only duplicate tokens and generic research nouns are removed. ``gap_id``,
    ``gap_description``, and ``research_context`` remain accepted for API compatibility but
    do not select benchmark-conditioned rewrites.
    """

    del gap_id, gap_description, research_context
    normalized = " ".join(query.split())
    if _IDENTIFIER.search(normalized):
        return QueryRefinement(query=normalized, changed=False)
    if len(normalized.split()) <= 8:
        return QueryRefinement(query=normalized, changed=False)

    refined = _compact_query(normalized)
    changed = refined != normalized
    return QueryRefinement(
        query=refined,
        changed=changed,
        reason=(
            "removed duplicate and generic research terms to preserve provider recall"
            if changed
            else None
        ),
    )


__all__ = ["QueryRefinement", "refine_search_query"]

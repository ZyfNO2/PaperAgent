from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from paperagent.literature.query_concepts import (
    required_candidate_term_groups as query_required_candidate_term_groups,
)
from paperagent.schemas import SearchQuery

PrecisionRisk = Literal["low", "medium", "high"]

_WORD = re.compile(r"[a-z0-9][a-z0-9+_.-]*", re.IGNORECASE)
_CJK = re.compile(r"[\u3400-\u9fff]")
_IDENTIFIER = re.compile(
    r"(?:10\.\d{4,9}/\S+|(?:arxiv:|arxiv\.org/(?:abs|pdf)/)?\d{4}\.\d{4,5})",
    re.IGNORECASE,
)
_ARXIV_IDENTIFIER = re.compile(
    r"(?:arxiv:|arxiv\.org/(?:abs|pdf)/)\s*\d{4}\.\d{4,5}",
    re.IGNORECASE,
)
_YEAR = re.compile(r"\b20(?:1\d|2\d)\b")
_RECENT_HINTS = frozenset(
    {
        "latest",
        "recent",
        "current",
        "state-of-the-art",
        "sota",
        "2024",
        "2025",
        "2026",
    }
)
_PREPRINT_HINTS = frozenset({"arxiv", "preprint", "preprints"})
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "based",
        "by",
        "for",
        "from",
        "in",
        "is",
        "model",
        "of",
        "on",
        "paper",
        "research",
        "study",
        "the",
        "to",
        "using",
        "with",
    }
)
_GENERIC_TERMS = frozenset(
    {
        "ai",
        "artificial",
        "deep",
        "learning",
        "machine",
        "method",
        "neural",
        "network",
        "survey",
        "review",
        "optimization",
        "improvement",
        "application",
    }
)


@dataclass(frozen=True)
class SearchSourcePolicy:
    approved: bool
    precision_risk: PrecisionRisk
    reasons: tuple[str, ...]
    informative_terms: tuple[str, ...]
    discriminative_terms: tuple[str, ...]
    required_candidate_term_groups: tuple[tuple[str, ...], ...]
    primary_provider: str
    escalation_providers: tuple[str, ...]
    allow_web_fallback: bool
    result_limit: int
    minimum_relevant_results: int
    minimum_relevance: float
    minimum_rank_score: float
    maximum_provider_calls: int


def _english_terms(query: str) -> tuple[str, ...]:
    return tuple(token.casefold() for token in _WORD.findall(query))


def _informative_terms(query: str) -> tuple[str, ...]:
    terms = _english_terms(query)
    informative = tuple(
        token
        for token in terms
        if token not in _STOPWORDS and len(token) > 1 and not token.isdigit()
    )
    if informative:
        return informative
    cjk = "".join(_CJK.findall(query))
    if len(cjk) >= 4:
        return tuple(cjk[index : index + 2] for index in range(0, len(cjk) - 1, 2))
    return ()


def required_candidate_term_groups(query: str) -> tuple[tuple[str, ...], ...]:
    """Derive candidate constraints only from the current query's task anchors."""

    return query_required_candidate_term_groups(query)


def review_search_query(query: SearchQuery) -> SearchSourcePolicy:
    normalized = " ".join(query.query.split())
    terms = _english_terms(normalized)
    informative = _informative_terms(normalized)
    unique_informative = tuple(dict.fromkeys(informative))
    discriminative = tuple(term for term in unique_informative if term not in _GENERIC_TERMS)
    identifier_query = bool(_IDENTIFIER.search(normalized))
    arxiv_requested = bool(
        _ARXIV_IDENTIFIER.search(normalized) or set(terms).intersection(_PREPRINT_HINTS)
    )
    cjk_count = len(_CJK.findall(normalized))
    generic_only = bool(unique_informative) and not discriminative
    reasons: list[str] = []

    if len(normalized) > 220:
        reasons.append("query is too long and likely mixes multiple retrieval intents")
    if not identifier_query and not unique_informative:
        reasons.append("query has no discriminative academic terms")
    if not identifier_query and len(unique_informative) < 2 and cjk_count < 8:
        reasons.append("query is too broad for rate-limited scholarly search")
    if not identifier_query and not discriminative and cjk_count < 8:
        reasons.append("query lacks a task-, domain-, dataset-, or mechanism-specific term")
    if generic_only:
        reasons.append("query contains only generic research vocabulary")

    approved = not reasons
    specificity = len(discriminative)
    if identifier_query or specificity >= 5 or cjk_count >= 14:
        risk: PrecisionRisk = "low"
    elif specificity >= 3 or cjk_count >= 10:
        risk = "medium"
    else:
        risk = "high"

    recent = bool(set(terms).intersection(_RECENT_HINTS) or _YEAR.search(normalized))
    escalation: tuple[str, ...]
    if arxiv_requested:
        primary = "arxiv"
        escalation = ("openalex", "semantic_scholar")
    else:
        primary = "openalex"
        escalation = ("semantic_scholar", "arxiv") if recent else ("semantic_scholar",)

    allow_web = approved and risk == "low" and "web" in query.source_types
    result_limit = 5 if risk == "low" else 6
    minimum_results = 1 if identifier_query else 2
    minimum_relevance = 0.34 if risk == "low" else 0.42
    minimum_rank_score = 0.62 if risk == "low" else 0.68

    return SearchSourcePolicy(
        approved=approved,
        precision_risk=risk,
        reasons=tuple(dict.fromkeys(reasons)),
        informative_terms=unique_informative,
        discriminative_terms=discriminative,
        required_candidate_term_groups=required_candidate_term_groups(normalized),
        primary_provider=primary,
        escalation_providers=escalation,
        allow_web_fallback=allow_web,
        result_limit=result_limit,
        minimum_relevant_results=minimum_results,
        minimum_relevance=minimum_relevance,
        minimum_rank_score=minimum_rank_score,
        maximum_provider_calls=4 if allow_web else 3,
    )


__all__ = ["SearchSourcePolicy", "required_candidate_term_groups", "review_search_query"]

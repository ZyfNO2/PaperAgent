from __future__ import annotations

import re

_QA_QUERY = re.compile(
    r"(?:\bquestion[- ]answering\b|\bprofessional\s+qa\b|\bdomain\s+qa\b|\bqa\s+system\b)",
    re.IGNORECASE,
)
_QA_CANDIDATE_TERMS = (
    "question answering",
    "question-answering",
    "qa system",
    "qa task",
    "qa benchmark",
    "grounded qa",
    "islamic qa",
    "medical qa",
    "legal qa",
    "domain-specific qa",
    "knowledge-intensive question",
)
_RELIABILITY_QUERY_TERMS = (
    "hallucination",
    "factuality",
    "faithfulness",
    "grounding",
    "verification",
    "uncertainty",
)
_RELIABILITY_CANDIDATE_TERMS = (
    "hallucination",
    "factuality",
    "factual error",
    "factual consistency",
    "faithfulness",
    "faithful answer",
    "grounded",
    "grounding",
    "unsupported claim",
    "uncertainty",
    "verification",
    "citation accuracy",
)


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def matches_specialized_candidate_terms(query: str, candidate_text: str) -> bool:
    """Enforce task pairs that generic token overlap cannot safely distinguish."""

    normalized_query = query.casefold()
    normalized_candidate = candidate_text.casefold()
    qa_match = not _QA_QUERY.search(normalized_query) or _contains_any(
        normalized_candidate, _QA_CANDIDATE_TERMS
    )
    reliability_match = not _contains_any(
        normalized_query, _RELIABILITY_QUERY_TERMS
    ) or _contains_any(normalized_candidate, _RELIABILITY_CANDIDATE_TERMS)
    return qa_match and reliability_match


__all__ = ["matches_specialized_candidate_terms"]

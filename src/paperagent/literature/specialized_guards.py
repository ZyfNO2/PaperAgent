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
_TIME_SERIES_ANOMALY_QUERY_TERMS = (
    "time series anomaly",
    "time-series anomaly",
    "anomaly transformer",
    "时间序列异常",
)
_TIME_SERIES_CANDIDATE_TERMS = (
    "time series",
    "time-series",
    "multivariate time series",
    "temporal sequence",
    "temporal data",
    "sensor series",
    "sensor data stream",
    "industrial time series",
)
_ANOMALY_CANDIDATE_TERMS = (
    "anomaly detection",
    "anomaly detector",
    "anomalous sequence",
    "anomalous point",
    "outlier detection",
)
_FEW_SHOT_QUERY_TERMS = (
    "few-shot",
    "few shot",
    "zero-shot",
    "zero shot",
    "small sample",
    "low-resource",
    "low resource",
    "meta-learning",
)
_FEW_SHOT_CANDIDATE_TERMS = (
    "few-shot",
    "few shot",
    "zero-shot",
    "zero shot",
    "small sample",
    "low-resource",
    "low resource",
    "few labeled",
    "few examples",
    "meta-learning",
    "transfer learning",
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

    time_series_query = _contains_any(normalized_query, _TIME_SERIES_ANOMALY_QUERY_TERMS)
    time_series_match = not time_series_query or (
        _contains_any(normalized_candidate, _TIME_SERIES_CANDIDATE_TERMS)
        and _contains_any(normalized_candidate, _ANOMALY_CANDIDATE_TERMS)
    )
    anomaly_transformer_match = "anomaly transformer" not in normalized_query or (
        "anomaly transformer" in normalized_candidate
    )
    few_shot_match = not (
        time_series_query and _contains_any(normalized_query, _FEW_SHOT_QUERY_TERMS)
    ) or _contains_any(normalized_candidate, _FEW_SHOT_CANDIDATE_TERMS)

    return (
        qa_match
        and reliability_match
        and time_series_match
        and anomaly_transformer_match
        and few_shot_match
    )


__all__ = ["matches_specialized_candidate_terms"]

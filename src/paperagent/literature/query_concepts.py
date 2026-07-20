from __future__ import annotations

_SMALL_OBJECT_QUERY_HINTS = (
    "small object",
    "small-object",
    "tiny object",
    "tiny-object",
    "small target",
    "tiny target",
    "ap_small",
)
_SMALL_OBJECT_CANDIDATE_TERMS = (
    "small object",
    "small-object",
    "tiny object",
    "tiny-object",
    "small target",
    "tiny target",
    "small oriented object",
    "small-scale object",
    "small-scale target",
    "tiny pixel-area",
)
_OBJECT_DETECTION_QUERY_HINTS = (
    "object detection",
    "object detector",
    "small object",
    "tiny object",
    "ap_small",
)
_OBJECT_DETECTION_CANDIDATE_TERMS = (
    "object detection",
    "object detector",
    "detect objects",
    "detecting objects",
    "target detection",
    "target detector",
    "oriented object detection",
    "computer vision",
    "visual detection",
)
_AERIAL_QUERY_HINTS = (
    "uav",
    "unmanned aerial",
    "aerial",
    "drone",
    "visdrone",
    "remote sensing",
)
_AERIAL_CANDIDATE_TERMS = (
    "uav",
    "unmanned aerial",
    "aerial",
    "drone",
    "visdrone",
    "remote sensing",
)


def _contains_any(value: str, terms: tuple[str, ...]) -> bool:
    return any(term in value for term in terms)


def required_candidate_term_groups(query: str) -> tuple[tuple[str, ...], ...]:
    normalized = query.casefold()
    groups: list[tuple[str, ...]] = []
    if _contains_any(normalized, _AERIAL_QUERY_HINTS):
        groups.append(_AERIAL_CANDIDATE_TERMS)
    if _contains_any(normalized, _SMALL_OBJECT_QUERY_HINTS):
        groups.append(_SMALL_OBJECT_CANDIDATE_TERMS)
    if _contains_any(normalized, _OBJECT_DETECTION_QUERY_HINTS):
        groups.append(_OBJECT_DETECTION_CANDIDATE_TERMS)
    return tuple(groups)


def matches_required_candidate_terms(query: str, candidate_text: str) -> bool:
    normalized_candidate = candidate_text.casefold()
    return all(
        _contains_any(normalized_candidate, group)
        for group in required_candidate_term_groups(query)
    )


__all__ = [
    "matches_required_candidate_terms",
    "required_candidate_term_groups",
]

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
    "small instance",
    "tiny instance",
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
    "satellite image",
    "overhead image",
)
_ROAD_CONTEXT_QUERY_HINTS = ("road", "pavement", "asphalt")
_ROAD_CONTEXT_CANDIDATE_TERMS = (
    "road",
    "roadway",
    "pavement",
    "asphalt",
    "transportation infrastructure",
)
_ROAD_DEFECT_QUERY_HINTS = ("crack", "anomaly", "distress", "damage")
_ROAD_DEFECT_CANDIDATE_TERMS = (
    "crack",
    "cracking",
    "road anomaly",
    "pavement anomaly",
    "pavement distress",
    "road damage",
    "surface distress",
)
_SKIN_QUERY_HINTS = (
    "skin lesion",
    "skin cancer",
    "dermoscopy",
    "dermoscopic",
    "melanoma",
)
_SKIN_CANDIDATE_TERMS = (
    "skin lesion",
    "skin cancer",
    "dermoscopy",
    "dermoscopic",
    "melanoma",
    "cutaneous lesion",
    "dermatology",
)
_SKIN_TASK_QUERY_HINTS = ("classification", "classifier", "diagnosis", "explainability")
_SKIN_TASK_CANDIDATE_TERMS = (
    "classification",
    "classifier",
    "diagnosis",
    "recognition",
    "explainability",
    "interpretability",
    "grad-cam",
    "class activation",
)
_STEEL_QUERY_HINTS = (
    "steel",
    "metal surface",
    "metallic surface",
    "neu-det",
    "gc10-det",
)
_STEEL_CANDIDATE_TERMS = (
    "steel",
    "metal surface",
    "metallic surface",
    "strip steel",
    "hot-rolled",
    "hot rolled",
    "cold-rolled",
    "cold rolled",
    "neu-det",
    "gc10-det",
)
_SURFACE_DEFECT_QUERY_HINTS = ("surface defect", "defect detection", "defect classification")
_SURFACE_DEFECT_CANDIDATE_TERMS = (
    "surface defect",
    "surface flaw",
    "defect detection",
    "defect classification",
    "industrial defect",
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

    if _contains_any(normalized, _ROAD_CONTEXT_QUERY_HINTS) and _contains_any(
        normalized, _ROAD_DEFECT_QUERY_HINTS
    ):
        groups.extend((_ROAD_CONTEXT_CANDIDATE_TERMS, _ROAD_DEFECT_CANDIDATE_TERMS))

    if _contains_any(normalized, _SKIN_QUERY_HINTS):
        groups.append(_SKIN_CANDIDATE_TERMS)
        if _contains_any(normalized, _SKIN_TASK_QUERY_HINTS):
            groups.append(_SKIN_TASK_CANDIDATE_TERMS)

    if _contains_any(normalized, _STEEL_QUERY_HINTS) and _contains_any(
        normalized, _SURFACE_DEFECT_QUERY_HINTS
    ):
        groups.extend((_STEEL_CANDIDATE_TERMS, _SURFACE_DEFECT_CANDIDATE_TERMS))

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

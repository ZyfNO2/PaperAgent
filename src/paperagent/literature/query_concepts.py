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
_LOW_LIGHT_QUERY_HINTS = (
    "low-light",
    "low light",
    "nighttime",
    "night-time",
    "night pedestrian",
)
_LOW_LIGHT_CANDIDATE_TERMS = (
    "low-light",
    "low light",
    "nighttime",
    "night-time",
    "at night",
    "darkness",
    "poor illumination",
    "adverse illumination",
    "varying illumination",
    "illumination factor",
    "infrared",
    "thermal image",
)
_PEDESTRIAN_QUERY_HINTS = ("pedestrian", "person detection", "people detection")
_PEDESTRIAN_CANDIDATE_TERMS = (
    "pedestrian",
    "person detection",
    "people detection",
    "human detection",
    "walking person",
)
_ACTION_QUERY_HINTS = (
    "action recognition",
    "activity recognition",
    "human action",
    "skeleton action",
)
_ACTION_CANDIDATE_TERMS = (
    "action recognition",
    "activity recognition",
    "human action",
    "human activity",
    "skeleton-based action",
    "pose-based human action",
    "video action",
)
_VISUAL_ACTION_QUERY_HINTS = (
    "camera",
    "video",
    "rgb",
    "pose",
    "skeleton",
)
_VISUAL_ACTION_CANDIDATE_TERMS = (
    "camera",
    "video",
    "rgb",
    "image sequence",
    "visual stream",
    "pose",
    "skeleton",
    "keypoint",
    "optical flow",
)
_GESTURE_QUERY_HINTS = (
    "gesture recognition",
    "hand gesture",
    "sign language recognition",
)
_GESTURE_CANDIDATE_TERMS = (
    "gesture recognition",
    "hand gesture",
    "sign language recognition",
    "sign language classification",
    "gesture classification",
    "recognize gestures",
)
_MOBILE_GESTURE_QUERY_HINTS = (
    "mobile",
    "smartphone",
    "on-device",
    "edge",
    "lightweight",
)
_MOBILE_DEPLOYMENT_CANDIDATE_TERMS = (
    "mobile",
    "smartphone",
    "on-device",
    "edge device",
    "embedded",
    "lightweight",
    "real-time",
    "real time",
    "low-latency",
    "low latency",
    "efficient",
    "resource-constrained",
    "small model",
    "model size",
)
_MEDICAL_IMAGING_QUERY_HINTS = (
    "medical image",
    "medical imaging",
    "radiology",
    "clinical imaging",
)
_MEDICAL_IMAGING_CANDIDATE_TERMS = (
    "medical image",
    "medical imaging",
    "radiology",
    "radiological",
    "clinical imaging",
    "ct image",
    "mri",
    "magnetic resonance",
    "pet-ct",
    "pet/ct",
    "ultrasound",
    "fundus",
    "retinal",
    "ophthalmic",
)
_MULTIMODAL_FUSION_QUERY_HINTS = (
    "multimodal",
    "multi-modal",
    "multi modal",
    "cross-modal",
    "cross modal",
    "modality fusion",
)
_MULTIMODAL_FUSION_CANDIDATE_TERMS = (
    "multimodal",
    "multi-modal",
    "multi modal",
    "multimodality",
    "multiple modalities",
    "cross-modal",
    "cross modal",
    "modality fusion",
    "fusion of medical imaging",
    "combine medical imaging",
    "combining medical imaging",
    "imaging and electronic health records",
)
_STRICT_CLASSIFICATION_QUERY_HINTS = (
    "classification",
    "classifier",
)
_STRICT_CLASSIFICATION_CANDIDATE_TERMS = (
    "classification",
    "classifier",
    "classify",
    "categorization",
    "multi-class",
    "multiclass",
    "multi-label",
    "multilabel",
    "class label",
    "grading",
)
_DIAGNOSIS_QUERY_HINTS = (
    "diagnosis",
    "diagnostic",
    "prediction",
    "prognosis",
)
_DIAGNOSIS_CANDIDATE_TERMS = (
    "diagnosis",
    "diagnostic",
    "prediction",
    "prognosis",
    "disease detection",
)
_LONG_DOCUMENT_QUERY_HINTS = (
    "long document",
    "long text",
    "long-context",
    "long context",
    "long-range",
    "hierarchical",
    "chunk",
    "sparse transformer",
)
_LONG_DOCUMENT_CANDIDATE_TERMS = (
    "long document",
    "long text",
    "long-context",
    "long context",
    "long-range",
    "lengthy document",
    "hierarchical",
    "chunk-level",
    "document-level",
    "segment-level",
    "sparse attention",
    "longformer",
    "bigbird",
)
_TEXT_CLASSIFICATION_QUERY_HINTS = (
    "text classification",
    "document classification",
    "document categorization",
)
_TEXT_CLASSIFICATION_CANDIDATE_TERMS = (
    "text classification",
    "document classification",
    "document categorization",
    "classify documents",
    "classifying documents",
    "document classifier",
    "text categorization",
)
_FEW_SHOT_QUERY_HINTS = (
    "few-shot",
    "few shot",
    "low-resource",
    "low resource",
    "few examples",
    "prototypical",
    "prototype",
)
_FEW_SHOT_CANDIDATE_TERMS = (
    "few-shot",
    "few shot",
    "low-resource",
    "low resource",
    "few examples",
    "few labeled",
    "k-shot",
    "prototypical",
    "prototype learning",
)
_INTENT_QUERY_HINTS = (
    "intent detection",
    "intent classification",
    "intent recognition",
    "intention recognition",
    "user intent",
)
_INTENT_CANDIDATE_TERMS = (
    "intent detection",
    "intent classification",
    "intent recognition",
    "user intent",
    "unknown intent",
    "out-of-scope intent",
    "out of scope intent",
    "task-oriented dialogue intent",
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

    if _contains_any(normalized, _LOW_LIGHT_QUERY_HINTS) and _contains_any(
        normalized, _PEDESTRIAN_QUERY_HINTS
    ):
        groups.extend((_LOW_LIGHT_CANDIDATE_TERMS, _PEDESTRIAN_CANDIDATE_TERMS))

    if _contains_any(normalized, _ACTION_QUERY_HINTS):
        groups.append(_ACTION_CANDIDATE_TERMS)
        if _contains_any(normalized, _VISUAL_ACTION_QUERY_HINTS):
            groups.append(_VISUAL_ACTION_CANDIDATE_TERMS)

    if _contains_any(normalized, _GESTURE_QUERY_HINTS):
        groups.append(_GESTURE_CANDIDATE_TERMS)
        if _contains_any(normalized, _MOBILE_GESTURE_QUERY_HINTS):
            groups.append(_MOBILE_DEPLOYMENT_CANDIDATE_TERMS)

    if _contains_any(normalized, _MEDICAL_IMAGING_QUERY_HINTS) and _contains_any(
        normalized, _MULTIMODAL_FUSION_QUERY_HINTS
    ):
        groups.extend((_MEDICAL_IMAGING_CANDIDATE_TERMS, _MULTIMODAL_FUSION_CANDIDATE_TERMS))
        if _contains_any(normalized, _STRICT_CLASSIFICATION_QUERY_HINTS):
            groups.append(_STRICT_CLASSIFICATION_CANDIDATE_TERMS)
        elif _contains_any(normalized, _DIAGNOSIS_QUERY_HINTS):
            groups.append(_DIAGNOSIS_CANDIDATE_TERMS)

    if _contains_any(normalized, _LONG_DOCUMENT_QUERY_HINTS) and _contains_any(
        normalized, _TEXT_CLASSIFICATION_QUERY_HINTS
    ):
        groups.extend((_LONG_DOCUMENT_CANDIDATE_TERMS, _TEXT_CLASSIFICATION_CANDIDATE_TERMS))

    if _contains_any(normalized, _INTENT_QUERY_HINTS):
        groups.append(_INTENT_CANDIDATE_TERMS)
        if _contains_any(normalized, _FEW_SHOT_QUERY_HINTS):
            groups.append(_FEW_SHOT_CANDIDATE_TERMS)

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

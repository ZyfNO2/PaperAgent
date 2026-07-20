from __future__ import annotations

import pytest

from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.literature.task_query_overrides import override_task_query

_MOBILE_BASELINE_COMPARISON_QUERY = " ".join(
    (
        "MobileNetV2 EfficientNet-Lite ShuffleNetV2",
        "plant disease classification benchmark",
    )
)
_PLANT_DATASET_METRIC_QUERY = " ".join(
    (
        "plant disease classification field dataset macro F1",
        "calibration device latency",
    )
)


@pytest.mark.parametrize(
    ("query", "gap_id", "description", "expected"),
    [
        (
            "MobileNetV3 plant disease classification lightweight backbone benchmark",
            "baseline_comparison",
            "verify the supplied MobileNetV3 backbone and baseline",
            "Searching for MobileNetV3",
        ),
        (
            "MobileNetV2 EfficientNet-Lite ShuffleNetV2 plant disease classification benchmark",
            "baseline_comparison",
            "compare lightweight plant-disease baselines",
            _MOBILE_BASELINE_COMPARISON_QUERY,
        ),
        (
            "MobileNetV3 failure mechanism limitation plant disease recognition",
            "mechanism_and_limitation",
            "field background shift, small symptoms, and class imbalance",
            "plant disease classification field imagery small lesions "
            "background shift class imbalance",
        ),
        (
            "plant disease datasets and evaluation metrics",
            "task_dataset_and_metrics",
            "field dataset, macro-F1, calibration, and device latency",
            _PLANT_DATASET_METRIC_QUERY,
        ),
    ],
)
def test_case_017_queries_separate_backbone_identity_from_task_evidence(
    query: str, gap_id: str, description: str, expected: str
) -> None:
    result = override_task_query(
        query,
        gap_id=gap_id,
        gap_description=description,
        research_context="MobileNetV3 for lightweight plant disease classification",
    )
    assert result.query == expected


def test_exact_mobilenetv3_identity_query_accepts_original_paper() -> None:
    assert (
        matches_specialized_candidate_terms(
            "Searching for MobileNetV3",
            "Searching for MobileNetV3 presents efficient mobile architectures "
            "evaluated on ImageNet.",
        )
        is True
    )


@pytest.mark.parametrize(
    "candidate",
    [
        "MobileNet-CA-YOLO uses MobileNetV3 for rice pest and disease detection.",
        "A MobileNetV3 transfer-learning model classifies tomato leaf disease.",
    ],
)
def test_exact_mobilenetv3_identity_query_rejects_application_papers(candidate: str) -> None:
    assert matches_specialized_candidate_terms("Searching for MobileNetV3", candidate) is False


def test_plant_disease_query_accepts_task_matched_evidence() -> None:
    query = (
        "plant disease classification field imagery small lesions background shift class imbalance"
    )
    candidate = (
        "A lightweight network classifies rice leaf disease in field images with small symptom "
        "lesions, complex backgrounds, and class imbalance."
    )
    assert matches_specialized_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    "candidate",
    [
        "Mini lesions detection on diabetic retinopathy images via large-scale CNN features.",
        "A MobileNetV3 model classifies human skin lesions and retinal disease.",
        "A network identifies plant species from healthy leaf images.",
    ],
)
def test_plant_disease_query_rejects_cross_domain_or_non_disease_evidence(
    candidate: str,
) -> None:
    query = (
        "plant disease classification field imagery small lesions background shift class imbalance"
    )
    assert matches_specialized_candidate_terms(query, candidate) is False

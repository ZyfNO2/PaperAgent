from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Nighttime pedestrian detection under low-light conditions uses foreground and "
            "background contrast attention.",
        ),
        (
            "human action recognition camera temporal robustness",
            "A pose-based human action recognition model captures temporal order in video.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A lightweight hand gesture recognition system runs on constrained devices.",
        ),
        (
            "multimodal medical imaging disease classification feature fusion",
            "A multimodal medical imaging classifier fuses MRI and clinical features for "
            "multi-class disease classification.",
        ),
    ],
)
def test_second_batch_guards_accept_task_matched_candidates(
    query: str,
    candidate: str,
) -> None:
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Low-light image enhancement improves naturalness through degradation learning.",
        ),
        (
            "human action recognition camera temporal robustness",
            "A survey of wearable devices studies communication security and power use.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A Metaverse taxonomy reviews mobile access, virtual currency, and social content.",
        ),
        (
            "multimodal medical imaging disease classification feature fusion",
            "The BRATS benchmark evaluates multimodal brain tumor image segmentation.",
        ),
        (
            "multimodal medical imaging disease classification feature fusion",
            "A survey reviews attention mechanisms for generic computer vision tasks.",
        ),
        (
            "multimodal medical imaging disease classification feature fusion",
            "Liver Segmentation from Multimodal Images uses HED and Mask R-CNN for automatic "
            "liver segmentation in computer-aided diagnosis.",
        ),
    ],
)
def test_second_batch_guards_reject_cross_task_false_positives(
    query: str,
    candidate: str,
) -> None:
    assert matches_required_candidate_terms(query, candidate) is False


def test_diagnosis_only_query_can_use_diagnostic_evidence_without_classification() -> None:
    query = "multimodal medical imaging diagnosis feature fusion"
    candidate = (
        "A multimodal medical imaging diagnostic system fuses MRI and electronic health records."
    )

    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "gap_id", "expected"),
    [
        (
            "multimodal medical image fusion classification baseline comparison benchmark dataset",
            "baseline_comparison",
            "multimodal medical imaging disease classification feature fusion baseline",
        ),
        (
            "multimodal medical image fusion classification mechanism limitation "
            "failure mode survey",
            "mechanism_limitation_parallel",
            "multimodal medical imaging disease classification feature fusion mechanism "
            "limitation failure mode",
        ),
        (
            "multimodal medical image fusion classification negative results limitations "
            "generalization noise sensitivity",
            "risk_negative_evidence",
            "multimodal medical imaging disease classification feature fusion negative "
            "limitations generalization noise sensitivity",
        ),
    ],
)
def test_multimodal_medical_queries_are_disambiguated_for_academic_indexes(
    query: str,
    gap_id: str,
    expected: str,
) -> None:
    result = refine_search_query(
        query,
        gap_id=gap_id,
        gap_description="multimodal medical classification evidence",
    )

    assert result.changed is True
    assert result.query == expected
    assert result.reason is not None
    assert "explicit disease-classification terms" in result.reason

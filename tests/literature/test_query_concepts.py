from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.ranking import rank_papers
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    PaperRecord,
    QueryLane,
)

_QUERY = "lightweight UAV aerial small object detection VisDrone AP_small latency TensorRT"


def _plan() -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question=_QUERY,
        scope="single-case relevance regression",
        query_lanes=[
            QueryLane(
                lane_id="case-001",
                purpose="method",
                query=_QUERY,
                source_preferences=["arxiv"],
                gap_ids=["gap-001"],
            )
        ],
        required_gap_ids=["gap-001"],
        max_rounds=1,
    )


def test_required_concepts_accept_visual_aerial_small_object_detection() -> None:
    text = (
        "Efficient ConvNet-based Object Detection for Unmanned Aerial Vehicles. "
        "The visual detection method detects small objects in UAV imagery with lower compute."
    )

    assert matches_required_candidate_terms(_QUERY, text) is True


def test_required_concepts_reject_uav_rf_fingerprint_detection() -> None:
    text = (
        "Detection and Classification of UAVs Using RF Fingerprints. "
        "A passive radio frequency system classifies controller signals under interference."
    )

    assert matches_required_candidate_terms(_QUERY, text) is False


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "remote sensing dense small object detection",
            "Remote sensing small object detection with a multi-scale detector for tiny "
            "instances in satellite images.",
        ),
        (
            "road crack detection edge deployment",
            "Edge AI detection of road anomalies and pavement cracks under mobile constraints.",
        ),
        (
            "skin lesion classification explainability",
            "Interpretable dermoscopic skin lesion classification using Grad-CAM.",
        ),
        (
            "steel surface defect detection",
            "Detection of surface defects on hot-rolled strip steel with a lightweight network.",
        ),
    ],
)
def test_domain_guards_accept_task_matched_candidates(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "road crack detection edge deployment",
            "Unmanned Aerial Vehicles: a survey on civil applications and key challenges.",
        ),
        (
            "skin lesion classification explainability",
            "Advances in general medical image segmentation and point-of-care testing.",
        ),
        (
            "steel surface defect detection",
            "Digital-twin operation and maintenance of electrical transformers using DETR.",
        ),
        (
            "steel surface defect detection",
            "Visual concrete bridge defect classification and detection using deep learning.",
        ),
        (
            "remote sensing dense small object detection",
            "Remote sensing scene classification with global land-cover representations.",
        ),
    ],
)
def test_domain_guards_reject_cross_domain_false_positives(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate) is False


def test_ranking_zeros_relevance_for_semantic_false_positive() -> None:
    relevant = PaperRecord(
        paper_id="relevant",
        canonical_title="Efficient UAV Small Object Detection",
        abstract="A visual object detection method for small objects in aerial images.",
        arxiv_id="2401.00001",
        verification_status="verified",
        matched_gap_ids=["gap-001"],
    )
    false_positive = PaperRecord(
        paper_id="rf-uav",
        canonical_title="Detection and Classification of UAVs Using RF Fingerprints",
        abstract="A radio frequency classifier detects UAV controller signals.",
        arxiv_id="2401.00002",
        verification_status="verified",
        matched_gap_ids=["gap-001"],
    )

    ranked = rank_papers([false_positive, relevant], _plan(), now_year=2026)
    by_id = {paper.paper_id: paper for paper in ranked}

    assert by_id["relevant"].rank_features is not None
    assert by_id["relevant"].rank_features.relevance > 0
    assert by_id["rf-uav"].rank_features is not None
    assert by_id["rf-uav"].rank_features.relevance == 0
    assert "required_concepts=missing" in by_id["rf-uav"].rank_features.explanation

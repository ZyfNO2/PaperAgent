from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import (
    concept_alignment_score,
    matches_required_candidate_terms,
    named_identifiers,
)
from paperagent.literature.ranking import rank_papers
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.schemas.literature import LiteratureQueryPlan, PaperRecord, QueryLane

_QUERY = "physics-informed glacier calving surrogate finite-volume simulation"


def _plan() -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question=_QUERY,
        scope="held-out semantic-alignment regression",
        query_lanes=[
            QueryLane(
                lane_id="held-out-glacier",
                purpose="method",
                query=_QUERY,
                source_preferences=["arxiv"],
                gap_ids=["gap-held-out"],
            )
        ],
        required_gap_ids=["gap-held-out"],
        max_rounds=1,
    )


def test_generic_concepts_accept_unseen_domain_candidate() -> None:
    candidate = (
        "A physics-informed surrogate accelerates finite-volume simulations of glacier "
        "calving fronts under changing boundary conditions."
    )
    assert matches_required_candidate_terms(_QUERY, candidate)
    assert concept_alignment_score(_QUERY, candidate) >= 0.4


def test_generic_concepts_reject_cross_domain_false_positive() -> None:
    candidate = "A finite-volume neural surrogate predicts combustion chemistry in gas turbines."
    assert not matches_required_candidate_terms(_QUERY, candidate)


@pytest.mark.parametrize(
    ("query", "candidate", "expected"),
    [
        (
            "marine debris hyperspectral mapping",
            "Hyperspectral mapping of floating marine debris in coastal imagery.",
            True,
        ),
        (
            "acoustic bat species monitoring",
            "Passive acoustic monitoring identifies bat species from ultrasonic calls.",
            True,
        ),
        (
            "soil salinity microwave inversion",
            "Microwave inversion estimates soil salinity in irrigated fields.",
            True,
        ),
        (
            "marine debris hyperspectral mapping",
            "Hyperspectral analysis of pharmaceutical tablet coatings.",
            False,
        ),
        (
            "acoustic bat species monitoring",
            "Acoustic monitoring of industrial bearing wear.",
            False,
        ),
    ],
)
def test_held_out_domain_alignment(query: str, candidate: str, expected: bool) -> None:
    assert matches_required_candidate_terms(query, candidate) is expected


def test_counterfactual_model_name_does_not_override_task_mismatch() -> None:
    query = "AeroFormer-X2 marine debris hyperspectral mapping"
    same_name_wrong_task = (
        "AeroFormer-X2 forecasts lithium battery degradation from charging curves."
    )
    different_name_right_task = "CoastSpec maps marine debris from hyperspectral coastal imagery."
    assert not matches_required_candidate_terms(query, same_name_wrong_task)
    assert matches_required_candidate_terms(query, different_name_right_task)


def test_identity_guard_is_form_based_not_name_list_based() -> None:
    query = "original AeroFormer-X2 architecture paper"
    assert named_identifiers(query) == ("aeroformerx2",)
    assert matches_specialized_candidate_terms(
        query,
        "AeroFormer-X2: an efficient architecture for atmospheric flow modelling.",
    )
    assert not matches_specialized_candidate_terms(
        query,
        "An application study compares several atmospheric flow architectures.",
    )


def test_mixed_language_query_uses_generic_cjk_concepts() -> None:
    query = "日语长文本情感分析 long-context"
    candidate = "面向日语长文本的情感分析与长上下文建模方法"
    assert matches_required_candidate_terms(query, candidate)


def test_ranking_zeros_relevance_for_semantic_false_positive() -> None:
    relevant = PaperRecord(
        paper_id="relevant",
        canonical_title="Physics-Informed Glacier Calving Surrogates",
        abstract="Finite-volume glacier simulation with calving-front dynamics.",
        arxiv_id="2601.00001",
        verification_status="verified",
        matched_gap_ids=["gap-held-out"],
    )
    false_positive = PaperRecord(
        paper_id="combustion",
        canonical_title="Finite-Volume Surrogates for Turbine Combustion",
        abstract="Neural chemistry acceleration for gas turbines.",
        arxiv_id="2601.00002",
        verification_status="verified",
        matched_gap_ids=["gap-held-out"],
    )

    ranked = rank_papers([false_positive, relevant], _plan(), now_year=2026)
    by_id = {paper.paper_id: paper for paper in ranked}

    assert by_id["relevant"].rank_features is not None
    assert by_id["relevant"].rank_features.relevance > 0
    assert by_id["combustion"].rank_features is not None
    assert by_id["combustion"].rank_features.relevance == 0
    assert "required_concepts=missing" in by_id["combustion"].rank_features.explanation

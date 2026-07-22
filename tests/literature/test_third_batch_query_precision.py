from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "peatland methane flux chamber modelling",
            "Chamber measurements and process modelling estimate methane flux in peatlands.",
        ),
        (
            "ancient manuscript script identification multispectral",
            "Multispectral imaging identifies scripts in damaged ancient manuscripts.",
        ),
        (
            "seagrass meadow restoration drone mapping",
            "Drone mapping evaluates restoration progress in seagrass meadows.",
        ),
    ],
)
def test_held_out_domains_accept_task_matched_candidates(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "peatland methane flux chamber modelling",
            "Methane combustion modelling in industrial chambers.",
        ),
        (
            "ancient manuscript script identification multispectral",
            "Multispectral crop disease identification from field images.",
        ),
        (
            "seagrass meadow restoration drone mapping",
            "Drone mapping of urban traffic congestion.",
        ),
    ],
)
def test_held_out_domains_reject_cross_task_candidates(query: str, candidate: str) -> None:
    assert not matches_required_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    ("gap_id", "description"),
    [
        ("baseline", "baseline reproducibility"),
        ("mechanism", "measurement failure mechanism"),
        ("alternative", "parallel alternatives"),
        ("risk", "risk and negative evidence"),
    ],
)
def test_gap_role_does_not_generate_a_canonical_query(gap_id: str, description: str) -> None:
    query = "peatland methane flux chamber modelling benchmark evidence dataset uncertainty"
    result = refine_search_query(
        query,
        gap_id=gap_id,
        gap_description=description,
        research_context="northern wetland carbon cycle",
    )
    assert result.query == "peatland methane flux chamber modelling uncertainty"
    assert result.reason is not None


def test_language_or_domain_context_is_not_silently_added() -> None:
    query = "manuscript script identification multispectral"
    result = refine_search_query(
        query,
        gap_id="baseline",
        gap_description="baseline evidence",
        research_context="Japanese historical documents",
    )
    assert result.query == query
    assert "Japanese" not in result.query
    assert result.changed is False


def test_counterfactual_task_swap_is_rejected() -> None:
    query = "peatland methane flux chamber modelling"
    same_instrument_wrong_task = "Chamber modelling of aerosol deposition in clean rooms."
    same_domain_wrong_measurement = "Peatland vegetation mapping from aerial photographs."
    assert not matches_required_candidate_terms(query, same_instrument_wrong_task)
    assert not matches_required_candidate_terms(query, same_domain_wrong_measurement)

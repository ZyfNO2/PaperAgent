from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms


def test_unseen_named_architecture_identity_query_accepts_origin_paper() -> None:
    query = "original RiverNet-Z4 architecture paper"
    candidate = "RiverNet-Z4: a neural architecture for river discharge forecasting."
    assert matches_specialized_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        "A comparison of efficient river forecasting architectures.",
        "RiverNet-Z3 is applied to flood warning in mountain catchments.",
    ],
)
def test_unseen_named_architecture_identity_query_rejects_wrong_identity(
    candidate: str,
) -> None:
    assert not matches_specialized_candidate_terms(
        "original RiverNet-Z4 architecture paper",
        candidate,
    )


def test_task_alignment_accepts_same_domain_and_problem() -> None:
    query = "river discharge forecasting mountain catchment uncertainty"
    candidate = (
        "Probabilistic river discharge forecasting for mountain catchments quantifies "
        "predictive uncertainty under sparse gauge observations."
    )
    assert matches_required_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        "Uncertainty-aware electricity demand forecasting for urban microgrids.",
        "Mountain image classification from satellite photographs.",
        "A river species taxonomy from environmental DNA samples.",
    ],
)
def test_task_alignment_rejects_partial_cross_domain_overlap(candidate: str) -> None:
    query = "river discharge forecasting mountain catchment uncertainty"
    assert not matches_required_candidate_terms(query, candidate)

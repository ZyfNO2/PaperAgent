from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms


@pytest.mark.parametrize(
    ("query", "candidate", "expected"),
    [
        (
            "few-shot whale call localization hydrophone array",
            "Few-shot localization of whale calls with a sparse hydrophone array.",
            True,
        ),
        (
            "few-shot whale call localization hydrophone array",
            "Few-shot localization of indoor robots with Wi-Fi arrays.",
            False,
        ),
        (
            "urban heat island causal inference satellite temperature",
            "Causal inference for urban heat islands from satellite land-surface temperature.",
            True,
        ),
        (
            "urban heat island causal inference satellite temperature",
            "Causal inference for treatment effects in hospital records.",
            False,
        ),
    ],
)
def test_generic_candidate_alignment(query: str, candidate: str, expected: bool) -> None:
    assert matches_required_candidate_terms(query, candidate) is expected


def test_identity_query_requires_exact_unseen_identifier() -> None:
    query = "source paper introducing HydroLoc-Q7"
    assert matches_specialized_candidate_terms(
        query,
        "HydroLoc-Q7 introduces sparse-array localization for marine acoustics.",
    )
    assert not matches_specialized_candidate_terms(
        query,
        "HydroLoc-Q6 is extended for sparse-array localization.",
    )


def test_non_identity_query_allows_parallel_method_without_named_baseline() -> None:
    query = "HydroLoc-Q7 limitations parallel acoustic localization methods"
    candidate = "A Bayesian sparse-array method localizes whale calls under sensor dropout."
    assert matches_specialized_candidate_terms(query, candidate)

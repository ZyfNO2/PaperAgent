from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms


def test_unseen_domain_candidate_passes_generic_alignment() -> None:
    query = "coral bleaching thermal stress satellite monitoring"
    candidate = (
        "Satellite monitoring of coral bleaching links thermal stress anomalies to reef decline."
    )
    assert matches_required_candidate_terms(query, candidate)
    assert matches_specialized_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    "candidate",
    [
        "Thermal stress monitoring of industrial turbine blades.",
        "Satellite monitoring of crop irrigation and soil moisture.",
        "Coral species recognition from healthy reef photographs.",
    ],
)
def test_unseen_domain_candidate_rejects_cross_task_noise(candidate: str) -> None:
    query = "coral bleaching thermal stress satellite monitoring"
    assert not matches_required_candidate_terms(query, candidate)


def test_same_method_family_does_not_override_domain_change() -> None:
    query = "contrastive learning coral bleaching satellite monitoring"
    candidate = "Contrastive learning for financial fraud detection in transaction graphs."
    assert not matches_required_candidate_terms(query, candidate)

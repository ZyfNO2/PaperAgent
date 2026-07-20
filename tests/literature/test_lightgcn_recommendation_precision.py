from __future__ import annotations

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms


def test_unseen_task_accepts_directly_aligned_evidence() -> None:
    query = "tidal turbine blade erosion acoustic monitoring"
    candidate = (
        "Acoustic monitoring detects blade erosion in tidal turbines under marine loading."
    )
    assert matches_required_candidate_terms(query, candidate)
    assert matches_specialized_candidate_terms(query, candidate)


def test_unseen_task_rejects_cross_domain_evidence() -> None:
    query = "tidal turbine blade erosion acoustic monitoring"
    candidate = "Acoustic monitoring detects bearing wear in factory conveyor motors."
    assert not matches_required_candidate_terms(query, candidate)


def test_non_identity_query_does_not_require_named_method() -> None:
    query = "TideGuard-R8 blade erosion limitations alternative monitoring methods"
    candidate = "A vibration-based method detects marine turbine blade erosion."
    assert matches_specialized_candidate_terms(query, candidate)


def test_identity_query_requires_exact_unseen_method_name() -> None:
    query = "original TideGuard-R8 method paper"
    assert matches_specialized_candidate_terms(
        query,
        "TideGuard-R8 introduces acoustic monitoring for tidal turbine erosion.",
    )
    assert not matches_specialized_candidate_terms(
        query,
        "TideGuard-R7 is extended for tidal turbine erosion monitoring.",
    )

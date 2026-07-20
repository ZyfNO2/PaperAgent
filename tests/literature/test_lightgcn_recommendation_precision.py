from __future__ import annotations

from paperagent.literature.specialized_guards import matches_specialized_candidate_terms


def test_lightgcn_query_accepts_recommendation_evidence() -> None:
    query = (
        "LightGCN graph convolutional network recommendation reproducible implementation "
        "NGCF PinSAGE matrix factorization baseline"
    )
    candidate = (
        "XSimGCL: Towards Extremely Simple Graph Contrastive Learning for Recommendation. "
        "A collaborative filtering recommender trained on user-item interactions."
    )

    assert matches_specialized_candidate_terms(query, candidate)


def test_lightgcn_query_rejects_energy_forecasting_evidence() -> None:
    query = (
        "contrastive learning recommendation limitations negative failure cases "
        "computational overhead hyperparameter sensitivity long-tail cold start"
    )
    candidate = (
        "Optimizing solar and wind forecasting with iHow optimization algorithm and "
        "multi-scale attention networks"
    )

    assert not matches_specialized_candidate_terms(query, candidate)


def test_non_recommendation_query_is_not_constrained_by_recommendation_guard() -> None:
    query = "solar and wind forecasting multi-scale attention network"
    candidate = (
        "Optimizing solar and wind forecasting with iHow optimization algorithm and "
        "multi-scale attention networks"
    )

    assert matches_specialized_candidate_terms(query, candidate)

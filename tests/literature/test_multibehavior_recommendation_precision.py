from __future__ import annotations

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.specialized_guards import matches_specialized_candidate_terms
from paperagent.literature.task_query_overrides import override_task_query


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_comparison",
            "multi-behavior recommendation baseline comparison",
            "multi-behavior recommendation graph neural network",
        ),
        (
            "failure_mechanism",
            "auxiliary behavior noise mechanism and gated transfer",
            "multi-behavior recommendation gated auxiliary behavior transfer",
        ),
        (
            "optional_risk",
            "cold-start, long-tail, and negative evidence",
            "multi-behavior recommendation data sparsity cold-start long-tail",
        ),
    ],
)
def test_case_015_queries_are_canonicalized_by_role(
    gap_id: str, description: str, expected: str
) -> None:
    result = override_task_query(
        "面向电商场景的多行为推荐系统基线方法数据集评估指标效率",
        gap_id=gap_id,
        gap_description=description,
        research_context="面向电商场景的多行为推荐系统",
    )
    assert result.changed is True
    assert result.query == expected


def test_multibehavior_recommendation_guard_accepts_task_matched_paper() -> None:
    query = "multi-behavior recommendation graph neural network"
    candidate = (
        "A graph convolutional network for multi-behavior recommendation models "
        "click, cart, and purchase interactions in an e-commerce recommender system."
    )
    assert matches_specialized_candidate_terms(query, candidate) is True
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    "candidate",
    [
        "A multi-behavior virtual patient model simulates clinical treatment trajectories.",
        "A graph neural network predicts molecular interactions for drug discovery.",
        "A single-behavior recommender optimizes only purchase interactions.",
    ],
)
def test_multibehavior_recommendation_guard_rejects_cross_task_noise(
    candidate: str,
) -> None:
    query = "multi-behavior recommendation graph neural network"
    assert matches_specialized_candidate_terms(query, candidate) is False
    assert matches_required_candidate_terms(query, candidate) is False

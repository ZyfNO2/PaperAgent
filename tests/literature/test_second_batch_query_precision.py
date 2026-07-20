from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "mangrove biomass lidar estimation",
            "LiDAR estimation of mangrove biomass from coastal forest structure.",
        ),
        (
            "volcanic ash plume satellite retrieval",
            "Satellite retrieval of volcanic ash plumes from multispectral imagery.",
        ),
        (
            "microplastic river transport particle tracking",
            "Particle tracking models microplastic transport through river networks.",
        ),
    ],
)
def test_held_out_candidates_match_task_constraints(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate)


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "mangrove biomass lidar estimation",
            "LiDAR estimation of urban building heights.",
        ),
        (
            "volcanic ash plume satellite retrieval",
            "Satellite retrieval of ocean chlorophyll concentration.",
        ),
        (
            "microplastic river transport particle tracking",
            "Particle tracking of aerosols in indoor ventilation.",
        ),
    ],
)
def test_held_out_candidates_reject_cross_domain_overlap(query: str, candidate: str) -> None:
    assert not matches_required_candidate_terms(query, candidate)


def test_refinement_does_not_canonicalize_by_gap_role() -> None:
    query = "mangrove biomass lidar estimation benchmark dataset evidence accuracy efficiency"
    baseline = refine_search_query(
        query,
        gap_id="baseline",
        gap_description="reproducible baseline comparison",
        research_context="coastal carbon monitoring",
    )
    mechanism = refine_search_query(
        query,
        gap_id="failure_mechanism",
        gap_description="measurement bias and failure mechanism",
        research_context="coastal carbon monitoring",
    )
    assert baseline.query == mechanism.query
    assert baseline.query == "mangrove biomass lidar estimation accuracy efficiency"


def test_refinement_does_not_inject_context_modality() -> None:
    query = "animal movement classification baseline reproducible"
    result = refine_search_query(
        query,
        gap_id="baseline",
        gap_description="baseline evidence",
        research_context="camera video pose tracking",
    )
    assert result.query == query
    assert result.changed is False


@pytest.mark.asyncio
async def test_prepare_search_preserves_planner_domain_terms() -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.prepare_search import prepare_search_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import (
        EvidenceGap,
        ResearchPlan,
        ResearchRequest,
        RunBudgets,
        RunContext,
        SearchQuery,
    )
    from paperagent.testing import FixedClock, SequenceIdFactory

    now = datetime(2026, 7, 20, tzinfo=UTC)
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(now),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    gap = EvidenceGap(gap_id="baseline", description="mangrove biomass baseline")
    original = "mangrove biomass lidar estimation benchmark dataset evidence accuracy efficiency"
    plan = ResearchPlan(
        status="ready",
        problem_statement="mangrove biomass estimation",
        scope="coastal forests",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id=gap.gap_id,
                query=original,
                source_types=["paper"],
            )
        ],
        success_criteria=["find a task-matched baseline"],
        risks=["sensor resolution unresolved"],
    )
    state = {
        "request": ResearchRequest(question="estimate mangrove biomass from lidar"),
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=now,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(max_queries_per_round=3),
        ),
        "plan": plan,
    }

    patch = await prepare_search_node(state, {"configurable": {"services": services}})
    prepared = patch["retrieval"].prepared_queries
    assert len(prepared) == 1
    assert prepared[0].query == "mangrove biomass lidar estimation accuracy efficiency"
    assert prepared[0].original_query == original

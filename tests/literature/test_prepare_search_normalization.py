from __future__ import annotations

import pytest

from paperagent.persistence import InMemoryStateStore
from paperagent.providers import FakeLLMProvider, FakeSearchProvider
from paperagent.retrieval.prepare_search import prepare_search_node
from paperagent.runtime import RuntimeServices
from paperagent.schemas import (
    EvidenceGap,
    ResearchPlan,
    RunBudgets,
    RunContext,
    SearchQuery,
)
from paperagent.testing import FixedClock, SequenceIdFactory


@pytest.mark.asyncio
async def test_whitespace_normalization_is_not_recorded_as_semantic_refinement(
    fixed_time,
) -> None:
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    gap = EvidenceGap(gap_id="qa-gap", description="professional QA hallucination evidence")
    plan = ResearchPlan(
        status="ready",
        problem_statement="professional QA hallucination",
        scope="retrieval-grounded answer quality",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="Q5",
                gap_id=gap.gap_id,
                query="professional   QA hallucination",
                source_types=["paper", "web"],
            )
        ],
        success_criteria=["find grounded QA evidence"],
        risks=["unsupported claims"],
    )
    state = {
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=fixed_time,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(max_queries_per_round=5),
        ),
        "plan": plan,
    }

    patch = await prepare_search_node(state, {"configurable": {"services": services}})
    prepared = patch["retrieval"].prepared_queries

    assert len(prepared) == 1
    assert prepared[0].query == "professional QA hallucination"
    assert prepared[0].original_query is None
    assert prepared[0].refinement_reason is None
    assert prepared[0].removed_families == []

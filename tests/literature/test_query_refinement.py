from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.literature.query_refinement import refine_search_query
from paperagent.schemas import PreparedQuery

_LONG_QUERY = (
    "glacier calving finite-volume uncertainty evidence benchmark dataset "
    "evaluation metrics glacier"
)
_REFINED_QUERY = "glacier calving finite-volume uncertainty"


def test_long_query_is_compacted_without_domain_rewrite() -> None:
    result = refine_search_query(
        _LONG_QUERY,
        gap_id="mechanism-gap",
        gap_description="boundary-condition failure mechanism",
        research_context="physics-informed glacier simulation",
    )

    assert result.changed is True
    assert result.query == _REFINED_QUERY
    assert result.removed_families == ()
    assert result.reason is not None
    for preserved in ("glacier", "calving", "finite-volume", "uncertainty"):
        assert preserved in result.query


def test_short_query_is_not_rewritten_from_context_or_gap_role() -> None:
    query = "marine debris hyperspectral mapping"
    result = refine_search_query(
        query,
        gap_id="baseline_comparison",
        gap_description="baseline and strong comparison evidence",
        research_context="unrelated hidden context must not inject terms",
    )
    assert result.changed is False
    assert result.query == query
    assert result.removed_families == ()


@pytest.mark.parametrize(
    "query",
    [
        "arxiv:2401.01234 multimodal temporal super-resolution",
        "10.1234/example.1 multimodal temporal super-resolution",
    ],
)
def test_exact_identifier_query_is_never_refined(query: str) -> None:
    result = refine_search_query(
        query,
        gap_id="failure_mechanism",
        gap_description="mechanism evidence",
    )
    assert result.changed is False
    assert result.query == query


def test_duplicate_tokens_are_removed_only_for_long_queries() -> None:
    query = "coral bleaching thermal stress satellite monitoring evidence study coral thermal"
    result = refine_search_query(
        query,
        gap_id="risk",
        gap_description="negative evidence",
    )
    assert result.query == "coral bleaching thermal stress satellite monitoring"
    assert result.changed is True


def test_domain_names_and_unknown_model_identifiers_are_preserved() -> None:
    query = "RiverNet-Z4 river discharge forecasting comparison dataset evidence efficiency latency"
    result = refine_search_query(
        query,
        gap_id="baseline",
        gap_description="baseline evidence",
    )
    assert result.changed is True
    assert "RiverNet-Z4" in result.query
    assert "river discharge forecasting" in result.query
    assert "efficiency latency" in result.query


def test_prepared_query_requires_complete_refinement_audit() -> None:
    with pytest.raises(ValidationError, match="refinement_reason"):
        PreparedQuery(
            query_id="q1",
            gap_id="g1",
            query="refined query",
            original_query="original query",
            removed_families=[],
            source_types=["paper"],
            round=1,
        )


@pytest.mark.asyncio
async def test_prepare_search_refines_once_and_preserves_audit_fields(fixed_time) -> None:
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

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    gap = EvidenceGap(
        gap_id="mechanism-gap",
        description="glacier calving boundary-condition mechanism",
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="glacier calving simulation",
        scope="physics-informed surrogate",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q-mechanism",
                gap_id=gap.gap_id,
                query=_LONG_QUERY,
                source_types=["paper"],
            )
        ],
        success_criteria=["find relevant mechanism evidence"],
        risks=["boundary observations are sparse"],
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
    assert prepared[0].query_id == "q-mechanism"
    assert prepared[0].query == _REFINED_QUERY
    assert prepared[0].original_query == _LONG_QUERY
    assert prepared[0].refinement_reason is not None
    assert prepared[0].removed_families == []
    assert plan.search_queries[0].query == _LONG_QUERY

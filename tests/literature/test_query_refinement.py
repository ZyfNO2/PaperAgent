from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.literature.query_refinement import refine_search_query
from paperagent.schemas import PreparedQuery

_OVERSTUFFED_QUERY = (
    "drone small object detection failure mechanism limitation parallel method "
    "feature enhancement multi-scale fusion knowledge distillation"
)
_REFINED_QUERY = "drone small object detection failure mechanism limitation"
_MECHANISM_DESCRIPTION = (
    "failure mechanism, limitation, and parallel method evidence for aerial small objects"
)


def test_overconstrained_mechanism_query_is_refined_without_losing_task_terms() -> None:
    result = refine_search_query(
        _OVERSTUFFED_QUERY,
        gap_id="failure_mechanism_parallel",
        gap_description=_MECHANISM_DESCRIPTION,
    )

    assert result.changed is True
    assert result.query == _REFINED_QUERY
    assert set(result.removed_families) == {
        "feature enhancement",
        "multi-scale fusion",
        "knowledge distillation",
    }
    assert result.reason is not None
    for preserved in (
        "drone",
        "small object detection",
        "failure mechanism",
        "limitation",
    ):
        assert preserved in result.query


def test_baseline_query_is_not_refined_even_when_it_lists_method_families() -> None:
    query = "drone detector transformer attention quantization baseline comparison"

    result = refine_search_query(
        query,
        gap_id="baseline_comparison",
        gap_description="reproducible baseline and strong comparison evidence",
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
        gap_description=_MECHANISM_DESCRIPTION,
    )

    assert result.changed is False
    assert result.query == query


@pytest.mark.parametrize(
    "query",
    [
        "drone small object detection knowledge distillation attention",
        "drone small object detection feature enhancement multi-scale fusion",
    ],
)
def test_one_or_two_method_families_are_kept(query: str) -> None:
    result = refine_search_query(
        query,
        gap_id="parallel_method",
        gap_description=_MECHANISM_DESCRIPTION,
    )

    assert result.changed is False
    assert result.query == query


@pytest.mark.parametrize(
    ("query", "gap_id", "description", "expected", "removed_families"),
    [
        (
            "remote sensing dense small object detection benchmark dataset evaluation metrics survey",
            "baseline_comparison",
            "reproducible baseline, dataset, and comparison evidence",
            "remote sensing dense small object detection",
            set(),
        ),
        (
            "remote sensing small object detection failure modes missed detections false positives "
            "boundary ambiguity analysis",
            "failure_mechanism_and_parallel_methods",
            "failure mechanism and parallel method evidence",
            "remote sensing small object detection failure modes",
            set(),
        ),
        (
            "remote sensing small object detection multi-scale feature fusion attention mechanism "
            "super-resolution auxiliary methods",
            "failure_mechanism_and_parallel_methods",
            "failure mechanism and parallel method evidence",
            "remote sensing small object detection mechanism",
            {"multi-scale feature fusion", "attention", "super-resolution"},
        ),
    ],
)
def test_case005_queries_are_compacted_without_losing_domain_and_task(
    query: str,
    gap_id: str,
    description: str,
    expected: str,
    removed_families: set[str],
) -> None:
    result = refine_search_query(
        query,
        gap_id=gap_id,
        gap_description=description,
    )

    assert result.changed is True
    assert result.query == expected
    assert set(result.removed_families) == removed_families
    assert result.reason is not None
    assert "remote sensing" in result.query
    assert "small object detection" in result.query


def test_prepared_query_requires_complete_refinement_audit() -> None:
    with pytest.raises(ValidationError, match="refinement_reason"):
        PreparedQuery(
            query_id="q1",
            gap_id="g1",
            query="refined query",
            original_query="original query",
            removed_families=["attention"],
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
    plan = ResearchPlan(
        status="ready",
        problem_statement="lightweight UAV small object detection",
        scope="aerial visual object detection",
        evidence_gaps=[
            EvidenceGap(
                gap_id="failure_mechanism_parallel",
                description=_MECHANISM_DESCRIPTION,
            )
        ],
        search_queries=[
            SearchQuery(
                query_id="q-mechanism",
                gap_id="failure_mechanism_parallel",
                query=_OVERSTUFFED_QUERY,
                source_types=["paper"],
            )
        ],
        success_criteria=["find relevant mechanism evidence"],
        risks=["overconstrained query"],
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
    assert prepared[0].original_query == _OVERSTUFFED_QUERY
    assert prepared[0].refinement_reason is not None
    assert set(prepared[0].removed_families) == {
        "feature enhancement",
        "multi-scale fusion",
        "knowledge distillation",
    }
    assert plan.search_queries[0].query == _OVERSTUFFED_QUERY

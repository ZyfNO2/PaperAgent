from __future__ import annotations

import pytest


def _plan():
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    return ResearchPlan(
        status="ready",
        problem_statement="p",
        scope="s",
        research_questions=["q"],
        evidence_gaps=[EvidenceGap(gap_id="g1", description="d", minimum_accepted_items=1)],
        search_queries=[
            SearchQuery(query_id="q1", gap_id="g1", query="first", source_types=["web"]),
            SearchQuery(query_id="q2", gap_id="g1", query="second", source_types=["web"]),
        ],
        success_criteria=["c"],
        risks=[],
    )


@pytest.mark.asyncio
async def test_prepare_search_node__budget_one__prepares_one_query_and_increments_round(
    fixed_time,
) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.prepare_search import prepare_search_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, RunBudgets
    from paperagent.state import apply_state_patch
    from paperagent.testing import FixedClock, SequenceIdFactory

    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state,
        await intake_node(
            state,
            {
                "configurable": {
                    "services": services,
                    "budgets": RunBudgets(max_queries_per_round=1),
                }
            },
        ),
    )
    state["plan"] = _plan()
    patch = await prepare_search_node(state, {"configurable": {"services": services}})
    assert patch["retrieval"].round == 1
    assert [query.query_id for query in patch["retrieval"].prepared_queries] == ["q1"]


@pytest.mark.asyncio
async def test_search_and_verify__valid_fixture_candidate__becomes_accepted(fixed_time) -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, SearchFixtureKey
    from paperagent.retrieval.search_tool import search_tool_node
    from paperagent.retrieval.verify_evidence import verify_evidence_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import (
        PreparedQuery,
        RetrievalState,
        RunBudgets,
        RunContext,
        SearchCandidate,
    )
    from paperagent.testing import FixedClock, SequenceIdFactory

    candidate = SearchCandidate(
        candidate_id="c1",
        query_id="q1",
        gap_id="g1",
        source_type="web",
        title="Fixture note",
        locator="fixture://candidate/c1",
        snippet="summary",
    )
    search = FakeSearchProvider(
        fixtures={SearchFixtureKey(scenario="happy_path", query_id="q1", call_index=0): [candidate]}
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    state = {
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=fixed_time,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(),
        ),
        "retrieval": RetrievalState(
            round=1,
            prepared_queries=[
                PreparedQuery(
                    query_id="q1", gap_id="g1", query="search", source_types=["web"], round=1
                )
            ],
        ),
    }
    search_patch = await search_tool_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    state["retrieval"] = search_patch["retrieval"]
    verify_patch = await verify_evidence_node(state, {"configurable": {"services": services}})
    evidence = verify_patch["evidence"]
    assert evidence.accepted_ids == ["ev-c1"]
    assert evidence.coverage_by_gap == {"g1": 1}


def test_retrieval_gate__coverage_and_round__is_bounded() -> None:
    from paperagent.retrieval.gate import retrieval_gate
    from paperagent.schemas import EvidenceBundle, RetrievalState

    assert (
        retrieval_gate(
            {"plan": _plan(), "retrieval": RetrievalState(round=1), "evidence": EvidenceBundle()}
        )
        == "retry_under_budget"
    )
    assert (
        retrieval_gate(
            {"plan": _plan(), "retrieval": RetrievalState(round=2), "evidence": EvidenceBundle()}
        )
        == "budget_exhausted"
    )

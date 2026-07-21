from __future__ import annotations

from copy import deepcopy

import pytest

from conftest import load_llm_raw


def _services(fixed_time, *, scenario="happy_path", failures=None):
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider, FixtureKey
    from paperagent.runtime import RuntimeServices
    from paperagent.testing import FixedClock, SequenceIdFactory

    fixtures = {
        FixtureKey(task="planning", scenario=scenario, call_index=0): load_llm_raw(
            "planning", scenario, 0
        )
    }
    return RuntimeServices(
        llm=FakeLLMProvider(fixtures=fixtures, failures=failures),
        search=FakeSearchProvider(fixtures={}),
        clock=FixedClock(fixed_time),
        ids=SequenceIdFactory(prefix="test"),
        store=InMemoryStateStore(),
    )


@pytest.mark.asyncio
async def test_intake_node__valid_request__initializes_bounded_state(fixed_time) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.schemas import ResearchRequest

    state = {
        "request": ResearchRequest(
            question="  evaluate citations  ", required_constraints=["offline", "offline"]
        )
    }
    before = deepcopy(state)
    services = _services(fixed_time)
    patch = await intake_node(state, {"configurable": {"services": services}})
    assert patch["request"].question == "evaluate citations"
    assert patch["request"].required_constraints == ["offline"]
    assert patch["run"].budgets.max_retrieval_rounds == 2
    assert patch["execution"].status == "running"
    assert state == before
    assert [event.event_type for event in patch["trace"]] == ["node.started", "node.completed"]


@pytest.mark.asyncio
async def test_planning_node__happy_fixture__returns_plan_and_usage_trace(fixed_time) -> None:
    from paperagent.nodes.intake import intake_node
    from paperagent.nodes.planning import planning_node
    from paperagent.schemas import ResearchRequest
    from paperagent.state import apply_state_patch

    services = _services(fixed_time)
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state, await intake_node(state, {"configurable": {"services": services}})
    )
    patch = await planning_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["plan"].status == "ready"
    assert patch["execution"].llm_call_count == 1
    assert any(event.event_type == "llm.responded" for event in patch["trace"])
    assert any(event.prompt_version == "planning.v0.1.3" for event in patch["trace"])


@pytest.mark.asyncio
async def test_planning_node__provider_timeout__returns_typed_failure(fixed_time) -> None:
    from paperagent.errors import ProviderTimeoutError
    from paperagent.nodes.intake import intake_node
    from paperagent.nodes.planning import planning_node
    from paperagent.providers import FixtureKey
    from paperagent.schemas import ResearchRequest
    from paperagent.state import apply_state_patch

    key = FixtureKey(task="planning", scenario="happy_path", call_index=0)
    services = _services(
        fixed_time, failures={key: ProviderTimeoutError(provider="fake_llm", task="planning")}
    )
    state = {"request": ResearchRequest(question="evaluate citations")}
    state = apply_state_patch(
        state, await intake_node(state, {"configurable": {"services": services}})
    )
    patch = await planning_node(
        state, {"configurable": {"services": services, "scenario": "happy_path"}}
    )
    assert patch["execution"].status == "failed"
    assert patch["execution"].last_error.code == "PROVIDER_TIMEOUT"
    assert patch["trace"][-1].event_type == "node.failed"


def test_planning_route__status__maps_to_expected_edge() -> None:
    from paperagent.nodes.planning import planning_route
    from paperagent.schemas import ResearchPlan

    for status in ("ready", "need_human", "blocked"):
        kwargs = {
            "status": status,
            "problem_statement": "p",
            "scope": "s",
            "research_questions": [],
            "evidence_gaps": [],
            "search_queries": [],
            "success_criteria": [],
            "risks": [],
            "clarification_question": "question" if status == "need_human" else None,
            "block_reason": "blocked" if status == "blocked" else None,
        }
        if status == "ready":
            kwargs["research_questions"] = ["q"]
            kwargs["evidence_gaps"] = [{"gap_id": "g", "description": "d"}]
            kwargs["search_queries"] = [{"query_id": "q", "gap_id": "g", "query": "search"}]
        assert planning_route({"plan": ResearchPlan(**kwargs)}, {}) == status


def test_planning_route__headless_policy_blocks_human_interrupt() -> None:
    from paperagent.nodes.planning import planning_route
    from paperagent.schemas import ResearchPlan

    plan = ResearchPlan(
        status="need_human",
        problem_statement="p",
        scope="s",
        clarification_question="Which corpus should be used?",
    )
    assert (
        planning_route({"plan": plan}, {"configurable": {"human_review_policy": "block"}})
        == "blocked"
    )


def test_plan_normalization__oversized_plan__keeps_one_query_per_gap_then_fills() -> None:
    from paperagent.nodes.planning import (
        _BUDGET_NORMALIZATION_RISK,
        _normalize_plan_to_query_budget,
    )
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="bounded retrieval",
        scope="test",
        evidence_gaps=[
            EvidenceGap(gap_id=f"g{index}", description=f"gap {index}") for index in range(1, 7)
        ],
        search_queries=[
            SearchQuery(
                query_id=f"q{index}",
                gap_id=f"g{((index - 1) % 6) + 1}",
                query=f"protein function evidence query {index}",
            )
            for index in range(1, 13)
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert len(normalized.search_queries) == 10
    assert {query.gap_id for query in normalized.search_queries} == {
        "g1",
        "g2",
        "g3",
        "g4",
        "g5",
        "g6",
    }
    assert _BUDGET_NORMALIZATION_RISK in normalized.risks
    normalized.validate_query_budget(10)


def test_plan_normalization__repository_or_dataset_query__adds_web_lane() -> None:
    from paperagent.nodes.planning import _normalize_plan_to_query_budget
    from paperagent.schemas import EvidenceGap, ResearchPlan, SearchQuery

    plan = ResearchPlan(
        status="ready",
        problem_statement="asset discovery",
        scope="test",
        evidence_gaps=[EvidenceGap(gap_id="g1", description="find implementation")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="g1",
                query="GraphSAGE official implementation repository",
                source_types=["paper", "repository"],
            )
        ],
    )

    normalized = _normalize_plan_to_query_budget(plan, query_budget=10)

    assert normalized.search_queries[0].source_types == ["paper", "repository", "web"]

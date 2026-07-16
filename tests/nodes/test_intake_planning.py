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
    assert any(event.prompt_version == "planning.v0.1.0" for event in patch["trace"])


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
        assert planning_route({"plan": ResearchPlan(**kwargs)}) == status

from __future__ import annotations

import pytest

from conftest import load_llm_raw


@pytest.mark.asyncio
async def test_graph__planning_interrupt__resumes_without_repeating_intake(fixed_time) -> None:
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command

    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, SearchCandidate
    from paperagent.testing import FixedClock, SequenceIdFactory

    fixtures = {
        FixtureKey(task="planning", scenario="need_human", call_index=0): load_llm_raw(
            "planning", "need_human", 0
        ),
        FixtureKey(task="planning", scenario="need_human", call_index=1): load_llm_raw(
            "planning", "need_human", 1
        ),
        FixtureKey(task="evidence_synthesis", scenario="happy_path", call_index=0): load_llm_raw(
            "evidence_synthesis", "happy_path", 0
        ),
        FixtureKey(task="method_design", scenario="happy_path", call_index=0): load_llm_raw(
            "method_design", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
    }
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(scenario="happy_path", query_id="query-support-01", call_index=0): [
                SearchCandidate(
                    candidate_id="support-001",
                    query_id="query-support-01",
                    gap_id="gap-support",
                    source_type="user_material",
                    title="Synthetic support note",
                    locator="fixture://support",
                    snippet="support",
                    metadata={"license": "MIT"},
                )
            ],
            SearchFixtureKey(scenario="happy_path", query_id="query-ablation-01", call_index=0): [
                SearchCandidate(
                    candidate_id="ablation-001",
                    query_id="query-ablation-01",
                    gap_id="gap-ablation",
                    source_type="user_material",
                    title="Synthetic ablation note",
                    locator="fixture://ablation",
                    snippet="ablation",
                    metadata={"license": "MIT"},
                )
            ],
        }
    )
    services = RuntimeServices(
        FakeLLMProvider(fixtures=fixtures),
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("hitl"),
        InMemoryStateStore(),
    )
    graph = build_graph(checkpointer=InMemorySaver())
    config = {
        "configurable": {
            "thread_id": "hitl-thread-1",
            "services": services,
            "scenarios": {
                "planning": "need_human",
                "evidence_synthesis": "happy_path",
                "method_design": "happy_path",
                "report": "happy_path",
            },
            "search_scenario": "happy_path",
        }
    }
    paused = await graph.ainvoke({"request": ResearchRequest(question="Study this method")}, config)
    assert paused["__interrupt__"]
    resumed = await graph.ainvoke(Command(resume="Evaluate citation evidence"), config)
    assert resumed["execution"].status == "completed"
    assert resumed["request"].clarification_answer == "Evaluate citation evidence"
    intake_completions = [
        event
        for event in resumed["trace"]
        if event.node == "intake_node" and event.event_type == "node.completed"
    ]
    assert len(intake_completions) == 1

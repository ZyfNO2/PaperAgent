from __future__ import annotations

import pytest

from conftest import load_llm_raw


@pytest.mark.asyncio
async def test_graph__empty_search__stops_after_two_rounds_and_revises(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest
    from paperagent.testing import FixedClock, SequenceIdFactory

    llm = FakeLLMProvider(
        fixtures={
            FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
                "planning", "happy_path", 0
            ),
            FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
                "report", "blocked", 0
            ),
        }
    )
    search_fixtures = {}
    for query_id in ("query-support-01", "query-ablation-01"):
        search_fixtures[SearchFixtureKey(scenario="empty", query_id=query_id, call_index=0)] = []
    search = FakeSearchProvider(fixtures=search_fixtures)
    services = RuntimeServices(
        llm, search, FixedClock(fixed_time), SequenceIdFactory("empty"), InMemoryStateStore()
    )
    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenarios": {
                    "planning": "happy_path",
                    "report": "blocked",
                },
                "search_scenario": "empty",
            }
        },
    )
    assert result["execution"].status == "completed"
    assert result["retrieval"].round == 2
    assert result["retrieval"].budget_exhausted is True
    assert len(search.calls) == 2
    assert "Q_RETRIEVAL_BUDGET_EXHAUSTED" in result["quality"].reason_codes
    assert result["final_outcome"].scientific_verdict == "REVISE"
    assert result["report"].status == "completed"
    assert result["report"].next_actions
    assert result.get("synthesis") is None
    assert result.get("method") is None

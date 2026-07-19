from __future__ import annotations

import pytest

from conftest import load_llm_raw


@pytest.mark.asyncio
@pytest.mark.e2e
async def test_exhausted_missing_evidence_stops_before_synthesis(fixed_time) -> None:
    from paperagent.graph import build_graph
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import (
        FakeLLMProvider,
        FakeSearchProvider,
        FixtureKey,
        SearchFixtureKey,
    )
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import ResearchRequest, RunBudgets
    from paperagent.testing import FixedClock, SequenceIdFactory

    llm = FakeLLMProvider(
        fixtures={
            FixtureKey(task="planning", scenario="no_evidence", call_index=0): load_llm_raw(
                "planning", "happy_path", 0
            ),
            FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
                "report", "blocked", 0
            ),
        }
    )
    search = FakeSearchProvider(
        fixtures={
            SearchFixtureKey(
                scenario="no_evidence",
                query_id="query-support-01",
                call_index=0,
            ): [],
            SearchFixtureKey(
                scenario="no_evidence",
                query_id="query-ablation-01",
                call_index=0,
            ): [],
        }
    )
    services = RuntimeServices(
        llm,
        search,
        FixedClock(fixed_time),
        SequenceIdFactory("evidence-gate"),
        InMemoryStateStore(),
    )

    result = await build_graph().ainvoke(
        {"request": ResearchRequest(question="Evaluate citation reliability")},
        {
            "configurable": {
                "services": services,
                "scenarios": {
                    "planning": "no_evidence",
                    "report": "blocked",
                },
                "search_scenario": "no_evidence",
                "budgets": RunBudgets(max_retrieval_rounds=1),
            }
        },
    )

    assert result["final_outcome"].scientific_verdict == "REVISE"
    assert result["final_outcome"].execution_status == "succeeded"
    assert result["final_outcome"].missing_gap_ids == [
        "gap-support",
        "gap-ablation",
    ]
    assert result["report"].status == "completed"
    assert result["report"].next_actions
    assert result["trace_audit"].passed is True
    assert result.get("synthesis") is None
    assert result.get("method") is None
    assert [call.key.task for call in llm.calls] == ["planning", "report"]
    assert any(
        event.node == "evidence_quality_gate_node"
        and event.event_type == "route.decided"
        and event.route == "blocked"
        for event in result["trace"]
    )

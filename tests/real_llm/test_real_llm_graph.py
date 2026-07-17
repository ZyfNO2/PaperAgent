"""Real-LLM full-graph test: drives ``build_graph()`` with a real LLM provider.

Strategy: a real LLM produces the planning output (and downstream nodes), while a
``FakeSearchProvider`` with empty fixtures forces every search query to raise
``FixtureNotFoundError``. ``search_tool_node`` records those as tool errors and
produces no candidates, so after the retrieval budget is exhausted the quality
gate routes to ``blocked`` and the graph reaches ``report_node`` then
``persist_node`` with bounded termination.

We do NOT assert a specific report status: the real LLM's report status is
non-deterministic. We assert that the graph terminates cleanly (within a 180s
budget) and produces a non-null report. Skipped unless
``PAPERAGENT_RUN_REAL_LLM=1`` and ``PAPERAGENT_OPENAI_API_KEY`` are set.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import pytest

from paperagent.graph import build_graph
from paperagent.persistence import InMemoryStateStore
from paperagent.providers import FakeSearchProvider
from paperagent.runtime import RuntimeServices
from paperagent.schemas import ResearchRequest
from paperagent.testing import FixedClock, SequenceIdFactory
from datetime import UTC, datetime

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(
        os.getenv("PAPERAGENT_RUN_REAL_LLM") != "1" or not os.getenv("PAPERAGENT_OPENAI_API_KEY"),
        reason="set PAPERAGENT_RUN_REAL_LLM=1 and PAPERAGENT_OPENAI_API_KEY",
    ),
]

_GRAPH_TIMEOUT_SECONDS = 180.0


@pytest.mark.asyncio
async def test_real_llm_graph__bounded_termination_with_empty_search(
    real_llm_provider,
) -> None:
    services = RuntimeServices(
        llm=real_llm_provider,
        # Empty fixtures: every search raises FixtureNotFoundError, which
        # search_tool_node records as a tool error without halting the graph.
        search=FakeSearchProvider(fixtures={}),
        clock=FixedClock(datetime(2026, 1, 1, tzinfo=UTC)),
        ids=SequenceIdFactory("real-llm-graph"),
        store=InMemoryStateStore(),
    )
    graph = build_graph()
    configurable = {"services": services, "scenario": "happy_path"}

    result = await asyncio.wait_for(
        graph.ainvoke(
            {"request": ResearchRequest(question="Evaluate citation reliability")},
            {"configurable": configurable},
        ),
        timeout=_GRAPH_TIMEOUT_SECONDS,
    )

    assert result is not None
    execution = result.get("execution")
    trace = result.get("trace", [])

    # TraceEvent may be a Pydantic model or a dict depending on whether the
    # graph was invoked directly (model) or through the HTTP contract (dict).
    def _event_node(e: Any) -> str:
        return getattr(e, "node", None) or e.get("node")

    def _event_type(e: Any) -> str:
        return getattr(e, "event_type", None) or e.get("event_type")

    # Diagnostic: surface the last few trace events on failure so we can see
    # where the graph actually stopped.
    last_events = [
        {"node": _event_node(e), "event_type": _event_type(e)}
        for e in trace[-5:]
    ]

    # Bounded termination contract: the graph must terminate within the timeout
    # without raising. Three legitimate outcomes:
    #   (a) plan.status=ready/blocked/unknown -> planning_route routes to
    #       report_node -> persist_node (defensive fallback ensures this).
    #   (b) plan.status=need_human -> graph routes to human_review_node which
    #       calls LangGraph interrupt() BEFORE emitting any trace event, so the
    #       graph suspends immediately after planning_node. This is a designed
    #       pause point requiring a checkpointer to resume; without one, the
    #       graph simply stops after planning.
    plan_status = getattr(result.get("plan"), "status", None)
    persist_completed = any(
        _event_node(e) == "persist_node" and _event_type(e) == "node.completed"
        for e in trace
    )
    planning_completed = any(
        _event_node(e) == "planning_node" and _event_type(e) == "node.completed"
        for e in trace
    )

    if plan_status == "need_human":
        # interrupt() pauses before human_review_node emits any trace event, so
        # we only assert that planning completed and the graph did not crash.
        assert planning_completed, (
            f"plan.status=need_human but planning_node did not complete; "
            f"last events: {last_events}"
        )
    else:
        # For ready/blocked/unknown statuses, planning_route's defensive
        # fallback ensures the graph reaches persist_node.
        assert persist_completed, (
            f"graph did not reach persist_node; last events: {last_events}; "
            f"plan_status={plan_status}; "
            f"execution_status={getattr(execution, 'status', None)}; "
            f"last_error={getattr(execution, 'last_error', None)}"
        )
        assert execution is not None, "graph terminated without execution metadata"
        # execution may be an ExecutionMeta Pydantic model (direct graph.ainvoke)
        # or a dict (HTTP contract). Use getattr to handle both shapes.
        status = getattr(execution, "status", None) or (
            execution.get("status") if isinstance(execution, dict) else None
        )
        assert status in ("completed", "blocked"), f"unexpected terminal status: {status}"

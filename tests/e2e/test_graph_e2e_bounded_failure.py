"""E2E: bounded retrieval exhaustion through the HTTP task contract.

When every search round returns empty, the retrieval subgraph must exhaust its
budget, the pre-synthesis evidence gate must produce a scientific ``REVISE``,
and the durable task must finish ``succeeded`` with a completed repair report.
This is the critical safety property: the graph never loops forever or invents
an evaluated method when required evidence is unavailable.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from helpers import (
    FixtureKey,
    SearchFixtureKey,
    assert_completed_nodes,
    build_services,
    load_llm_raw,
)

EXPECTED_BOUNDED_NODES = [
    "intake_node",
    "planning_node",
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "report_node",
    "persist_node",
]


def _empty_search_services() -> Any:
    llm_fixtures = {
        FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
            "planning", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    # Empty result lists for every query the happy_path plan emits. Returning []
    # (not omitting the key) avoids FixtureNotFoundError while still starving
    # coverage so the evidence gate must terminate before synthesis.
    search_fixtures = {
        SearchFixtureKey(scenario="empty", query_id="query-support-01", call_index=0): [],
        SearchFixtureKey(scenario="empty", query_id="query-ablation-01", call_index=0): [],
    }
    return build_services(
        llm_fixtures=llm_fixtures,
        search_fixtures=search_fixtures,
        prefix="bounded",
    )


def test_e2e__empty_retrieval__exhausts_budget_and_revises_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(
        services=_empty_search_services(),
        configurable={
            "scenarios": {
                "planning": "happy_path",
                "report": "blocked",
            },
            "search_scenario": "empty",
        },
    )
    with client:
        task_id = submit_task(client, key="bounded-failure-e2e")
        task = wait_for_terminal(client, task_id, timeout=20.0)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "completed"
        assert result["retrieval"]["round"] == 2
        assert result["retrieval"]["budget_exhausted"] is True
        assert result["quality"]["verdict"] == "blocked"
        assert "Q_RETRIEVAL_BUDGET_EXHAUSTED" in result["quality"]["reason_codes"]
        assert result["final_outcome"]["scientific_verdict"] == "REVISE"
        assert result["report"]["status"] == "completed"
        assert result["report"]["next_actions"]
        assert result.get("synthesis") is None
        assert result.get("method") is None

        assert_completed_nodes(result, EXPECTED_BOUNDED_NODES)

        # Two rounds x two queries per round = four search calls total.
        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=200").json()
        progress = [
            event["payload"]
            for event in page["events"]
            if event["event_type"] == "workflow.progress"
        ]
        assert progress, "expected workflow.progress events from the graph stream"

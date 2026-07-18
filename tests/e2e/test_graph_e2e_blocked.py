"""E2E: planning ``blocked`` route through the HTTP task contract.

When planning returns ``blocked`` the graph must skip retrieval/synthesis/method
and go straight to a blocked report. The durable task layer must still mark the
task ``succeeded`` (the workflow completed with a blocked *report*, not a task
failure) and expose the blocked report in the result.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from helpers import FixtureKey, assert_completed_nodes, build_services, load_llm_raw

EXPECTED_BLOCKED_NODES = [
    "intake_node",
    "planning_node",
    "report_node",
    "persist_node",
]


def _blocked_services() -> Any:
    fixtures = {
        FixtureKey(task="planning", scenario="blocked", call_index=0): load_llm_raw(
            "planning", "blocked", 0
        ),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    return build_services(
        llm_fixtures=fixtures,
        search_fixtures={},
        prefix="blocked",
    )


def test_e2e__planning_blocked__routes_to_blocked_report_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(
        services=_blocked_services(),
        configurable={"scenarios": {"planning": "blocked", "report": "blocked"}},
    )
    with client:
        task_id = submit_task(client, question="Prove a result without evidence", key="blocked-e2e")
        task = wait_for_terminal(client, task_id)

        # Blocked report is still a completed task (workflow finished normally).
        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "blocked"
        assert result["plan"]["status"] == "blocked"
        assert result["plan"]["block_reason"] is not None
        assert result["report"]["status"] == "blocked"
        # PaperAgentState is TypedDict(total=False): unset None fields are not
        # serialized into the result primitive, so .get() must be used here.
        assert result.get("quality") is None
        assert result.get("synthesis") is None
        assert result.get("method") is None

        assert_completed_nodes(result, EXPECTED_BLOCKED_NODES)

        # No retrieval should have run for a blocked plan.
        assert result["retrieval"]["round"] == 0

        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=100").json()
        assert page["terminal"] is True
        assert page["events"][-1]["event_type"] == "task.succeeded"

"""E2E: malformed LLM JSON through the HTTP task contract.

When the LLM returns invalid JSON, the node must not fall back or retry silently;
it must record ``LLM_RESPONSE_JSON_INVALID`` and route to a blocked report. This
is the no-fallback guarantee from the v0.1 fixture contract, verified here
through the full HTTP task pipeline rather than only at the graph level.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from helpers import FixtureKey, assert_completed_nodes, build_services, load_llm_raw

EXPECTED_MALFORMED_NODES = [
    "intake_node",
    # planning_node emits node.failed (not node.completed) when the LLM returns
    # invalid JSON, so it must NOT appear in the completed-node sequence.
    "report_node",
    "persist_node",
]


def _malformed_services() -> Any:
    fixtures = {
        FixtureKey(task="planning", scenario="malformed", call_index=0): '{"status":',
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    return build_services(
        llm_fixtures=fixtures,
        search_fixtures={},
        prefix="malformed",
    )


def test_e2e__malformed_planning_json__does_not_fallback_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(
        services=_malformed_services(),
        configurable={"scenarios": {"planning": "malformed", "report": "blocked"}},
    )
    with client:
        task_id = submit_task(client, key="malformed-e2e")
        task = wait_for_terminal(client, task_id)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "blocked"
        assert result["execution"]["last_error"]["code"] == "LLM_RESPONSE_JSON_INVALID"
        assert result["execution"]["last_error"]["retryable"] is False
        assert result["report"]["status"] == "blocked"
        assert result.get("plan") is None

        assert_completed_nodes(result, EXPECTED_MALFORMED_NODES)

        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=100").json()
        assert page["terminal"] is True
        assert page["events"][-1]["event_type"] == "task.succeeded"

"""E2E: planning provider timeout through the HTTP task contract.

When the LLM provider times out during planning, the node must record a typed
``PROVIDER_TIMEOUT`` error, route to a blocked report, and the durable task must
finish ``succeeded`` with the blocked report. This proves the timeout contract
is honoured end-to-end, not only at the graph level.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from helpers import FixtureKey, assert_completed_nodes, build_services, load_llm_raw

from paperagent.runtime import RuntimeServices

EXPECTED_TIMEOUT_NODES = [
    "intake_node",
    # planning_node emits node.failed (not node.completed) when the LLM provider
    # times out, so it must NOT appear in the completed-node sequence.
    "report_node",
    "persist_node",
]


def _timeout_services() -> RuntimeServices:
    from paperagent.errors import ProviderTimeoutError

    planning_key = FixtureKey(task="planning", scenario="timeout", call_index=0)
    fixtures = {
        planning_key: load_llm_raw("planning", "happy_path", 0),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }
    failures = {planning_key: ProviderTimeoutError(provider="fake_llm", task="planning")}
    return build_services(
        llm_fixtures=fixtures,
        llm_failures=failures,
        search_fixtures={},
        prefix="timeout",
    )


def test_e2e__planning_timeout__produces_typed_blocked_report_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    services = _timeout_services()
    client: TestClient = graph_app_factory(
        services=services,
        configurable={"scenarios": {"planning": "timeout", "report": "blocked"}},
    )
    with client:
        task_id = submit_task(client, key="timeout-e2e")
        task = wait_for_terminal(client, task_id)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "blocked"
        assert result["execution"]["last_error"]["code"] == "PROVIDER_TIMEOUT"
        assert result["execution"]["last_error"]["retryable"] is True
        assert result["report"]["status"] == "blocked"
        assert result.get("plan") is None

        assert_completed_nodes(result, EXPECTED_TIMEOUT_NODES)

        # The llm.failed trace event must surface through the result trace.
        failed_events = [
            event
            for event in result.get("trace", [])
            if event.get("event_type") == "llm.failed"
        ]
        assert failed_events, "expected at least one llm.failed trace event"
        assert any(event.get("error_code") == "PROVIDER_TIMEOUT" for event in failed_events)

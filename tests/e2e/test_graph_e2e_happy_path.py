"""E2E: happy path through the real LangGraph behind the HTTP task contract.

Verifies the full pipeline that the deterministic ``DemoTaskExecutor`` bypasses:
``/v1/tasks`` submit -> ``SingleProcessTaskRunner`` claim ->
``LangGraphTaskExecutor`` streaming ``build_graph()`` -> SSE progress events ->
terminal ``succeeded`` -> full ``PaperAgentState`` primitive in the result.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from helpers import assert_completed_nodes

EXPECTED_HAPPY_NODES = [
    "intake_node",
    "readiness_preflight_node",
    "planning_node",
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "evidence_synthesis_node",
    "method_design_node",
    "methodology_audit_node",
    "quality_gate_node",
    "report_node",
    "persist_node",
]


def test_e2e__happy_path__real_graph_reaches_succeeded_with_full_state(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory()
    with client:
        task_id = submit_task(client, key="happy-path-e2e")
        task = wait_for_terminal(client, task_id)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        # Real graph emits the full PaperAgentState primitive, not the demo shape.
        assert result["execution"]["status"] == "completed"
        assert result["execution"]["current_node"] == "persist_node"
        assert result["plan"]["status"] == "ready"
        assert result["quality"]["verdict"] == "pass"
        assert result["report"]["status"] == "completed"
        assert result["retrieval"]["round"] == 1
        assert result["run"]["network_policy"] == "offline"

        # Evidence bundle should carry the two accepted synthetic items. The
        # FakeSearch fixtures only return accepted candidates, so rejected_ids
        # stays empty here — that is the expected shape for this scenario.
        accepted_ids = result["evidence"]["accepted_ids"]
        assert accepted_ids == ["ev-support-001", "ev-ablation-001"]
        assert result["evidence"]["coverage_by_gap"] == {"gap-support": 1, "gap-ablation": 1}

        assert_completed_nodes(result, EXPECTED_HAPPY_NODES)

        # The runner must emit durable events observable through the events API.
        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=500").json()
        assert page["terminal"] is True
        event_types = [event["event_type"] for event in page["events"]]
        assert event_types[0] == "task.queued"
        assert "task.started" in event_types
        assert "workflow.progress" in event_types
        assert event_types[-1] == "task.succeeded"

        # Progress events should reflect graph node boundaries, not demo phases.
        progress_payloads = [
            event["payload"]
            for event in page["events"]
            if event["event_type"] == "workflow.progress"
        ]
        assert progress_payloads, "expected at least one workflow.progress event"
        assert all("execution_status" in payload for payload in progress_payloads)
        assert all("report_status" in payload for payload in progress_payloads)
        assert any(payload.get("report_status") == "completed" for payload in progress_payloads)


def test_e2e__happy_path__sse_stream_replays_full_event_history(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory()
    with client:
        task_id = submit_task(client, key="happy-path-sse")
        wait_for_terminal(client, task_id)

        stream = client.get(f"/v1/tasks/{task_id}/events/stream?after=0")
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "event: task.queued" in stream.text
        assert "event: task.started" in stream.text
        assert "event: workflow.progress" in stream.text
        assert "event: task.succeeded" in stream.text


def test_e2e__happy_path__idempotent_replay_returns_same_task(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory()
    with client:
        first = submit_task(client, key="idempotent-replay")
        wait_for_terminal(client, first)

        replay = client.post(
            "/v1/tasks",
            json={"request": {"question": "Evaluate citation reliability for a small RAG system"}},
            headers={"Idempotency-Key": "idempotent-replay"},
        )
        assert replay.status_code == 202
        assert replay.json()["task_id"] == first
        assert replay.json()["reused"] is True

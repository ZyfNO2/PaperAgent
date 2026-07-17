"""E2E: task cancellation contract through the HTTP API.

Covers two branches of ``POST /v1/tasks/{task_id}/cancel``:

1. Cancelling a task that is still in-flight (QUEUED or RUNNING). The runner
   keeps the event loop alive between TestClient requests, so the task may
   already be RUNNING by the time cancel arrives — in that case the repository
   transitions it to ``cancel_requested`` (accepted=True) and the runner
   observes ``cancel_requested`` at the next graph boundary, then marks the
   task ``cancelled``. Either way the terminal state must be ``cancelled``.

2. Cancelling a task that has already reached a terminal state (succeeded) must
   be rejected with ``accepted=False`` and must not mutate the task.

Note: the exact intermediate status (cancel_requested vs cancelled) depends on
whether the runner has claimed the task before the cancel request arrives; the
terminal state is what matters and is asserted after wait_for_terminal.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from helpers import build_services


def test_e2e__cancel_inflight_task__reaches_cancelled_terminal(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(services=build_services(prefix="cancel_inflight"))
    with client:
        task_id = submit_task(client, key="cancel-inflight-e2e")

        # Cancel immediately. The task may still be QUEUED (direct CANCELLED) or
        # already RUNNING (CANCEL_REQUESTED -> runner marks CANCELLED at the next
        # graph boundary). Either way accepted must be True.
        cancel_response = client.post(f"/v1/tasks/{task_id}/cancel")
        assert cancel_response.status_code == 200, cancel_response.text
        cancel_body = cancel_response.json()
        assert cancel_body["accepted"] is True
        assert cancel_body["status"] in ("cancel_requested", "cancelled")

        task = wait_for_terminal(client, task_id, timeout=15.0)
        assert task["status"] == "cancelled"
        assert task["cancel_requested"] is True
        # No result should be attached to a cancelled task.
        assert task.get("result") is None

        # The events API must surface a task.cancelled event as the terminal event.
        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=100").json()
        assert page["terminal"] is True
        assert page["events"][-1]["event_type"] == "task.cancelled"


def test_e2e__cancel_terminal_task__rejected_without_mutation(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(services=build_services(prefix="cancel_terminal"))
    with client:
        task_id = submit_task(client, key="cancel-terminal-e2e")
        task = wait_for_terminal(client, task_id)
        assert task["status"] == "succeeded"
        original_result: dict[str, Any] = task["result"]

        cancel_response = client.post(f"/v1/tasks/{task_id}/cancel")
        assert cancel_response.status_code == 200, cancel_response.text
        cancel_body = cancel_response.json()
        assert cancel_body["accepted"] is False
        assert cancel_body["status"] == "succeeded"

        # The task must not have been mutated by the rejected cancel.
        after = client.get(f"/v1/tasks/{task_id}").json()
        assert after["status"] == "succeeded"
        assert after["result"] == original_result
        assert after["cancel_requested"] is False

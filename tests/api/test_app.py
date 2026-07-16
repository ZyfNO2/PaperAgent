from __future__ import annotations

import asyncio
import threading
import time

from fastapi.testclient import TestClient

from paperagent.api import SQLiteTaskRepository, create_app
from paperagent.api.models import TaskStatus


class ImmediateExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute(self, *, task_id, request, emit, should_cancel):
        self.calls.append(task_id)
        await emit("workflow.progress", {"question": request.question})
        assert should_cancel() is False
        return {"report": {"status": "completed", "question": request.question}}


class BlockingExecutor:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.started = threading.Event()
        self.release = threading.Event()

    async def execute(self, *, task_id, request, emit, should_cancel):
        del request
        self.calls.append(task_id)
        self.started.set()
        await emit("workflow.progress", {"phase": "blocked"})
        await asyncio.to_thread(self.release.wait)
        if should_cancel():
            from paperagent.api.executor import TaskCancelledError

            raise TaskCancelledError("cancelled")
        return {"ok": True}


def _body(question: str = "Evaluate retrieval reliability") -> dict:
    return {"request": {"question": question}, "metadata": {"client": "test"}}


def _wait_for_terminal(client: TestClient, task_id: str) -> dict:
    for _ in range(200):
        payload = client.get(f"/v1/tasks/{task_id}").json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError("task did not reach terminal state")


def test_api__health_submit_poll_events_and_sse_share_state(tmp_path) -> None:
    executor = ImmediateExecutor()
    app = create_app(executor=executor, database_path=tmp_path / "tasks.db", sse_poll_seconds=0.01)

    with TestClient(app) as client:
        assert client.get("/healthz").json() == {"status": "ok", "api_contract": "v0.3"}
        accepted = client.post(
            "/v1/tasks", json=_body(), headers={"Idempotency-Key": "request-1"}
        )
        assert accepted.status_code == 202
        accepted_payload = accepted.json()
        assert accepted_payload["reused"] is False
        task_id = accepted_payload["task_id"]

        task = _wait_for_terminal(client, task_id)
        assert task["status"] == "succeeded"
        assert task["result"]["report"]["question"] == "Evaluate retrieval reliability"
        assert task["event_cursor"] >= 4

        page = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=100").json()
        assert page["terminal"] is True
        assert page["next_cursor"] == task["event_cursor"]
        assert [event["event_type"] for event in page["events"]] == [
            "task.queued",
            "task.started",
            "workflow.progress",
            "task.succeeded",
        ]

        stream = client.get(f"/v1/tasks/{task_id}/events/stream?after=0")
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        assert "event: task.queued" in stream.text
        assert "event: task.succeeded" in stream.text
        assert f'id: {task["event_cursor"]}' in stream.text

    assert executor.calls == [task_id]


def test_api__idempotency_replay_and_conflict(tmp_path) -> None:
    executor = ImmediateExecutor()
    app = create_app(executor=executor, database_path=tmp_path / "tasks.db")

    with TestClient(app) as client:
        first = client.post(
            "/v1/tasks", json=_body(), headers={"Idempotency-Key": "same-key"}
        )
        replay = client.post(
            "/v1/tasks", json=_body(), headers={"Idempotency-Key": "same-key"}
        )
        conflict = client.post(
            "/v1/tasks",
            json=_body("A different research question"),
            headers={"Idempotency-Key": "same-key"},
        )
        missing = client.post("/v1/tasks", json=_body())
        invalid = client.post(
            "/v1/tasks", json=_body(), headers={"Idempotency-Key": "contains spaces"}
        )

        assert first.status_code == replay.status_code == 202
        assert replay.json()["reused"] is True
        assert replay.json()["task_id"] == first.json()["task_id"]
        assert conflict.status_code == 409
        assert missing.status_code == invalid.status_code == 422


def test_api__queued_cancel_prevents_executor_call(tmp_path) -> None:
    executor = BlockingExecutor()
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    app = create_app(executor=executor, repository=repository, sse_poll_seconds=0.01)

    with TestClient(app) as client:
        first = client.post(
            "/v1/tasks", json=_body("First research task"), headers={"Idempotency-Key": "one"}
        ).json()["task_id"]
        assert executor.started.wait(timeout=1)
        second = client.post(
            "/v1/tasks", json=_body("Second research task"), headers={"Idempotency-Key": "two"}
        ).json()["task_id"]

        cancelled = client.post(f"/v1/tasks/{second}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json() == {
            "task_id": second,
            "status": "cancelled",
            "accepted": True,
        }
        repeated = client.post(f"/v1/tasks/{second}/cancel").json()
        assert repeated["accepted"] is False

        executor.release.set()
        assert _wait_for_terminal(client, first)["status"] == "succeeded"
        assert _wait_for_terminal(client, second)["status"] == "cancelled"

    assert executor.calls == [first]


def test_api__missing_task_paths_and_empty_event_page(tmp_path) -> None:
    executor = ImmediateExecutor()
    repository = SQLiteTaskRepository(tmp_path / "tasks.db")
    app = create_app(executor=executor, repository=repository)

    with TestClient(app) as client:
        assert client.get("/v1/tasks/missing").status_code == 404
        assert client.get("/v1/tasks/missing/events").status_code == 404
        assert client.get("/v1/tasks/missing/events/stream").status_code == 404
        assert client.post("/v1/tasks/missing/cancel").status_code == 404

        repository.create_task(
            task_id="manual-task",
            idempotency_key="manual",
            payload=__import__(
                "paperagent.api.models", fromlist=["TaskCreateRequest"]
            ).TaskCreateRequest.model_validate(_body()),
        )
        page = client.get("/v1/tasks/manual-task/events?after=1").json()
        assert page == {
            "task_id": "manual-task",
            "events": [],
            "next_cursor": 1,
            "terminal": False,
        }
        assert client.get("/v1/tasks/manual-task/events?after=-1").status_code == 422
        assert client.get("/v1/tasks/manual-task/events?limit=501").status_code == 422


def test_task_status_enum_contract() -> None:
    assert TaskStatus.QUEUED.value == "queued"

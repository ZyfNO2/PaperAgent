from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from paperagent.api import (
    SQLiteReviewRepository,
    SQLiteTaskRepository,
    TaskCreateRequest,
    create_app,
)
from paperagent.demo import DemoTaskExecutor
from paperagent.schemas.request import ResearchRequest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wait_for_terminal(client: TestClient, task_id: str) -> dict[str, Any]:
    for _ in range(300):
        response = client.get(f"/v1/tasks/{task_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in {"succeeded", "failed", "cancelled"}:
            return payload
        time.sleep(0.01)
    raise AssertionError(f"task {task_id} did not reach a terminal state")


def _consistent_backup(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        destination.unlink()
    with (
        sqlite3.connect(source) as source_connection,
        sqlite3.connect(destination) as destination_connection,
    ):
        source_connection.backup(destination_connection)


def run_local_state_roundtrip(workdir: Path) -> dict[str, Any]:
    workdir.mkdir(parents=True, exist_ok=True)
    live_database = workdir / "paperagent-local.db"
    backup_database = workdir / "paperagent-local.backup.db"
    restored_database = workdir / "paperagent-local.restored.db"
    for path in (live_database, backup_database, restored_database):
        if path.exists():
            path.unlink()

    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=live_database,
        sse_poll_seconds=0.01,
    )
    with TestClient(app) as client:
        accepted = client.post(
            "/v1/tasks",
            headers={"Idempotency-Key": "local-state-roundtrip"},
            json={
                "request": {
                    "question": "Verify local backup, restore, and restart recovery"
                }
            },
        )
        accepted.raise_for_status()
        task_id = accepted.json()["task_id"]
        task = _wait_for_terminal(client, task_id)
        if task["status"] != "succeeded":
            raise AssertionError(task)

        review = client.put(
            f"/v1/tasks/{task_id}/papers/demo-attention-2017/review",
            json={"decision": "accepted", "favorite": True, "expected_version": 0},
        )
        review.raise_for_status()

        export = client.get(f"/v1/tasks/{task_id}/exports/json?selection=all")
        export.raise_for_status()
        export_digest = export.headers["X-PaperAgent-SHA256"]
        if export_digest != hashlib.sha256(export.content).hexdigest():
            raise AssertionError("export digest header does not match content")

        diagnostics = client.get("/v1/diagnostics/runtime")
        diagnostics.raise_for_status()
        live_snapshot = diagnostics.json()

    _consistent_backup(live_database, backup_database)
    backup_digest = _sha256(backup_database)
    shutil.copy2(backup_database, restored_database)

    restored_app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=restored_database,
        sse_poll_seconds=0.01,
    )
    with TestClient(restored_app) as client:
        restored_task = client.get(f"/v1/tasks/{task_id}")
        restored_task.raise_for_status()
        if restored_task.json()["status"] != "succeeded":
            raise AssertionError(restored_task.json())

        cards = client.get(f"/v1/tasks/{task_id}/papers?limit=100")
        cards.raise_for_status()
        card_by_id = {item["paper_id"]: item for item in cards.json()["items"]}
        restored_review = card_by_id["demo-attention-2017"]
        if restored_review["decision"] != "accepted" or not restored_review["favorite"]:
            raise AssertionError(restored_review)

        restored_export = client.get(
            f"/v1/tasks/{task_id}/exports/json?selection=all"
        )
        restored_export.raise_for_status()
        restored_export_digest = restored_export.headers["X-PaperAgent-SHA256"]
        if restored_export_digest != export_digest:
            raise AssertionError("restored export digest differs from the live database export")

        restored_diagnostics = client.get("/v1/diagnostics/runtime")
        restored_diagnostics.raise_for_status()
        restored_snapshot = restored_diagnostics.json()

    repository = SQLiteTaskRepository(live_database)
    SQLiteReviewRepository(repository)
    restart_task_id = "task-local-restart-recovery"
    repository.create_task(
        task_id=restart_task_id,
        idempotency_key="local-restart-recovery",
        payload=TaskCreateRequest(
            request=ResearchRequest(question="Fail an in-flight task closed after restart")
        ),
    )
    claimed = repository.claim_next_task()
    if claimed is None or claimed.status.value != "running":
        raise AssertionError("restart fixture was not claimed as running")

    recovery_app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=live_database,
        sse_poll_seconds=0.01,
    )
    with TestClient(recovery_app) as client:
        recovered = client.get(f"/v1/tasks/{restart_task_id}")
        recovered.raise_for_status()
        recovered_payload = recovered.json()
        if recovered_payload["status"] != "failed":
            raise AssertionError(recovered_payload)
        if recovered_payload["error"]["code"] != "PROCESS_RESTARTED":
            raise AssertionError(recovered_payload)
        recovery_events = client.get(
            f"/v1/tasks/{restart_task_id}/events?after=0&limit=100"
        )
        recovery_events.raise_for_status()
        event_types = [item["event_type"] for item in recovery_events.json()["events"]]
        if event_types[-1] != "task.failed":
            raise AssertionError(event_types)

    return {
        "status": "passed",
        "task_id": task_id,
        "live_database": str(live_database),
        "backup_database": str(backup_database),
        "restored_database": str(restored_database),
        "backup_sha256": backup_digest,
        "export_sha256": export_digest,
        "restored_export_sha256": restored_export_digest,
        "review_restored": True,
        "restart_task_id": restart_task_id,
        "restart_recovery_code": "PROCESS_RESTARTED",
        "live_task_total_before_restart_fixture": live_snapshot["tasks"]["total"],
        "restored_task_total": restored_snapshot["tasks"]["total"],
        "journal_mode": restored_snapshot["database"]["journal_mode"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exercise local SQLite backup/restore and fail-closed restart recovery."
    )
    parser.add_argument("--workdir", type=Path, default=Path("build/local-state-roundtrip"))
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    summary = run_local_state_roundtrip(args.workdir)
    rendered = json.dumps(summary, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

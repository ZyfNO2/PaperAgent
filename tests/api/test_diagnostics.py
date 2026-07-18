from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paperagent.api import (
    SQLiteReviewRepository,
    SQLiteTaskRepository,
    TaskCreateRequest,
    create_app,
)
from paperagent.api.diagnostics import (
    CURRENT_SCHEMA_VERSION,
    DatabaseNotInitializedError,
    UnsupportedSchemaVersionError,
    collect_runtime_diagnostics,
    ensure_schema_version,
    render_prometheus_metrics,
)
from paperagent.demo import DemoTaskExecutor
from paperagent.schemas.request import ResearchRequest


def _payload(
    question: str = "How should a bounded research agent be evaluated?",
) -> TaskCreateRequest:
    return TaskCreateRequest(request=ResearchRequest(question=question))


def _initialize_database(database: Path) -> SQLiteTaskRepository:
    repository = SQLiteTaskRepository(database)
    SQLiteReviewRepository(repository)
    return repository


def test_schema_version_is_idempotent(tmp_path: Path) -> None:
    database = tmp_path / "paperagent.db"
    _initialize_database(database)

    first = ensure_schema_version(database)
    second = ensure_schema_version(database)

    assert first == second
    assert first["current_version"] == CURRENT_SCHEMA_VERSION
    assert [item["version"] for item in first["migrations"]] == [1]


def test_missing_database_is_not_created_by_diagnostics(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"

    with pytest.raises(FileNotFoundError, match="does not exist"):
        ensure_schema_version(database)

    assert not database.exists()


def test_database_without_application_schema_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "uninitialized.db"
    with sqlite3.connect(database):
        pass

    with pytest.raises(DatabaseNotInitializedError, match="missing required PaperAgent tables"):
        ensure_schema_version(database)


def test_task_only_database_is_not_marked_current(tmp_path: Path) -> None:
    database = tmp_path / "task-only.db"
    SQLiteTaskRepository(database)

    with pytest.raises(DatabaseNotInitializedError, match="paper_reviews"):
        ensure_schema_version(database)


def test_newer_database_schema_fails_closed(tmp_path: Path) -> None:
    database = tmp_path / "future.db"
    _initialize_database(database)
    with sqlite3.connect(database) as connection:
        connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 1}")

    with pytest.raises(UnsupportedSchemaVersionError, match="newer than supported"):
        ensure_schema_version(database)


def test_runtime_diagnostics_and_prometheus_are_secret_free(tmp_path: Path) -> None:
    database = tmp_path / "paperagent.db"
    repository = _initialize_database(database)
    repository.create_task(
        task_id="task-diagnostics",
        idempotency_key="diagnostics-key",
        payload=_payload(),
    )

    snapshot = collect_runtime_diagnostics(database)
    rendered = render_prometheus_metrics(snapshot)

    assert snapshot["tasks"]["total"] == 1
    assert snapshot["tasks"]["by_status"]["queued"] == 1
    assert snapshot["events"]["by_type"]["task.queued"] == 1
    assert snapshot["database"]["schema"]["current_version"] == CURRENT_SCHEMA_VERSION
    assert 'paperagent_tasks_by_status{status="queued"} 1' in rendered
    assert "diagnostics-key" not in json.dumps(snapshot)


def test_diagnostics_http_endpoints(tmp_path: Path) -> None:
    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=tmp_path / "paperagent.db",
    )

    with TestClient(app) as client:
        diagnostics = client.get("/v1/diagnostics/runtime")
        metrics = client.get("/metrics")
        readiness = client.get("/readyz")

    assert diagnostics.status_code == 200
    assert diagnostics.json()["execution_mode"] == "single_process"
    assert metrics.status_code == 200
    assert "paperagent_schema_version 1" in metrics.text
    assert readiness.status_code == 200
    assert readiness.json()["checks"]["schema"] == {"ok": True, "version": 1}

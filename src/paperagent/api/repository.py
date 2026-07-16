from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from paperagent.api.models import (
    JsonObject,
    TaskCreateRequest,
    TaskError,
    TaskEvent,
    TaskRecord,
    TaskStatus,
)

MAX_EVENT_PAYLOAD_BYTES = 16_384


class TaskNotFoundError(LookupError):
    pass


class IdempotencyConflictError(ValueError):
    pass


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SQLiteTaskRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if self.database_path != Path(":memory:"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    request_json TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    cancel_requested INTEGER NOT NULL DEFAULT 0,
                    result_json TEXT,
                    error_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );

                CREATE TABLE IF NOT EXISTS task_events (
                    task_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (task_id, sequence),
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_tasks_status_created
                    ON tasks(status, created_at, task_id);
                CREATE INDEX IF NOT EXISTS idx_task_events_cursor
                    ON task_events(task_id, sequence);
                """
            )

    def create_task(
        self,
        *,
        task_id: str,
        idempotency_key: str,
        payload: TaskCreateRequest,
        now: datetime | None = None,
    ) -> tuple[TaskRecord, bool]:
        instant = now or utc_now()
        request_json = _canonical_json(payload.model_dump(mode="json"))
        request_hash = hashlib.sha256(request_json.encode("utf-8")).hexdigest()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM tasks WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            if existing is not None:
                if cast(str, existing["request_hash"]) != request_hash:
                    raise IdempotencyConflictError(
                        "idempotency key is already bound to a different request"
                    )
                return self._record_from_row(connection, existing), True

            timestamp = _iso(instant)
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, idempotency_key, request_json, request_hash, status,
                    cancel_requested, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    task_id,
                    idempotency_key,
                    request_json,
                    request_hash,
                    TaskStatus.QUEUED.value,
                    timestamp,
                    timestamp,
                ),
            )
            self._append_event_tx(
                connection,
                task_id=task_id,
                event_type="task.queued",
                payload={"status": TaskStatus.QUEUED.value},
                now=instant,
            )
            row = self._require_row(connection, task_id)
            return self._record_from_row(connection, row), False

    def get_task(self, task_id: str) -> TaskRecord:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise TaskNotFoundError(task_id)
            return self._record_from_row(connection, row)

    def list_events(
        self, task_id: str, *, after_sequence: int = 0, limit: int = 100
    ) -> list[TaskEvent]:
        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative")
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        with self._connect() as connection:
            if connection.execute(
                "SELECT 1 FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone() is None:
                raise TaskNotFoundError(task_id)
            rows = connection.execute(
                """
                SELECT task_id, sequence, event_type, payload_json, created_at
                FROM task_events
                WHERE task_id = ? AND sequence > ?
                ORDER BY sequence ASC
                LIMIT ?
                """,
                (task_id, after_sequence, limit),
            ).fetchall()
            return [self._event_from_row(row) for row in rows]

    def append_event(
        self,
        *,
        task_id: str,
        event_type: str,
        payload: JsonObject,
        now: datetime | None = None,
    ) -> TaskEvent:
        instant = now or utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_row(connection, task_id)
            sequence = self._append_event_tx(
                connection,
                task_id=task_id,
                event_type=event_type,
                payload=payload,
                now=instant,
            )
            row = connection.execute(
                """
                SELECT task_id, sequence, event_type, payload_json, created_at
                FROM task_events WHERE task_id = ? AND sequence = ?
                """,
                (task_id, sequence),
            ).fetchone()
            if row is None:  # pragma: no cover - protected by the transaction
                raise RuntimeError("event insert did not persist")
            return self._event_from_row(row)

    def claim_next_task(self, *, now: datetime | None = None) -> TaskRecord | None:
        instant = now or utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT * FROM tasks
                WHERE status = ? AND cancel_requested = 0
                ORDER BY created_at ASC, task_id ASC
                LIMIT 1
                """,
                (TaskStatus.QUEUED.value,),
            ).fetchone()
            if row is None:
                return None
            task_id = cast(str, row["task_id"])
            timestamp = _iso(instant)
            updated = connection.execute(
                """
                UPDATE tasks
                SET status = ?, started_at = COALESCE(started_at, ?), updated_at = ?
                WHERE task_id = ? AND status = ? AND cancel_requested = 0
                """,
                (
                    TaskStatus.RUNNING.value,
                    timestamp,
                    timestamp,
                    task_id,
                    TaskStatus.QUEUED.value,
                ),
            ).rowcount
            if updated != 1:
                return None
            self._append_event_tx(
                connection,
                task_id=task_id,
                event_type="task.started",
                payload={"status": TaskStatus.RUNNING.value},
                now=instant,
            )
            return self._record_from_row(connection, self._require_row(connection, task_id))

    def request_cancel(
        self, task_id: str, *, now: datetime | None = None
    ) -> tuple[TaskRecord, bool]:
        instant = now or utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = self._require_row(connection, task_id)
            status = TaskStatus(cast(str, row["status"]))
            if status in {TaskStatus.CANCELLED, TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
                return self._record_from_row(connection, row), False
            if status is TaskStatus.CANCEL_REQUESTED:
                return self._record_from_row(connection, row), False

            timestamp = _iso(instant)
            if status is TaskStatus.QUEUED:
                next_status = TaskStatus.CANCELLED
                finished_at: str | None = timestamp
                event_type = "task.cancelled"
            else:
                next_status = TaskStatus.CANCEL_REQUESTED
                finished_at = None
                event_type = "task.cancel_requested"
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, cancel_requested = 1, updated_at = ?, finished_at = ?
                WHERE task_id = ?
                """,
                (next_status.value, timestamp, finished_at, task_id),
            )
            self._append_event_tx(
                connection,
                task_id=task_id,
                event_type=event_type,
                payload={"status": next_status.value},
                now=instant,
            )
            return self._record_from_row(connection, self._require_row(connection, task_id)), True

    def should_cancel(self, task_id: str) -> bool:
        return self.get_task(task_id).cancel_requested

    def complete_task(
        self, task_id: str, result: JsonObject, *, now: datetime | None = None
    ) -> TaskRecord:
        return self._finish_task(
            task_id,
            status=TaskStatus.SUCCEEDED,
            result=result,
            error=None,
            event_type="task.succeeded",
            now=now,
        )

    def fail_task(
        self, task_id: str, error: TaskError, *, now: datetime | None = None
    ) -> TaskRecord:
        return self._finish_task(
            task_id,
            status=TaskStatus.FAILED,
            result=None,
            error=error,
            event_type="task.failed",
            now=now,
        )

    def mark_cancelled(self, task_id: str, *, now: datetime | None = None) -> TaskRecord:
        return self._finish_task(
            task_id,
            status=TaskStatus.CANCELLED,
            result=None,
            error=None,
            event_type="task.cancelled",
            now=now,
            cancel_requested=True,
        )

    def recover_inflight_tasks(self, *, now: datetime | None = None) -> int:
        instant = now or utc_now()
        error = TaskError(
            code="PROCESS_RESTARTED",
            message=(
                "The single-process runner restarted while this task was active. "
                "The MVP fails closed instead of replaying provider calls."
            ),
            retryable=True,
        )
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                "SELECT task_id FROM tasks WHERE status IN (?, ?)",
                (TaskStatus.RUNNING.value, TaskStatus.CANCEL_REQUESTED.value),
            ).fetchall()
            timestamp = _iso(instant)
            for row in rows:
                task_id = cast(str, row["task_id"])
                connection.execute(
                    """
                    UPDATE tasks
                    SET status = ?, error_json = ?, updated_at = ?, finished_at = ?
                    WHERE task_id = ?
                    """,
                    (
                        TaskStatus.FAILED.value,
                        _canonical_json(error.model_dump(mode="json")),
                        timestamp,
                        timestamp,
                        task_id,
                    ),
                )
                self._append_event_tx(
                    connection,
                    task_id=task_id,
                    event_type="task.failed",
                    payload={"code": error.code, "status": TaskStatus.FAILED.value},
                    now=instant,
                )
            return len(rows)

    def has_queued_tasks(self) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM tasks WHERE status = ? LIMIT 1", (TaskStatus.QUEUED.value,)
            ).fetchone()
            return row is not None

    def _finish_task(
        self,
        task_id: str,
        *,
        status: TaskStatus,
        result: JsonObject | None,
        error: TaskError | None,
        event_type: str,
        now: datetime | None,
        cancel_requested: bool | None = None,
    ) -> TaskRecord:
        instant = now or utc_now()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            self._require_row(connection, task_id)
            timestamp = _iso(instant)
            connection.execute(
                """
                UPDATE tasks
                SET status = ?, result_json = ?, error_json = ?, updated_at = ?, finished_at = ?,
                    cancel_requested = COALESCE(?, cancel_requested)
                WHERE task_id = ?
                """,
                (
                    status.value,
                    _canonical_json(result) if result is not None else None,
                    _canonical_json(error.model_dump(mode="json")) if error else None,
                    timestamp,
                    timestamp,
                    int(cancel_requested) if cancel_requested is not None else None,
                    task_id,
                ),
            )
            payload: JsonObject = {"status": status.value}
            if error is not None:
                payload["code"] = error.code
            self._append_event_tx(
                connection,
                task_id=task_id,
                event_type=event_type,
                payload=payload,
                now=instant,
            )
            return self._record_from_row(connection, self._require_row(connection, task_id))

    def _append_event_tx(
        self,
        connection: sqlite3.Connection,
        *,
        task_id: str,
        event_type: str,
        payload: JsonObject,
        now: datetime,
    ) -> int:
        payload_json = _canonical_json(payload)
        if len(payload_json.encode("utf-8")) > MAX_EVENT_PAYLOAD_BYTES:
            raise ValueError("event payload exceeds the 16 KiB MVP limit")
        sequence_row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM task_events WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        if sequence_row is None:  # pragma: no cover - aggregate always returns one row
            raise RuntimeError("failed to allocate event sequence")
        sequence = int(sequence_row["next_sequence"])
        connection.execute(
            """
            INSERT INTO task_events (task_id, sequence, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task_id, sequence, event_type, payload_json, _iso(now)),
        )
        return sequence

    def _require_row(self, connection: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise TaskNotFoundError(task_id)
        return row

    def _record_from_row(
        self, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> TaskRecord:
        payload = TaskCreateRequest.model_validate_json(cast(str, row["request_json"]))
        result_raw = cast(str | None, row["result_json"])
        error_raw = cast(str | None, row["error_json"])
        cursor_row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS cursor FROM task_events WHERE task_id = ?",
            (cast(str, row["task_id"]),),
        ).fetchone()
        cursor = int(cursor_row["cursor"]) if cursor_row is not None else 0
        result = cast(JsonObject | None, json.loads(result_raw) if result_raw else None)
        error = TaskError.model_validate_json(error_raw) if error_raw else None
        created_at = _parse_time(cast(str, row["created_at"]))
        updated_at = _parse_time(cast(str, row["updated_at"]))
        if created_at is None or updated_at is None:  # pragma: no cover - database constraints
            raise RuntimeError("task timestamps are missing")
        return TaskRecord(
            task_id=cast(str, row["task_id"]),
            idempotency_key=cast(str, row["idempotency_key"]),
            request=payload.request,
            request_hash=cast(str, row["request_hash"]),
            metadata=payload.metadata,
            status=TaskStatus(cast(str, row["status"])),
            cancel_requested=bool(row["cancel_requested"]),
            result=result,
            error=error,
            created_at=created_at,
            updated_at=updated_at,
            started_at=_parse_time(cast(str | None, row["started_at"])),
            finished_at=_parse_time(cast(str | None, row["finished_at"])),
            event_cursor=cursor,
        )

    @staticmethod
    def _event_from_row(row: sqlite3.Row) -> TaskEvent:
        payload = cast(JsonObject, json.loads(cast(str, row["payload_json"])))
        created_at = _parse_time(cast(str, row["created_at"]))
        if created_at is None:  # pragma: no cover - database constraints
            raise RuntimeError("event timestamp is missing")
        return TaskEvent(
            task_id=cast(str, row["task_id"]),
            sequence=int(row["sequence"]),
            event_type=cast(str, row["event_type"]),
            payload=payload,
            created_at=created_at,
        )


def task_ids(records: Iterable[TaskRecord]) -> list[str]:
    return [record.task_id for record in records]

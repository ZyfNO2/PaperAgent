from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from paperagent.api.models import TaskStatus

CURRENT_SCHEMA_VERSION = 1
_REQUIRED_SCHEMA_TABLES = ("tasks", "task_events", "paper_reviews")


class DatabaseNotInitializedError(RuntimeError):
    """Raised when diagnostics target a file without the durable application schema."""


class UnsupportedSchemaVersionError(RuntimeError):
    """Raised when a database was created by a newer incompatible PaperAgent build."""


def _database_path(database_path: str | Path) -> Path:
    path = Path(database_path)
    if path != Path(":memory:") and not path.exists():
        raise FileNotFoundError(f"PaperAgent database does not exist: {path}")
    return path


def _connect(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(_database_path(database_path)), timeout=30.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def _has_table(connection: sqlite3.Connection, name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def ensure_schema_version(database_path: str | Path) -> dict[str, Any]:
    """Apply metadata migrations after verifying the durable application schema."""

    with _connect(database_path) as connection:
        missing = [name for name in _REQUIRED_SCHEMA_TABLES if not _has_table(connection, name)]
        if missing:
            raise DatabaseNotInitializedError(
                "database is missing required PaperAgent tables: " + ", ".join(missing)
            )
        current = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if current > CURRENT_SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(
                f"database schema {current} is newer than supported {CURRENT_SCHEMA_VERSION}"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied_at = datetime.now(tz=UTC).isoformat()
        connection.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, name, applied_at)
            VALUES (1, 'initial_task_and_review_schema', ?)
            """,
            (applied_at,),
        )
        if current < 1:
            connection.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION}")
            current = CURRENT_SCHEMA_VERSION
        rows = connection.execute(
            "SELECT version, name, applied_at FROM schema_migrations ORDER BY version"
        ).fetchall()
    return {
        "current_version": current,
        "supported_version": CURRENT_SCHEMA_VERSION,
        "migrations": [
            {
                "version": int(row["version"]),
                "name": cast(str, row["name"]),
                "applied_at": cast(str, row["applied_at"]),
            }
            for row in rows
        ],
    }


def collect_runtime_diagnostics(database_path: str | Path) -> dict[str, Any]:
    """Return low-cardinality, secret-free operational state for local diagnosis."""

    schema = ensure_schema_version(database_path)
    status_counts = {status.value: 0 for status in TaskStatus}
    event_counts: dict[str, int] = {}
    with _connect(database_path) as connection:
        for row in connection.execute(
            "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
        ).fetchall():
            status_counts[cast(str, row["status"])] = int(row["count"])
        for row in connection.execute(
            "SELECT event_type, COUNT(*) AS count FROM task_events GROUP BY event_type"
        ).fetchall():
            event_counts[cast(str, row["event_type"])] = int(row["count"])
        task_total = int(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0])
        event_total = int(connection.execute("SELECT COUNT(*) FROM task_events").fetchone()[0])

    path = Path(database_path)
    size_bytes = 0 if path == Path(":memory:") else path.stat().st_size
    return {
        "service": "paperagent",
        "execution_mode": "single_process",
        "database": {
            "engine": "sqlite",
            "journal_mode": "wal" if path != Path(":memory:") else "memory",
            "size_bytes": size_bytes,
            "schema": schema,
        },
        "tasks": {"total": task_total, "by_status": status_counts},
        "events": {"total": event_total, "by_type": dict(sorted(event_counts.items()))},
    }


def render_prometheus_metrics(snapshot: dict[str, Any]) -> str:
    """Render a stable Prometheus text exposition without adding a runtime dependency."""

    tasks = cast(dict[str, Any], snapshot["tasks"])
    events = cast(dict[str, Any], snapshot["events"])
    database = cast(dict[str, Any], snapshot["database"])
    schema = cast(dict[str, Any], database["schema"])
    lines = [
        "# HELP paperagent_tasks_total Total durable tasks.",
        "# TYPE paperagent_tasks_total gauge",
        f"paperagent_tasks_total {int(tasks['total'])}",
        "# HELP paperagent_tasks_by_status Durable tasks by lifecycle status.",
        "# TYPE paperagent_tasks_by_status gauge",
    ]
    for status, count in sorted(cast(dict[str, int], tasks["by_status"]).items()):
        lines.append(f'paperagent_tasks_by_status{{status="{status}"}} {count}')
    lines.extend(
        [
            "# HELP paperagent_events_total Total durable task events.",
            "# TYPE paperagent_events_total gauge",
            f"paperagent_events_total {int(events['total'])}",
            "# HELP paperagent_database_size_bytes SQLite database file size.",
            "# TYPE paperagent_database_size_bytes gauge",
            f"paperagent_database_size_bytes {int(database['size_bytes'])}",
            "# HELP paperagent_schema_version Current SQLite schema version.",
            "# TYPE paperagent_schema_version gauge",
            f"paperagent_schema_version {int(schema['current_version'])}",
        ]
    )
    return "\n".join(lines) + "\n"

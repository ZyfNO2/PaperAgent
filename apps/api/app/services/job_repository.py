"""Re7.1 Job Runtime — Job schema and repository.

Job lifecycle: pending → running → completed | failed | cancelled → resumable.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

JobStatus = Literal["pending", "running", "completed", "failed", "cancelled", "resumable"]


class JobCreate(BaseModel):
    topic: str = ""
    idempotency_key: str = ""
    budget_tokens: int = 50000
    budget_timeout_s: int = 1800  # 30 min


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: _uuid())
    case_id: str = ""
    idempotency_key: str = ""
    topic: str = ""
    status: JobStatus = "pending"
    created_at: str = Field(default_factory=lambda: _utcnow())
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    budget_tokens: int = 50000
    tokens_used: int = 0
    budget_timeout_s: int = 0
    node_checkpoint: str | None = None
    worker_lease: str | None = None
    lease_expires_at: str | None = None


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobRepository:
    """SQLite-backed job repository.

    MVP: single worker, SQLite. No distributed coordination.
    """

    def __init__(self, db_path: str = ":memory:"):
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get or create a connection. For :memory:, reuse same connection."""
        if self._db_path == ":memory:":
            if self._conn is None:
                self._conn = sqlite3.connect(":memory:", check_same_thread=False)
                self._conn.row_factory = sqlite3.Row
            return self._conn
        return sqlite3.connect(self._db_path)

    def _init_db(self) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    case_id TEXT,
                    idempotency_key TEXT,
                    topic TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    error TEXT,
                    budget_tokens INTEGER DEFAULT 50000,
                    tokens_used INTEGER DEFAULT 0,
                    budget_timeout_s INTEGER DEFAULT 0,
                    node_checkpoint TEXT,
                    worker_lease TEXT,
                    lease_expires_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    seq INTEGER NOT NULL,
                    event_type TEXT,
                    event_data TEXT,
                    created_at TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
                )
            """)
            conn.commit()

    def create_job(self, job: JobCreate) -> JobRecord:
        with self._lock:
            conn = self._get_conn()
            existing = conn.execute(
                "SELECT job_id, status FROM jobs WHERE idempotency_key = ? AND status != 'cancelled'",
                (job.idempotency_key,),
            ).fetchone()
            if existing:
                raise ValueError(f"duplicate idempotency_key: {existing[0]} (status={existing[1]})")

            record = JobRecord(
                idempotency_key=job.idempotency_key,
                topic=job.topic,
                budget_tokens=job.budget_tokens,
                budget_timeout_s=job.budget_timeout_s,
            )
            conn.execute(
                """INSERT INTO jobs (job_id, case_id, idempotency_key, topic, status,
                   created_at, budget_tokens, budget_timeout_s)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.job_id, record.case_id, record.idempotency_key,
                 record.topic, record.status, record.created_at,
                 record.budget_tokens, record.budget_timeout_s),
            )
            conn.commit()
            return record

    def get_job(self, job_id: str) -> JobRecord | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_jobs(self, status: str | None = None) -> list[JobRecord]:
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_status(self, job_id: str, status: JobStatus, error: str | None = None) -> bool:
        with self._lock:
            conn = self._get_conn()
            now = _utcnow()
            updates = ["status = ?"]
            params: list[Any] = [status]
            if status == "running" or status == "resumable":
                updates.append("started_at = COALESCE(started_at, ?)")
                params.append(now)
            if status in ("completed", "failed", "cancelled"):
                updates.append("completed_at = ?")
                params.append(now)
            if error:
                updates.append("error = ?")
                params.append(error)
            params.append(job_id)
            conn.execute(
                f"UPDATE jobs SET {', '.join(updates)} WHERE job_id = ?",
                params,
            )
            conn.commit()
            affected = conn.total_changes
            return affected > 0

    def acquire_lease(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> bool:
        with self._lock:
            conn = self._get_conn()
            expires = datetime.now(timezone.utc).timestamp() + lease_seconds
            expires_str = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat()
            conn.execute(
                """UPDATE jobs SET worker_lease = ?, lease_expires_at = ?
                   WHERE job_id = ? AND status = 'pending'""",
                (worker_id, expires_str, job_id),
            )
            conn.commit()
            affected = conn.total_changes
            return affected > 0

    def update_checkpoint(self, job_id: str, node_name: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE jobs SET node_checkpoint = ? WHERE job_id = ?",
                (node_name, job_id),
            )
            conn.commit()

    def update_tokens(self, job_id: str, tokens: int) -> bool:
        """Add tokens used. Returns True if budget not exceeded."""
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE jobs SET tokens_used = tokens_used + ? WHERE job_id = ?",
                (tokens, job_id),
            )
            conn.commit()
            row = conn.execute(
                "SELECT tokens_used, budget_tokens FROM jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
            if row and row[1] > 0 and row[0] >= row[1]:
                return False  # Budget exceeded
            return True

    def append_event(self, job_id: str, event_type: str, data: dict[str, Any]) -> int:
        with self._lock:
            conn = self._get_conn()
            seq = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM job_events WHERE job_id = ?",
                (job_id,),
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO job_events (job_id, seq, event_type, event_data, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (job_id, seq, event_type, json.dumps(data, default=str), _utcnow()),
            )
            conn.commit()
            return seq

    def get_events(self, job_id: str, after_seq: int = 0) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT seq, event_type, event_data, created_at FROM job_events "
            "WHERE job_id = ? AND seq > ? ORDER BY seq",
            (job_id, after_seq),
        ).fetchall()
        return [
            {"seq": r[0], "type": r[1], "data": json.loads(r[2]), "created_at": r[3]}
            for r in rows
        ]

    def cancel_job(self, job_id: str) -> bool:
        return self.update_status(job_id, "cancelled", "user requested cancellation")

    def _row_to_record(self, row: tuple) -> JobRecord:
        cols = [
            "job_id", "case_id", "idempotency_key", "topic", "status",
            "created_at", "started_at", "completed_at", "error",
            "budget_tokens", "tokens_used", "budget_timeout_s",
            "node_checkpoint", "worker_lease", "lease_expires_at",
        ]
        data = dict(zip(cols, row))
        return JobRecord(**{k: v for k, v in data.items() if v is not None or k in ("error", "started_at", "completed_at")})

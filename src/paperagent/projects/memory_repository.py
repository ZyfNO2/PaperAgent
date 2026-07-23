from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from uuid import uuid4

from paperagent.projects.corpus_repository import SQLiteCorpusRepository
from paperagent.projects.models import (
    MemoryCategory,
    MemoryScope,
    MemoryStatus,
    ProjectMemoryEntry,
)
from paperagent.projects.storage import (
    MemoryEntryNotFoundError,
    SQLiteProjectDatabase,
    iso,
    memory_from_row,
    utc_now,
)


class SQLiteMemoryRepository:
    def __init__(
        self,
        database: SQLiteProjectDatabase,
        corpus: SQLiteCorpusRepository,
    ) -> None:
        self.database = database
        self.corpus = corpus

    def propose_memory(
        self,
        *,
        project_id: str,
        scope: MemoryScope,
        category: MemoryCategory,
        content: str,
        evidence_unit_ids: Iterable[str] = (),
        memory_id: str | None = None,
        now: datetime | None = None,
    ) -> ProjectMemoryEntry:
        self.corpus.get_project(project_id)
        clean_content = content.strip()
        if not clean_content:
            raise ValueError("memory content must not be empty")
        evidence_ids = tuple(dict.fromkeys(evidence_unit_ids))
        if len(self.corpus.get_evidence_units_by_id(project_id, evidence_ids)) != len(
            evidence_ids
        ):
            raise ValueError("memory references unknown evidence units")
        instant = now or utc_now()
        identifier = memory_id or f"mem-{uuid4().hex}"
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO project_memory (
                    memory_id, project_id, scope, category, content,
                    evidence_unit_ids_json, status, proposed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    project_id,
                    scope.value,
                    category.value,
                    clean_content,
                    json.dumps(evidence_ids),
                    MemoryStatus.PROPOSED.value,
                    iso(instant),
                ),
            )
            connection.execute(
                """
                INSERT INTO memory_write_audit (
                    memory_id, from_status, to_status, note, created_at
                ) VALUES (?, NULL, ?, ?, ?)
                """,
                (identifier, MemoryStatus.PROPOSED.value, "proposal created", iso(instant)),
            )
        return ProjectMemoryEntry(
            memory_id=identifier,
            project_id=project_id,
            scope=scope,
            category=category,
            content=clean_content,
            evidence_unit_ids=evidence_ids,
            status=MemoryStatus.PROPOSED,
            proposed_at=instant,
        )

    def review_memory(
        self,
        memory_id: str,
        *,
        approve: bool,
        note: str | None = None,
        now: datetime | None = None,
    ) -> ProjectMemoryEntry:
        instant = now or utc_now()
        target = MemoryStatus.APPROVED if approve else MemoryStatus.REJECTED
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM project_memory WHERE memory_id = ?", (memory_id,)
            ).fetchone()
            if row is None:
                raise MemoryEntryNotFoundError(memory_id)
            current = MemoryStatus(str(row["status"]))
            if current is not MemoryStatus.PROPOSED:
                raise ValueError("only proposed memory entries can be reviewed")
            connection.execute(
                """
                UPDATE project_memory
                SET status = ?, reviewed_at = ?, review_note = ?
                WHERE memory_id = ?
                """,
                (target.value, iso(instant), note, memory_id),
            )
            connection.execute(
                """
                INSERT INTO memory_write_audit (
                    memory_id, from_status, to_status, note, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, current.value, target.value, note, iso(instant)),
            )
            updated = connection.execute(
                "SELECT * FROM project_memory WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        if updated is None:  # pragma: no cover
            raise RuntimeError("memory review did not persist")
        return memory_from_row(updated)

    def list_memory(
        self, project_id: str, *, include_pending: bool = False
    ) -> tuple[ProjectMemoryEntry, ...]:
        self.corpus.get_project(project_id)
        where = "project_id = ?" if include_pending else "project_id = ? AND status = ?"
        params: tuple[object, ...] = (
            (project_id,)
            if include_pending
            else (project_id, MemoryStatus.APPROVED.value)
        )
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM project_memory WHERE {where}
                ORDER BY proposed_at, memory_id
                """,
                params,
            ).fetchall()
        return tuple(memory_from_row(row) for row in rows)

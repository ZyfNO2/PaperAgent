from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from paperagent.projects.models import (
    CitationLocator,
    EvidenceUnit,
    MemoryCategory,
    MemoryScope,
    MemoryStatus,
    PaperVersion,
    ProjectMemoryEntry,
)


class ProjectNotFoundError(LookupError):
    pass


class PaperNotFoundError(LookupError):
    pass


class MemoryEntryNotFoundError(LookupError):
    pass


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("timestamps must be timezone-aware")
    return value.astimezone(UTC).isoformat()


def loads_object(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("expected a JSON object")
    return cast(dict[str, Any], parsed)


class SQLiteProjectDatabase:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        if self.database_path != Path(":memory:"):
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.database_path), timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        if self.database_path != Path(":memory:"):
            connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_projects (
                    project_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    research_question TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_versions (
                    paper_id TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    content_sha256 TEXT NOT NULL,
                    ingestion_version INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    ingested_at TEXT NOT NULL,
                    PRIMARY KEY (paper_id, ingestion_version),
                    FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS evidence_units (
                    unit_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    paper_id TEXT NOT NULL,
                    ingestion_version INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    section TEXT,
                    page INTEGER,
                    paragraph INTEGER,
                    keywords_json TEXT NOT NULL,
                    locator_json TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (paper_id, ingestion_version)
                        REFERENCES paper_versions(paper_id, ingestion_version)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS project_memory (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    evidence_unit_ids_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    proposed_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    review_note TEXT,
                    FOREIGN KEY (project_id) REFERENCES research_projects(project_id)
                        ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS memory_write_audit (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (memory_id) REFERENCES project_memory(memory_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_paper_versions_project
                    ON paper_versions(project_id, paper_id, ingestion_version DESC);
                CREATE INDEX IF NOT EXISTS idx_evidence_project_paper
                    ON evidence_units(project_id, paper_id, ingestion_version);
                CREATE INDEX IF NOT EXISTS idx_memory_project_status
                    ON project_memory(project_id, status, scope, proposed_at);
                """
            )


def paper_from_row(row: sqlite3.Row) -> PaperVersion:
    return PaperVersion(
        paper_id=cast(str, row["paper_id"]),
        project_id=cast(str, row["project_id"]),
        title=cast(str, row["title"]),
        source_path=Path(cast(str, row["source_path"])),
        content_sha256=cast(str, row["content_sha256"]),
        ingestion_version=cast(int, row["ingestion_version"]),
        media_type=cast(str, row["media_type"]),
        metadata=loads_object(cast(str, row["metadata_json"])),
        ingested_at=datetime.fromisoformat(cast(str, row["ingested_at"])),
    )


def evidence_from_row(row: sqlite3.Row) -> EvidenceUnit:
    keywords_raw = json.loads(cast(str, row["keywords_json"]))
    if not isinstance(keywords_raw, list):
        raise ValueError("invalid evidence keywords")
    return EvidenceUnit(
        unit_id=cast(str, row["unit_id"]),
        project_id=cast(str, row["project_id"]),
        paper_id=cast(str, row["paper_id"]),
        ingestion_version=cast(int, row["ingestion_version"]),
        content=cast(str, row["content"]),
        section=cast(str | None, row["section"]),
        page=cast(int | None, row["page"]),
        paragraph=cast(int | None, row["paragraph"]),
        keywords=tuple(str(item) for item in keywords_raw),
        locator=CitationLocator.model_validate_json(cast(str, row["locator_json"])),
    )


def memory_from_row(row: sqlite3.Row) -> ProjectMemoryEntry:
    evidence_raw = json.loads(cast(str, row["evidence_unit_ids_json"]))
    if not isinstance(evidence_raw, list):
        raise ValueError("invalid memory evidence references")
    return ProjectMemoryEntry(
        memory_id=cast(str, row["memory_id"]),
        project_id=cast(str, row["project_id"]),
        scope=MemoryScope(cast(str, row["scope"])),
        category=MemoryCategory(cast(str, row["category"])),
        content=cast(str, row["content"]),
        evidence_unit_ids=tuple(str(item) for item in evidence_raw),
        status=MemoryStatus(cast(str, row["status"])),
        proposed_at=datetime.fromisoformat(cast(str, row["proposed_at"])),
        reviewed_at=(
            datetime.fromisoformat(cast(str, row["reviewed_at"]))
            if row["reviewed_at"] is not None
            else None
        ),
        review_note=cast(str | None, row["review_note"]),
    )

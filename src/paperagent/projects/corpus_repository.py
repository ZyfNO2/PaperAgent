from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from typing import cast
from uuid import uuid4

from paperagent.projects.models import EvidenceUnit, PaperVersion, ResearchProject
from paperagent.projects.storage import (
    PaperNotFoundError,
    ProjectNotFoundError,
    SQLiteProjectDatabase,
    evidence_from_row,
    iso,
    paper_from_row,
    utc_now,
)


class SQLiteCorpusRepository:
    def __init__(self, database: SQLiteProjectDatabase) -> None:
        self.database = database

    def create_project(
        self,
        *,
        name: str,
        research_question: str,
        project_id: str | None = None,
        now: datetime | None = None,
    ) -> ResearchProject:
        clean_name = name.strip()
        clean_question = research_question.strip()
        if not clean_name or not clean_question:
            raise ValueError("project name and research question must not be empty")
        instant = now or utc_now()
        identifier = project_id or f"proj-{uuid4().hex}"
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO research_projects (
                    project_id, name, research_question, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (identifier, clean_name, clean_question, iso(instant), iso(instant)),
            )
        return ResearchProject(
            project_id=identifier,
            name=clean_name,
            research_question=clean_question,
            created_at=instant,
            updated_at=instant,
        )

    def get_project(self, project_id: str) -> ResearchProject:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM research_projects WHERE project_id = ?", (project_id,)
            ).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id)
        return ResearchProject(
            project_id=cast(str, row["project_id"]),
            name=cast(str, row["name"]),
            research_question=cast(str, row["research_question"]),
            created_at=datetime.fromisoformat(cast(str, row["created_at"])),
            updated_at=datetime.fromisoformat(cast(str, row["updated_at"])),
        )

    def next_ingestion_version(self, *, project_id: str, paper_id: str) -> int:
        self.get_project(project_id)
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT MAX(ingestion_version) AS latest
                FROM paper_versions WHERE project_id = ? AND paper_id = ?
                """,
                (project_id, paper_id),
            ).fetchone()
        latest = cast(int | None, row["latest"] if row is not None else None)
        return 1 if latest is None else latest + 1

    def persist_ingestion(
        self, paper: PaperVersion, evidence_units: Iterable[EvidenceUnit]
    ) -> None:
        self.get_project(paper.project_id)
        units = tuple(evidence_units)
        if any(
            unit.project_id != paper.project_id
            or unit.paper_id != paper.paper_id
            or unit.ingestion_version != paper.ingestion_version
            for unit in units
        ):
            raise ValueError("evidence units must match the paper identity and version")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT INTO paper_versions (
                    paper_id, project_id, title, source_path, content_sha256,
                    ingestion_version, media_type, metadata_json, ingested_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper.paper_id,
                    paper.project_id,
                    paper.title,
                    str(paper.source_path),
                    paper.content_sha256,
                    paper.ingestion_version,
                    paper.media_type,
                    json.dumps(paper.metadata, ensure_ascii=False, sort_keys=True),
                    iso(paper.ingested_at),
                ),
            )
            connection.executemany(
                """
                INSERT INTO evidence_units (
                    unit_id, project_id, paper_id, ingestion_version, content,
                    section, page, paragraph, keywords_json, locator_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        unit.unit_id,
                        unit.project_id,
                        unit.paper_id,
                        unit.ingestion_version,
                        unit.content,
                        unit.section,
                        unit.page,
                        unit.paragraph,
                        json.dumps(unit.keywords, ensure_ascii=False),
                        unit.locator.model_dump_json(),
                    )
                    for unit in units
                ],
            )
            connection.execute(
                "UPDATE research_projects SET updated_at = ? WHERE project_id = ?",
                (iso(paper.ingested_at), paper.project_id),
            )

    def get_latest_paper(self, *, project_id: str, paper_id: str) -> PaperVersion:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM paper_versions
                WHERE project_id = ? AND paper_id = ?
                ORDER BY ingestion_version DESC LIMIT 1
                """,
                (project_id, paper_id),
            ).fetchone()
        if row is None:
            raise PaperNotFoundError(paper_id)
        return paper_from_row(row)

    def list_latest_papers(self, project_id: str) -> tuple[PaperVersion, ...]:
        self.get_project(project_id)
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT pv.* FROM paper_versions pv
                JOIN (
                    SELECT paper_id, MAX(ingestion_version) AS latest_version
                    FROM paper_versions WHERE project_id = ? GROUP BY paper_id
                ) latest ON latest.paper_id = pv.paper_id
                    AND latest.latest_version = pv.ingestion_version
                WHERE pv.project_id = ?
                ORDER BY pv.title ASC, pv.paper_id ASC
                """,
                (project_id, project_id),
            ).fetchall()
        return tuple(paper_from_row(row) for row in rows)

    def list_evidence_units(
        self,
        project_id: str,
        *,
        paper_ids: Iterable[str] | None = None,
    ) -> tuple[EvidenceUnit, ...]:
        self.get_project(project_id)
        selected = tuple(dict.fromkeys(paper_ids or ()))
        paper_clause = ""
        params: list[object] = [project_id, project_id]
        if selected:
            paper_clause = f" AND eu.paper_id IN ({','.join('?' for _ in selected)})"
            params.extend(selected)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT eu.* FROM evidence_units eu
                JOIN (
                    SELECT paper_id, MAX(ingestion_version) AS latest_version
                    FROM paper_versions WHERE project_id = ? GROUP BY paper_id
                ) latest ON latest.paper_id = eu.paper_id
                    AND latest.latest_version = eu.ingestion_version
                WHERE eu.project_id = ?{paper_clause}
                ORDER BY eu.paper_id, eu.page, eu.paragraph, eu.unit_id
                """,
                params,
            ).fetchall()
        return tuple(evidence_from_row(row) for row in rows)

    def get_evidence_units_by_id(
        self, project_id: str, unit_ids: Iterable[str]
    ) -> tuple[EvidenceUnit, ...]:
        selected = tuple(dict.fromkeys(unit_ids))
        if not selected:
            return ()
        placeholders = ",".join("?" for _ in selected)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM evidence_units
                WHERE project_id = ? AND unit_id IN ({placeholders})
                ORDER BY unit_id
                """,
                (project_id, *selected),
            ).fetchall()
        return tuple(evidence_from_row(row) for row in rows)

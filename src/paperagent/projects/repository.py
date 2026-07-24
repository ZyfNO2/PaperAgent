from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from paperagent.projects.corpus_repository import SQLiteCorpusRepository
from paperagent.projects.memory_repository import SQLiteMemoryRepository
from paperagent.projects.models import (
    EvidenceUnit,
    MemoryCategory,
    MemoryScope,
    PaperVersion,
    ProjectMemoryEntry,
    ResearchProject,
)
from paperagent.projects.storage import (
    MemoryEntryNotFoundError,
    PaperNotFoundError,
    ProjectNotFoundError,
    SQLiteProjectDatabase,
    utc_now,
)


class SQLiteProjectRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database = SQLiteProjectDatabase(database_path)
        self.corpus = SQLiteCorpusRepository(self.database)
        self.memory = SQLiteMemoryRepository(self.database, self.corpus)

    def create_project(
        self,
        *,
        name: str,
        research_question: str,
        project_id: str | None = None,
        now: datetime | None = None,
    ) -> ResearchProject:
        return self.corpus.create_project(
            name=name,
            research_question=research_question,
            project_id=project_id,
            now=now,
        )

    def get_project(self, project_id: str) -> ResearchProject:
        return self.corpus.get_project(project_id)

    def next_ingestion_version(self, *, project_id: str, paper_id: str) -> int:
        return self.corpus.next_ingestion_version(project_id=project_id, paper_id=paper_id)

    def persist_ingestion(
        self, paper: PaperVersion, evidence_units: Iterable[EvidenceUnit]
    ) -> None:
        self.corpus.persist_ingestion(paper, evidence_units)

    def get_latest_paper(self, *, project_id: str, paper_id: str) -> PaperVersion:
        return self.corpus.get_latest_paper(project_id=project_id, paper_id=paper_id)

    def list_latest_papers(self, project_id: str) -> tuple[PaperVersion, ...]:
        return self.corpus.list_latest_papers(project_id)

    def list_evidence_units(
        self, project_id: str, *, paper_ids: Iterable[str] | None = None
    ) -> tuple[EvidenceUnit, ...]:
        return self.corpus.list_evidence_units(project_id, paper_ids=paper_ids)

    def get_evidence_units_by_id(
        self, project_id: str, unit_ids: Iterable[str]
    ) -> tuple[EvidenceUnit, ...]:
        return self.corpus.get_evidence_units_by_id(project_id, unit_ids)

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
        return self.memory.propose_memory(
            project_id=project_id,
            scope=scope,
            category=category,
            content=content,
            evidence_unit_ids=evidence_unit_ids,
            memory_id=memory_id,
            now=now,
        )

    def review_memory(
        self,
        memory_id: str,
        *,
        approve: bool,
        note: str | None = None,
        now: datetime | None = None,
    ) -> ProjectMemoryEntry:
        return self.memory.review_memory(memory_id, approve=approve, note=note, now=now)

    def list_memory(
        self, project_id: str, *, include_pending: bool = False
    ) -> tuple[ProjectMemoryEntry, ...]:
        return self.memory.list_memory(project_id, include_pending=include_pending)


__all__ = [
    "MemoryEntryNotFoundError",
    "PaperNotFoundError",
    "ProjectNotFoundError",
    "SQLiteProjectRepository",
    "utc_now",
]

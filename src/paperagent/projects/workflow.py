from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from paperagent.projects.ingestion import PaperIngestionService
from paperagent.projects.models import (
    IngestionResult,
    MemoryCategory,
    MemoryScope,
    ProjectMemoryEntry,
    ResearchProject,
    SearchHit,
    TailoringPlan,
)
from paperagent.projects.rag import HybridAcademicRetriever
from paperagent.projects.repository import SQLiteProjectRepository
from paperagent.projects.tailoring import EvidenceBoundTailoringService


class MemoryRAGWorkflow:
    def __init__(self, database_path: str | Path) -> None:
        self.repository = SQLiteProjectRepository(database_path)
        self.ingestion = PaperIngestionService(self.repository)
        self.retriever = HybridAcademicRetriever(self.repository)
        self.tailoring = EvidenceBoundTailoringService(self.repository, self.retriever)

    def create_project(self, *, name: str, research_question: str) -> ResearchProject:
        return self.repository.create_project(name=name, research_question=research_question)

    def ingest_paper(
        self,
        *,
        project_id: str,
        path: str | Path,
        title: str | None = None,
        paper_id: str | None = None,
    ) -> IngestionResult:
        return self.ingestion.ingest_file(
            project_id=project_id,
            path=path,
            title=title,
            paper_id=paper_id,
        )

    def query(
        self,
        *,
        project_id: str,
        query: str,
        limit: int = 8,
        paper_ids: Iterable[str] | None = None,
    ) -> tuple[SearchHit, ...]:
        return self.retriever.search(
            project_id=project_id,
            query=query,
            limit=limit,
            paper_ids=paper_ids,
        )

    def propose_memory(
        self,
        *,
        project_id: str,
        scope: MemoryScope,
        category: MemoryCategory,
        content: str,
        evidence_unit_ids: Iterable[str] = (),
    ) -> ProjectMemoryEntry:
        return self.repository.propose_memory(
            project_id=project_id,
            scope=scope,
            category=category,
            content=content,
            evidence_unit_ids=evidence_unit_ids,
        )

    def review_memory(
        self,
        memory_id: str,
        *,
        approve: bool,
        note: str | None = None,
    ) -> ProjectMemoryEntry:
        return self.repository.review_memory(
            memory_id,
            approve=approve,
            note=note,
        )

    def design_tailoring_plan(
        self,
        *,
        project_id: str,
        hypothesis: str,
        baseline_paper_id: str,
        module_paper_ids: Iterable[str],
        evidence_query: str | None = None,
    ) -> TailoringPlan:
        return self.tailoring.design(
            project_id=project_id,
            hypothesis=hypothesis,
            baseline_paper_id=baseline_paper_id,
            module_paper_ids=module_paper_ids,
            evidence_query=evidence_query,
        )

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from paperagent.projects import (
    MemoryCategory,
    MemoryRAGWorkflow,
    MemoryScope,
    MemoryStatus,
    ProjectNotFoundError,
    TailoringDecision,
)
from paperagent.projects.storage import MemoryEntryNotFoundError


def _paper(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_project_identity_and_empty_corpus_boundaries(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "db.sqlite")
    with pytest.raises(ValueError, match="must not be empty"):
        workflow.create_project(name=" ", research_question="question")

    project = workflow.create_project(name="Project", research_question="Question")
    assert workflow.repository.get_project(project.project_id) == project
    assert workflow.query(project_id=project.project_id, query="anything") == ()
    with pytest.raises(ValueError, match="must not be empty"):
        workflow.query(project_id=project.project_id, query=" ")
    with pytest.raises(ValueError, match="between 1 and 100"):
        workflow.query(project_id=project.project_id, query="test", limit=0)
    with pytest.raises(ProjectNotFoundError):
        workflow.repository.get_project("missing")
    with pytest.raises(sqlite3.IntegrityError):
        workflow.repository.create_project(
            project_id=project.project_id,
            name="Duplicate",
            research_question="Duplicate",
        )


def test_ingestion_infers_title_and_filters_by_paper(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "db.sqlite")
    project = workflow.create_project(name="Corpus", research_question="Question")
    first = workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="first",
        path=_paper(tmp_path / "first.md", "# First paper\n\nAlpha attention method."),
    )
    workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="second",
        path=_paper(tmp_path / "second.txt", "Second paper\n\nBeta regularization method."),
    )
    assert first.paper.title == "First paper"
    hits = workflow.query(
        project_id=project.project_id,
        query="attention",
        paper_ids=("first",),
    )
    assert hits and {hit.unit.paper_id for hit in hits} == {"first"}
    assert (
        workflow.query(
            project_id=project.project_id,
            query="regularization",
            paper_ids=("first",),
        )
        == ()
    )


def test_memory_pending_listing_and_missing_review(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "db.sqlite")
    project = workflow.create_project(name="Memory", research_question="Question")
    proposal = workflow.propose_memory(
        project_id=project.project_id,
        scope=MemoryScope.WORKING,
        category=MemoryCategory.FINDING,
        content="A pending finding",
    )
    assert workflow.repository.list_memory(project.project_id) == ()
    pending = workflow.repository.list_memory(project.project_id, include_pending=True)
    assert pending == (proposal,)
    rejected = workflow.review_memory(proposal.memory_id, approve=False, note="not supported")
    assert rejected.status is MemoryStatus.REJECTED
    assert workflow.repository.list_memory(project.project_id) == ()
    with pytest.raises(MemoryEntryNotFoundError):
        workflow.review_memory("missing", approve=True)


def test_tailoring_blocks_missing_identities_and_evidence(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "db.sqlite")
    project = workflow.create_project(name="Tailoring", research_question="Question")
    missing_baseline = workflow.design_tailoring_plan(
        project_id=project.project_id,
        hypothesis="Improve robustness",
        baseline_paper_id="missing",
        module_paper_ids=("module",),
    )
    assert missing_baseline.decision is TailoringDecision.BLOCKED
    assert missing_baseline.reason_code == "baseline_identity_missing"

    workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="baseline",
        title="Baseline",
        path=_paper(tmp_path / "baseline.txt", "Unrelated baseline content."),
    )
    baseline_no_match = workflow.design_tailoring_plan(
        project_id=project.project_id,
        hypothesis="Improve robustness",
        baseline_paper_id="baseline",
        module_paper_ids=("module",),
        evidence_query="nonexistent-token",
    )
    assert baseline_no_match.reason_code == "baseline_evidence_missing"

    module_missing = workflow.design_tailoring_plan(
        project_id=project.project_id,
        hypothesis="Use baseline content",
        baseline_paper_id="baseline",
        module_paper_ids=("module",),
        evidence_query="baseline content",
    )
    assert module_missing.reason_code == "parallel_module_identity_missing"

    workflow.ingest_paper(
        project_id=project.project_id,
        paper_id="module",
        title="Module",
        path=_paper(tmp_path / "module.txt", "Unrelated module text."),
    )
    module_no_match = workflow.design_tailoring_plan(
        project_id=project.project_id,
        hypothesis="Use baseline content",
        baseline_paper_id="baseline",
        module_paper_ids=("module",),
        evidence_query="baseline content",
    )
    assert module_no_match.reason_code == (
        "module_design_deferred:insufficient_independent_evidence"
    )

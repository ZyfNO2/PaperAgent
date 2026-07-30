from __future__ import annotations

from pathlib import Path

from paperagent.academic import AcademicRAGWorkflow, AcademicRetrievalRequest
from paperagent.academic.project_adapter import ProjectRAGEvidenceSource
from paperagent.projects.workflow import MemoryRAGWorkflow


def test_project_rag_adapter_exposes_locator_aware_text_fallback(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "project.sqlite")
    project = workflow.create_project(name="Demo", research_question="How does ECA work?")
    paper = tmp_path / "eca.md"
    paper.write_text(
        "# ECA-Net\n\n## Method\nEfficient channel attention uses local cross-channel interaction.",
        encoding="utf-8",
    )
    workflow.ingest_paper(
        project_id=project.project_id,
        path=paper,
        paper_id="eca",
        title="ECA-Net",
    )
    source = ProjectRAGEvidenceSource(workflow.repository, workflow.retriever)

    result = AcademicRAGWorkflow(source).run(
        project_id=project.project_id,
        question="Where is channel attention connected in Figure 2?",
        paper_ids=("eca",),
    )

    assert result.sufficiency == "partial"
    assert result.stop_reason == "visual_channel_degraded"
    assert result.ledger.accepted_ids
    entry = result.ledger.entries[0]
    assert entry.locator.paper_id == "eca"
    assert (
        entry.locator.source_hash
        == workflow.repository.get_latest_paper(
            project_id=project.project_id,
            paper_id="eca",
        ).content_sha256
    )


def test_project_rag_adapter_rejects_cross_project_resolve(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "project.sqlite")
    first = workflow.create_project(name="First", research_question="First")
    second = workflow.create_project(name="Second", research_question="Second")
    source = ProjectRAGEvidenceSource(workflow.repository, workflow.retriever)
    request = AcademicRetrievalRequest(
        project_id=first.project_id,
        query="anything",
        original_question="anything",
        kind="method",
        round_kind="primary",
        channels=("lexical",),
    )

    assert source.retrieve(request).sufficiency == "insufficient"
    assert first.project_id != second.project_id

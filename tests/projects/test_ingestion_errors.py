from __future__ import annotations

from pathlib import Path

import pytest

from paperagent.projects import MemoryRAGWorkflow


def test_ingestion_rejects_unsupported_and_empty_files(tmp_path: Path) -> None:
    workflow = MemoryRAGWorkflow(tmp_path / "db.sqlite")
    project = workflow.create_project(name="Errors", research_question="Validate ingestion")
    unsupported = tmp_path / "paper.docx"
    unsupported.write_bytes(b"not a supported format")
    with pytest.raises(ValueError, match="unsupported paper format"):
        workflow.ingest_paper(project_id=project.project_id, path=unsupported)

    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        workflow.ingest_paper(project_id=project.project_id, path=empty)

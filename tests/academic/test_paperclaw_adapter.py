from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("paperclaw", reason="install PaperAgent[paperclaw] on Python 3.12")

import fitz
from paperclaw.academic import (
    AcademicLocator as ClawLocator,
)
from paperclaw.academic import (
    AcademicObject,
    AcademicRuntime,
    BoundingBox,
    EvidenceLocator,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalService,
    RetrievalTrace,
)
from paperclaw.artifacts import FileArtifactStore
from paperclaw.papers import PaperImportRequest, PaperService
from paperclaw.projects import ProjectManifestStore

from paperagent.academic import (
    AcademicArtifactDraft,
    AcademicRetrievalRequest,
    EvidenceBoundClaim,
)
from paperagent.academic.paperclaw_adapter import (
    PaperClawAcademicArtifactSink,
    PaperClawAcademicEvidenceSource,
)
from paperagent.projects.workflow import MemoryRAGWorkflow


def _claw_locator() -> ClawLocator:
    return ClawLocator(
        paper_id="paper-1",
        version_id="version-2",
        object_id="table-3-cell-2-4",
        page_number=7,
        object_type="table_cell",
        source_hash="a" * 64,
        section_path=("Experiments", "Ablation"),
        bounding_box=BoundingBox(10.0, 20.0, 30.0, 40.0),
        paragraph_index=5,
        line_range=(11, 13),
        table_row=2,
        table_column=4,
    )


class FakeAcademicRuntime:
    def __init__(self) -> None:
        self.request = None

    def retrieve(self, request):
        self.request = request
        return RetrievalResult(
            query=request.text,
            candidates=(
                RetrievalCandidate(
                    locator=_claw_locator(),
                    text="F1 = 91.2",
                    channel_scores={"lexical": 0.8, "dense": 0.7, "visual": 0.9},
                    fused_score=0.86,
                    explanation=("weighted_rrf",),
                ),
            ),
            sufficiency="sufficient",
            reasons=("grounded table cell found",),
            trace=RetrievalTrace(
                trace_id="trace-1",
                request_fingerprint="b" * 64,
                index_generation_id="generation-1",
                channels=("lexical", "dense", "visual"),
                model_fingerprints={"visual": "colqwen2:test"},
                rounds_used={"primary": 1, "corrective": 0, "conflict": 0},
                degraded_channels=(),
                stop_reason="sufficient",
            ),
        )

    @staticmethod
    def evidence_bundle(result):
        return SimpleNamespace(
            schema_version="academic.v1",
            candidates=result.candidates,
            sufficiency=result.sufficiency,
            reasons=result.reasons,
            trace=result.trace,
        )

    def resolve(self, locator):
        assert locator == _claw_locator()
        return AcademicObject(
            object_id=locator.object_id,
            object_type="table_cell",
            reading_order=9,
            locator=locator,
            text="F1 = 91.2",
        )


def test_paperclaw_evidence_adapter_preserves_canonical_locator_and_trace() -> None:
    runtime = FakeAcademicRuntime()
    source = PaperClawAcademicEvidenceSource(runtime)

    result = source.retrieve(
        AcademicRetrievalRequest(
            project_id="project-1",
            query="What is the F1 in Table 3?",
            original_question="What is the F1 in Table 3?",
            kind="table",
            round_kind="primary",
            channels=("exact", "lexical", "dense", "visual"),
            paper_ids=("paper-1",),
            object_types=("table_cell",),
        )
    )
    resolved = source.resolve(result.candidates[0].locator)

    assert runtime.request.channels == ("exact", "lexical", "dense", "visual")
    assert result.trace_id == "trace-1"
    assert result.candidates[0].locator.table_row == 2
    assert result.candidates[0].locator.bounding_box == (10.0, 20.0, 30.0, 40.0)
    assert resolved.locator == result.candidates[0].locator
    assert resolved.text == "F1 = 91.2"


def test_paperclaw_artifact_sink_persists_append_only_review_history(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(tmp_path / "artifacts")
    sink = PaperClawAcademicArtifactSink(store)
    draft = AcademicArtifactDraft(
        artifact_type="method_draft",
        title="Method draft",
        project_id="project-1",
        summary="Evidence-bound draft.",
        evidence_ids=("paper-1:table-3-cell-2-4",),
        claims=(
            EvidenceBoundClaim(
                text="F1 is 91.2.",
                evidence_ids=("paper-1:table-3-cell-2-4",),
            ),
        ),
    )

    created = sink.create_draft(draft)
    approved = sink.review(created.artifact_id, decision="approved", note="Checked.")
    final = sink.finalize(created.artifact_id)
    bundle = store.get_bundle(created.artifact_id)

    assert [revision.revision_number for revision in bundle.revisions] == [1, 2, 3]
    assert [created.state, approved.state, final.state] == [
        "draft",
        "approved",
        "final",
    ]


def test_memory_rag_workflow_accepts_paperclaw_adapters(
    tmp_path: Path,
) -> None:
    source = PaperClawAcademicEvidenceSource(FakeAcademicRuntime())
    sink = PaperClawAcademicArtifactSink(FileArtifactStore(tmp_path / "artifacts"))
    workflow = MemoryRAGWorkflow(
        tmp_path / "paperagent.sqlite3",
        academic_evidence_source=source,
        academic_artifact_sink=sink,
    )

    result = workflow.academic_query(
        project_id="project-1",
        question="What is the F1 in Table 3?",
        paper_ids=("paper-1",),
    )

    assert result.sufficiency == "sufficient"
    assert result.ledger.accepted_ids == ("paper-1:version-2:table-3-cell-2-4",)


def test_real_paperclaw_runtime_drives_paperagent_evidence_workflow(
    tmp_path: Path,
) -> None:
    manifest = ProjectManifestStore(tmp_path).initialize("Cross-repo Academic RAG")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "DOI 10.1234/ABC.Def")
    page.insert_text((72, 100), "Concrete crack F1 is 91.2.")
    source_pdf = tmp_path / "paper.pdf"
    document.save(source_pdf)
    document.close()
    papers = PaperService.for_workspace(tmp_path, project_id=manifest.project_id)
    imported = papers.import_paper(PaperImportRequest(manifest.project_id, source_pdf))
    runtime = AcademicRuntime.for_workspace(tmp_path, manifest.project_id)
    runtime.parse_paper(imported.paper.paper_id)
    runtime.build_index()
    evidence_source = PaperClawAcademicEvidenceSource(RetrievalService(runtime))
    workflow = MemoryRAGWorkflow(
        tmp_path / "paperagent.sqlite3",
        academic_evidence_source=evidence_source,
        academic_artifact_sink=PaperClawAcademicArtifactSink(
            FileArtifactStore(tmp_path / ".paperclaw" / "paperagent-artifacts")
        ),
    )

    result = workflow.academic_query(
        project_id=manifest.project_id,
        question="Find DOI 10.1234/ABC.Def",
        paper_ids=(imported.paper.paper_id,),
    )

    assert result.sufficiency == "sufficient"
    assert len(result.ledger.accepted_ids) == 1
    locator = result.ledger.entries[0].locator
    resolved = runtime.resolve(
        EvidenceLocator(
            paper_id=locator.paper_id,
            version_id=locator.version_id,
            object_id=locator.object_id,
            page_number=locator.page_number,
            object_type=locator.object_type,
            source_hash=locator.source_hash,
            section_path=locator.section_path,
            bounding_box=(
                BoundingBox(*locator.bounding_box) if locator.bounding_box is not None else None
            ),
            paragraph_index=locator.paragraph_index,
            line_range=locator.line_range,
            table_row=locator.table_row,
            table_column=locator.table_column,
        )
    )
    assert any(asset.kind == "page" for asset in resolved.assets)
    page_asset = next(asset for asset in resolved.assets if asset.kind == "page")
    page_bytes = runtime.read_asset(resolved.locator, page_asset.asset_hash)
    assert page_bytes.startswith(b"\x89PNG")
    assert hashlib.sha256(page_bytes).hexdigest() == page_asset.asset_hash

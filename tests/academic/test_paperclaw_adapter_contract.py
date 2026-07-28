from __future__ import annotations

import hashlib
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from paperagent.academic import (
    AcademicArtifactDraft,
    AcademicRetrievalRequest,
    EvidenceBoundClaim,
    paperclaw_adapter,
)
from paperagent.academic.paperclaw_adapter import (
    PaperClawAcademicArtifactSink,
    PaperClawAcademicEvidenceSource,
)


@dataclass(frozen=True)
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class Locator:
    paper_id: str
    version_id: str
    object_id: str
    page_number: int
    object_type: str
    source_hash: str
    section_path: tuple[str, ...] = ()
    bounding_box: BoundingBox | None = None
    paragraph_index: int | None = None
    line_range: tuple[int, int] | None = None
    table_row: int | None = None
    table_column: int | None = None
    schema_version: str = "academic.v1"


class KeywordRecord:
    def __init__(self, **values: object) -> None:
        self.__dict__.update(values)


class FakeRuntime:
    def __init__(self) -> None:
        self.request = None
        self.locator = Locator(
            "paper-1",
            "version-1",
            "cell-1",
            4,
            "table_cell",
            "a" * 64,
            ("Results",),
            BoundingBox(1.0, 2.0, 3.0, 4.0),
            table_row=2,
            table_column=3,
        )

    def retrieve(self, request):
        self.request = request
        candidate = SimpleNamespace(
            locator=self.locator,
            text="F1 = 91.2",
            channel_scores={"exact": 1.0, "lexical": 0.8, "unknown": 9.0},
            fused_score=1.0,
            explanation=("exact identifier match",),
            provenance="extracted",
        )
        trace = SimpleNamespace(
            trace_id="trace-1",
            degraded_channels=("visual", "unknown"),
            stop_reason="sufficient",
        )
        return SimpleNamespace(
            candidates=(candidate,),
            sufficiency="sufficient",
            reasons=("matched",),
            trace=trace,
        )

    def resolve(self, locator):
        return SimpleNamespace(
            locator=locator,
            text="F1 = 91.2",
            provenance="extracted",
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


class FakeStore:
    def __init__(self) -> None:
        self.contents: dict[str, list[bytes]] = {}

    def create_artifact(self, **kwargs):
        artifact_id = "artifact-1"
        content = kwargs["content"]
        self.contents[artifact_id] = [content]
        return (
            SimpleNamespace(
                artifact_id=artifact_id,
                artifact_type=kwargs["artifact_type"],
            ),
            self._revision(artifact_id),
            True,
        )

    def add_revision(self, artifact_id, **kwargs):
        self.contents[artifact_id].append(kwargs["content"])
        return self._revision(artifact_id), True

    def read_revision(self, artifact_id, revision_number=None):
        number = revision_number or len(self.contents[artifact_id])
        return self.contents[artifact_id][number - 1]

    def _revision(self, artifact_id):
        content = self.contents[artifact_id][-1]
        return SimpleNamespace(
            revision_number=len(self.contents[artifact_id]),
            content_hash=hashlib.sha256(content).hexdigest(),
        )


@pytest.fixture(autouse=True)
def canonical_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    academic = SimpleNamespace(
        EvidenceLocator=Locator,
        BoundingBox=BoundingBox,
        RetrievalBudget=KeywordRecord,
        RetrievalRequest=KeywordRecord,
    )
    artifacts = SimpleNamespace(ArtifactSourceLinks=KeywordRecord)
    monkeypatch.setattr(paperclaw_adapter, "_academic_module", lambda: academic)
    monkeypatch.setattr(paperclaw_adapter, "_artifact_module", lambda: artifacts)


def test_structural_evidence_adapter_preserves_exact_locator_and_degradation() -> None:
    runtime = FakeRuntime()
    source = PaperClawAcademicEvidenceSource(runtime)

    result = source.retrieve(
        AcademicRetrievalRequest(
            project_id="project-1",
            query="Find DOI 10.1234/ABC.Def",
            original_question="Find DOI 10.1234/ABC.Def",
            kind="identity",
            round_kind="primary",
            channels=("exact", "lexical", "visual"),
        )
    )
    resolved = source.resolve(result.candidates[0].locator)

    assert runtime.request.channels == ("exact", "lexical", "visual")
    assert result.degraded_channels == ("visual",)
    assert result.candidates[0].channel_scores == {"exact": 1.0, "lexical": 0.8}
    assert result.candidates[0].locator.table_row == 2
    assert resolved.text == "F1 = 91.2"


def test_structural_artifact_adapter_is_append_only_and_fail_closed() -> None:
    store = FakeStore()
    sink = PaperClawAcademicArtifactSink(store)
    draft = AcademicArtifactDraft(
        artifact_type="method_draft",
        title="Method",
        project_id="project-1",
        summary="Evidence-bound.",
        evidence_ids=("evidence-1",),
        claims=(EvidenceBoundClaim(text="Supported.", evidence_ids=("evidence-1",)),),
    )

    created = sink.create_draft(draft)
    approved = sink.review(created.artifact_id, decision="approved", note="Checked")
    final = sink.finalize(created.artifact_id)

    assert [created.revision_number, approved.revision_number, final.revision_number] == [
        1,
        2,
        3,
    ]
    with pytest.raises(ValueError, match="draft"):
        sink.review(created.artifact_id, decision="rejected", note="late")

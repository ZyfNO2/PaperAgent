from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from paperagent.academic import (
    AcademicArtifactCoordinator,
    AcademicArtifactDraft,
    AcademicArtifactRevision,
    AcademicCandidate,
    AcademicEvidenceSource,
    AcademicLocator,
    AcademicRAGWorkflow,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
    InMemoryAcademicArtifactSink,
)


def _paper_candidate(paper_id: str, text: str) -> AcademicCandidate:
    return AcademicCandidate(
        evidence_id=f"{paper_id}:paragraph:1",
        locator=AcademicLocator(
            schema_version="academic.v1",
            paper_id=paper_id,
            version_id=f"{paper_id}-v1",
            object_id=f"{paper_id}-paragraph-1",
            page_number=3,
            object_type="paragraph",
            source_hash=("a" if paper_id == "baseline" else "b") * 64,
        ),
        text=text,
        score=0.9,
        provenance="extracted",
    )


@dataclass
class PerPaperEvidenceSource(AcademicEvidenceSource):
    candidates: dict[str, AcademicCandidate]
    requests: list[AcademicRetrievalRequest] = field(default_factory=list)

    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult:
        self.requests.append(request)
        paper_id = request.paper_ids[0]
        candidate = self.candidates[paper_id]
        return AcademicRetrievalResult(
            candidates=(candidate,),
            sufficiency="sufficient",
            reasons=("paper-scoped evidence",),
            degraded_channels=(),
            conflict_detected=False,
            trace_id=f"trace-{paper_id}",
        )

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        return self.candidates[locator.paper_id]


def test_cross_paper_tailoring_creates_complete_evidence_bound_draft_set() -> None:
    source = PerPaperEvidenceSource(
        {
            "baseline": _paper_candidate("baseline", "Baseline architecture and loss."),
            "module": _paper_candidate("module", "Module mechanism and ablation."),
        }
    )
    sink = InMemoryAcademicArtifactSink()
    coordinator = AcademicArtifactCoordinator(AcademicRAGWorkflow(source), sink)

    result = coordinator.create_tailoring_drafts(
        project_id="project-1",
        hypothesis="Add the module to the baseline.",
        baseline_paper_id="baseline",
        module_paper_ids=("module",),
    )

    assert result.decision == "REVISE"
    assert {revision.artifact_type for revision in result.revisions} == {
        "evidence_bundle",
        "paper_comparison",
        "baseline_card",
        "module_card",
        "compatibility_matrix",
        "experiment_matrix",
        "method_draft",
        "review_report",
    }
    accepted = {"baseline:paragraph:1", "module:paragraph:1"}
    for revision in result.revisions:
        draft = sink.read(revision.artifact_id)
        assert draft.state == "draft"
        assert set(draft.evidence_ids) <= accepted
        assert all(set(claim.evidence_ids) <= accepted for claim in draft.claims)


def test_artifact_review_is_append_only_draft_approve_final() -> None:
    sink = InMemoryAcademicArtifactSink()
    draft = AcademicArtifactDraft(
        artifact_type="method_draft",
        title="Method draft",
        project_id="project-1",
        summary="Evidence-bound draft.",
        evidence_ids=("evidence-1",),
        claims=(),
    )
    created = sink.create_draft(draft)
    approved = sink.review(created.artifact_id, decision="approved", note="Checked.")
    final = sink.finalize(created.artifact_id)

    assert [item.state for item in sink.history(created.artifact_id)] == [
        "draft",
        "approved",
        "final",
    ]
    assert created.revision_number == 1
    assert approved.revision_number == 2
    assert final.revision_number == 3

    with pytest.raises(ValueError, match="final"):
        sink.review(created.artifact_id, decision="rejected", note="Too late.")


def test_final_revision_requires_prior_approval() -> None:
    sink = InMemoryAcademicArtifactSink()
    created: AcademicArtifactRevision = sink.create_draft(
        AcademicArtifactDraft(
            artifact_type="compatibility_matrix",
            title="Compatibility",
            project_id="project-1",
            summary="Pending review.",
            evidence_ids=(),
            claims=(),
        )
    )

    with pytest.raises(ValueError, match="approved"):
        sink.finalize(created.artifact_id)

"""Re4.3: Evidence-bound schema tests."""
from __future__ import annotations


from apps.api.app.services.agents.graph.schemas.evidence_schema import (
    BindingValidationResult,
    EvidenceSnippet,
    InnovationPoint,
    NarrativeRevision,
    WorkPackage,
)


class TestInnovationPoint:
    def test_has_evidence_with_candidate_ids(self) -> None:
        ip = InnovationPoint(description="test", candidate_ids=["p1"])
        assert ip.has_evidence()

    def test_has_evidence_without_candidates(self) -> None:
        ip = InnovationPoint(description="test")
        assert not ip.has_evidence()

    def test_needs_evidence_status(self) -> None:
        ip = InnovationPoint(description="test", candidate_ids=[])
        assert not ip.has_evidence()

    def test_scores_in_range(self) -> None:
        ip = InnovationPoint(
            description="test",
            novelty_score=8.5,
            feasibility_score=7.0,
            evidence_score=6.0,
        )
        assert 0 <= ip.novelty_score <= 10

    def test_backward_compatible_with_legacy_fields(self) -> None:
        ip = InnovationPoint(
            description="test",
            baseline_used="YOLOv8",
            stitched_modules=["attention"],
            evidence_ref="YOLOv8 paper",
        )
        assert ip.baseline_used == "YOLOv8"
        assert ip.evidence_ref == "YOLOv8 paper"

    def test_evidence_snippets(self) -> None:
        snip = EvidenceSnippet(candidate_id="p1", snippet="YOLO achieves 67 mAP")
        ip = InnovationPoint(description="test", evidence_snippets=[snip])
        assert ip.has_evidence()
        assert ip.evidence_snippets[0].candidate_id == "p1"

    def test_status_defaults_to_pending(self) -> None:
        ip = InnovationPoint(description="test")
        assert ip.status == "pending"


class TestNarrativeRevision:
    def test_initial_revision(self) -> None:
        rev = NarrativeRevision(revision_id="rev-0", narrative_summary="initial")
        assert rev.parent_revision_id is None
        assert rev.revision_source == "initial"

    def test_devils_advocate_revision(self) -> None:
        rev = NarrativeRevision(
            revision_id="rev-1",
            parent_revision_id="rev-0",
            revision_reason="D2 evidence insufficient",
            revision_source="devils_advocate",
        )
        assert rev.parent_revision_id == "rev-0"
        assert rev.revision_source == "devils_advocate"

    def test_diff_is_optional(self) -> None:
        rev = NarrativeRevision(revision_id="rev-0")
        assert rev.diff is None


class TestWorkPackage:
    def test_package_id_deterministic(self) -> None:
        wp = WorkPackage(title="复现 YOLOv8 基线")
        assert wp.package_id.startswith("wp-")

    def test_package_id_consistent(self) -> None:
        wp1 = WorkPackage(title="复现 YOLOv8 基线")
        wp2 = WorkPackage(title="复现 YOLOv8 基线")
        assert wp1.package_id == wp2.package_id

    def test_prerequisite_ids(self) -> None:
        wp1 = WorkPackage(title="A")
        wp2 = WorkPackage(title="B", prerequisite_ids=[wp1.package_id])
        assert wp1.package_id in wp2.prerequisite_ids

    def test_backward_compatible(self) -> None:
        wp = WorkPackage(
            title="test",
            baseline="YOLOv8",
            improved_module_source="attention",
            data_source="NEU-DET",
        )
        assert wp.baseline == "YOLOv8"

    def test_new_fields_default(self) -> None:
        wp = WorkPackage(title="test")
        assert wp.objective is None
        assert wp.method is None
        assert wp.deliverable is None
        assert wp.effort is None
        assert wp.prerequisite_ids == []
        assert wp.bound_candidate_ids == []
        assert wp.status == "pending"


class TestBindingValidationResult:
    def test_default_valid(self) -> None:
        r = BindingValidationResult(valid=True)
        assert r.valid
        assert r.issues == []
        assert r.orphan_packages == []

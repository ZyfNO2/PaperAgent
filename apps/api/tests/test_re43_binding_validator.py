"""Re4.3: Binding validator tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.validators.binding_validator import (
    mark_stale_derived_items,
    run_full_validation,
    validate_innovations,
    validate_narrative,
    validate_work_packages,
)


class TestBindingValidator:
    def test_innovation_with_valid_candidate_id(self) -> None:
        """Innovation referencing a real paper should pass."""
        evidence_index = {"yolov8": {"title": "YOLOv8"}}
        innovations = [{"description": "improve YOLOv8", "candidate_ids": ["yolov8"]}]
        validated, issues = validate_innovations(innovations, evidence_index)
        assert len(issues) == 0
        assert validated[0].status != "needs_evidence"

    def test_innovation_without_evidence_marked_needs_evidence(self) -> None:
        """Innovation with no candidate_ids should be marked needs_evidence."""
        evidence_index: dict[str, dict] = {}
        innovations = [{"description": "novel approach"}]
        validated, issues = validate_innovations(innovations, evidence_index)
        assert validated[0].status == "needs_evidence"
        assert any(i["type"] == "innovation_no_evidence" for i in issues)

    def test_innovation_dangling_ref_detected(self) -> None:
        """Innovation referencing unknown candidate should produce issue."""
        evidence_index: dict[str, dict] = {}
        innovations = [{"description": "test", "candidate_ids": ["nonexistent"]}]
        validated, issues = validate_innovations(innovations, evidence_index)
        assert validated[0].status == "needs_evidence"
        assert any(i["type"] == "innovation_dangling_ref" for i in issues)

    def test_work_package_with_dangling_baseline(self) -> None:
        """Work package referencing non-existent baseline should produce issue."""
        evidence_index: dict[str, dict] = {}
        packages = [{"title": "WP1", "baseline": "nonexistent_model"}]
        validated, issues, orphans = validate_work_packages(packages, evidence_index)
        assert any(i["type"] == "work_package_dangling_ref" for i in issues)

    def test_orphan_prerequisite_detected(self) -> None:
        """Work package with prerequisite_ids pointing to non-existent package."""
        evidence_index: dict[str, dict] = {}
        packages = [{"title": "WP1", "prerequisite_ids": ["wp-nonexistent"]}]
        validated, issues, orphan_ids = validate_work_packages(packages, evidence_index)
        assert len(orphan_ids) > 0
        assert any(i["type"] == "work_package_orphan_prerequisite" for i in issues)

    def test_narrative_dangling_ref_detected(self) -> None:
        """Narrative referencing unknown paper should produce issue."""
        from apps.api.app.services.agents.graph.schemas.evidence_schema import InnovationPoint
        innovations = [InnovationPoint(description="test", candidate_ids=["real_paper"])]
        narrative = {
            "three_problems": [
                {"problem": "test", "from_paper": "nonexistent_paper"},
            ],
        }
        issues = validate_narrative(narrative, innovations)
        assert any(i["type"] == "narrative_dangling_ref" for i in issues)

    def test_stale_marking_on_evidence_change(self) -> None:
        """When evidence changes, derived items should be marked stale."""
        state = {
            "innovation_points": [
                {"description": "test", "candidate_ids": ["paper_a"]},
            ],
            "work_packages": [
                {"title": "WP1", "bound_candidate_ids": ["paper_b"]},
            ],
        }
        stale = mark_stale_derived_items(state, {"paper_a", "paper_b"})
        assert "innovation_0" in stale
        assert "work_package_0" in stale
        assert state["innovation_points"][0]["status"] == "stale"

    def test_full_validation_aggregates_all(self) -> None:
        """run_full_validation should aggregate innovation + work_package + narrative issues."""
        state = {
            "verified_papers": [{"title": "YOLOv8"}],
            "innovation_points": [{"description": "no evidence"}],
            "work_packages": [{"title": "WP1", "baseline": "nonexistent"}],
            "research_narrative": {
                "three_problems": [{"problem": "x", "from_paper": "unknown"}],
            },
        }
        result = run_full_validation(state)
        assert not result.valid
        assert len(result.issues) > 0
        assert len(result.needs_evidence_items) > 0

    def test_full_validation_passes_on_valid_state(self) -> None:
        """run_full_validation should pass when all bindings are valid."""
        state = {
            "verified_papers": [{"title": "YOLOv8", "paper_id": "yolov8"}],
            "innovation_points": [{"description": "test", "candidate_ids": ["yolov8"]}],
            "work_packages": [{"title": "WP1", "baseline": "yolov8"}],
            "research_narrative": {"three_problems": []},
        }
        result = run_full_validation(state)
        assert result.valid

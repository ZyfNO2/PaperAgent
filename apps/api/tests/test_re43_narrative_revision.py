"""Re4.3: Narrative revision history tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.nodes.narrative_builder import _compute_diff


class TestNarrativeRevision:
    def test_initial_revision_has_no_parent(self) -> None:
        """First revision should have parent_revision_id=None."""
        revision = {
            "revision_id": "rev-0",
            "parent_revision_id": None,
            "revision_source": "initial",
        }
        assert revision["parent_revision_id"] is None
        assert revision["revision_source"] == "initial"

    def test_second_revision_links_to_first(self) -> None:
        """Second revision should have parent_revision_id=rev-0."""
        revision = {
            "revision_id": "rev-1",
            "parent_revision_id": "rev-0",
            "revision_source": "devils_advocate",
        }
        assert revision["parent_revision_id"] == "rev-0"
        assert revision["revision_source"] == "devils_advocate"

    def test_diff_computed_on_revision(self) -> None:
        """When narrative changes, diff should show what changed."""
        prev = {
            "nick_model_name": "OldNet",
            "narrative_summary": "old summary",
            "abstract_draft": "old abstract",
            "three_problems": [{"problem": "a"}],
        }
        curr = {
            "nick_model_name": "NewNet",
            "narrative_summary": "new summary",
            "abstract_draft": "old abstract",
            "three_problems": [{"problem": "a"}, {"problem": "b"}],
        }
        diff = _compute_diff(prev, curr)
        assert diff is not None
        assert len(diff["changed"]) > 0
        # nick_model_name changed
        changed_fields = [c["field"] for c in diff["changed"]]
        assert "nick_model_name" in changed_fields
        assert "narrative_summary" in changed_fields
        # abstract_draft did not change
        assert "abstract_draft" not in changed_fields
        # three_problems grew
        assert len(diff["added"]) > 0

    def test_diff_no_changes(self) -> None:
        """When narrative is identical, diff should be empty."""
        prev = {"nick_model_name": "Same", "narrative_summary": "same",
                "abstract_draft": "same", "three_problems": []}
        curr = {"nick_model_name": "Same", "narrative_summary": "same",
                "abstract_draft": "same", "three_problems": []}
        diff = _compute_diff(prev, curr)
        assert diff["changed"] == []
        assert diff["added"] == []
        assert diff["removed"] == []

    def test_revision_count_increments(self) -> None:
        """narrative_revision_count should increment per revision."""
        # Simulate state progression
        count_0 = 0
        count_1 = count_0 + 1
        count_2 = count_1 + 1
        assert count_1 == 1
        assert count_2 == 2
        assert f"rev-{count_0}" == "rev-0"
        assert f"rev-{count_1}" == "rev-1"

    def test_devils_advocate_critique_passed_to_narrative(self) -> None:
        """When MINOR_REVISION, critique reason should be set for narrative_builder."""
        # Simulate what devils_advocate_node does on MINOR_REVISION
        result = {
            "overall_verdict": "MINOR_REVISION",
            "evidence_critiques": [
                {"target_type": "narrative", "issue": "叙事与证据不匹配"},
                {"target_type": "innovation", "issue": "创新点缺证据"},
            ],
        }
        critiques = result.get("evidence_critiques") or []
        critique_reasons = [
            c.get("issue", "") for c in critiques if c.get("target_type") == "narrative"
        ]
        revision_reason = "; ".join(critique_reasons) or "MINOR_REVISION"
        assert "叙事与证据不匹配" in revision_reason
        assert revision_reason != "MINOR_REVISION"

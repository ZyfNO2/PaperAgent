"""Re7.6 D-09: Novelty Draft Generator tests."""
from __future__ import annotations

import pytest


class TestNoveltyDraftNode:
    """Test the novelty_draft_node function."""

    def test_no_innovation_points_returns_empty(self):
        """When no innovation points, should return empty drafts."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import novelty_draft_node

        state = {
            "topic": "test topic",
            "innovation_points": [],
            "evidence_contexts": [],
        }
        result = novelty_draft_node(state)
        assert result["novelty_drafts"] == []
        assert len(result["trace_events"]) == 1

    def test_heuristic_draft_generation(self):
        """Heuristic fallback should produce P-M-I structured drafts."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import _heuristic_draft

        state = {
            "innovation_points": [
                {
                    "description": "在ViT基础上引入注意力机制",
                    "baseline_used": "ViT",
                    "stitched_modules": ["CBAM"],
                    "candidate_ids": ["ev-0", "ev-1", "ev-2"],
                }
            ],
            "evidence_contexts": [
                {"candidate_id": "ev-0", "snippet": "paper about ViT"},
                {"candidate_id": "ev-1", "snippet": "paper about CBAM"},
                {"candidate_id": "ev-2", "snippet": "paper about attention"},
            ],
            "baseline_candidates": [{"title": "ViT paper"}],
        }
        drafts = _heuristic_draft(state)
        assert len(drafts) >= 1
        d = drafts[0]
        assert "problem" in d
        assert "method" in d
        assert "insight" in d
        assert d["status"] in ("draft", "needs_evidence")

    def test_never_auto_accepted(self):
        """Drafts must never have status 'accepted'."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import parse_draft_output

        raw = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "gap",
                    "method": "approach",
                    "insight": "finding",
                    "scope": "scope",
                    "evidence_ids": ["ev-0", "ev-1", "ev-2"],
                    "status": "accepted",  # should be downgraded
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        state = {
            "evidence_contexts": [
                {"candidate_id": "ev-0"},
                {"candidate_id": "ev-1"},
                {"candidate_id": "ev-2"},
            ],
        }
        drafts = parse_draft_output(raw, state)
        assert drafts[0]["status"] == "needs_evidence"

    def test_evidence_binding_filtered(self):
        """Evidence IDs not in evidence_contexts should be filtered out."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import parse_draft_output

        raw = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "gap",
                    "method": "approach",
                    "insight": "finding",
                    "scope": "scope",
                    "evidence_ids": ["ev-0", "ev-1", "fake-id"],
                    "status": "draft",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        state = {
            "evidence_contexts": [
                {"candidate_id": "ev-0"},
                {"candidate_id": "ev-1"},
            ],
        }
        drafts = parse_draft_output(raw, state)
        assert "fake-id" not in drafts[0]["evidence_ids"]
        assert "ev-0" in drafts[0]["evidence_ids"]
        assert "ev-1" in drafts[0]["evidence_ids"]

    def test_pseudo_innovation_risks_detected(self):
        """Performance-only insights should be flagged."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import _heuristic_draft

        state = {
            "innovation_points": [
                {
                    "description": "使用新的注意力机制",
                    "baseline_used": "ResNet",
                    "stitched_modules": ["SENet"],
                    "stitching_plan": "准确率提高了5%，outperforms SOTA",
                    "candidate_ids": ["ev-0"],
                }
            ],
            "evidence_contexts": [{"candidate_id": "ev-0"}],
            "baseline_candidates": [{"title": "ResNet"}],
        }
        drafts = _heuristic_draft(state)
        risks = drafts[0].get("pseudo_innovation_risks", [])
        assert "performance_only" in risks

    def test_first_claim_downgrade(self):
        """NoveltyCandidate schema should downgrade first claims."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        candidate = NoveltyCandidate(
            candidate_id="nd-001",
            problem="首次提出这个方法",
            method="approach",
            insight="insight",
            evidence_ids=["ev-0", "ev-1", "ev-2"],
            status="draft",
        )
        assert candidate.status == "needs_literature_verification"
        assert "first_claim_unsupported" in candidate.pseudo_innovation_risks

    def test_performance_only_insight_downgrade(self):
        """Insights that are just performance numbers should be downgraded."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        candidate = NoveltyCandidate(
            candidate_id="nd-001",
            problem="gap",
            method="approach",
            insight="F1 提高了 5%, accuracy 达到 95%, outperforms SOTA",
            evidence_ids=["ev-0", "ev-1", "ev-2"],
            status="draft",
        )
        assert candidate.status == "needs_evidence"

    def test_accepted_requires_3_evidence(self):
        """Accepted status requires at least 3 evidence IDs."""
        from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyCandidate

        with pytest.raises(ValueError, match="at least 3 evidence_ids"):
            NoveltyCandidate(
                candidate_id="nd-001",
                problem="gap",
                method="approach",
                insight="insight",
                evidence_ids=["ev-0"],
                status="accepted",
            )

    def test_node_returns_trace_event(self):
        """Node should always return a trace_events list."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import novelty_draft_node

        state = {
            "topic": "test",
            "innovation_points": [],
            "evidence_contexts": [],
        }
        result = novelty_draft_node(state)
        assert "trace_events" in result
        assert isinstance(result["trace_events"], list)
        assert len(result["trace_events"]) == 1
        assert result["trace_events"][0]["node"] == "novelty_draft"

    def test_drafts_have_pmi_structure(self):
        """All drafts should have problem, method, insight fields."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import _heuristic_draft

        state = {
            "innovation_points": [
                {
                    "description": "test",
                    "baseline_used": "Base",
                    "stitched_modules": ["Mod"],
                    "candidate_ids": ["ev-0", "ev-1", "ev-2"],
                }
            ],
            "evidence_contexts": [
                {"candidate_id": f"ev-{i}"} for i in range(3)
            ],
            "baseline_candidates": [{"title": "Base"}],
        }
        drafts = _heuristic_draft(state)
        for d in drafts:
            assert "problem" in d
            assert "method" in d
            assert "insight" in d
            assert "scope" in d
            assert "evidence_ids" in d
            assert "status" in d
            assert "pseudo_innovation_risks" in d

    def test_unbound_evidence_flagged(self):
        """Evidence IDs not in contexts should add a risk flag."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import parse_draft_output

        raw = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": "gap",
                    "method": "approach",
                    "insight": "insight",
                    "scope": "scope",
                    "evidence_ids": ["ev-0", "fake-1"],
                    "status": "draft",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        state = {
            "evidence_contexts": [{"candidate_id": "ev-0"}],
        }
        drafts = parse_draft_output(raw, state)
        risks = drafts[0].get("pseudo_innovation_risks", [])
        assert any("unbound" in r for r in risks)

    def test_parse_draft_coerces_list_insight_to_str(self):
        """Re7.7: LLM may return insight/method/problem as a list (observed
        on XD-10). parse_draft_output should coerce to string so the
        NoveltyCandidate validator's .lower() call doesn't crash with
        AttributeError: 'list' object has no attribute 'lower'."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import parse_draft_output

        raw = {
            "novelty_drafts": [
                {
                    "candidate_id": "nd-001",
                    "problem": ["gap1", "gap2"],          # list, should be coerced
                    "method": {"approach": "mod"},        # dict, should be coerced
                    "insight": ["finding1", "finding2"],  # list, should be coerced
                    "scope": "",
                    "evidence_ids": ["ev-0", "ev-1", "ev-2"],
                    "status": "draft",
                    "pseudo_innovation_risks": [],
                }
            ]
        }
        state = {
            "evidence_contexts": [
                {"candidate_id": "ev-0"},
                {"candidate_id": "ev-1"},
                {"candidate_id": "ev-2"},
            ],
        }
        drafts = parse_draft_output(raw, state)
        assert len(drafts) == 1
        d = drafts[0]
        # All P/M/I fields must be strings, not lists/dicts
        assert isinstance(d["problem"], str)
        assert isinstance(d["method"], str)
        assert isinstance(d["insight"], str)
        # The list content should be preserved as json-encoded string
        assert "gap1" in d["problem"]
        assert "finding1" in d["insight"]

    def test_heuristic_draft_coerces_list_stitching_plan(self):
        """Re7.7: state['innovation_points'][i]['stitching_plan'] may be a
        list (returned by LLM). _heuristic_draft should coerce to string
        before calling .lower() on it."""
        from apps.api.app.services.agents.graph.nodes.novelty_draft import _heuristic_draft

        state = {
            "innovation_points": [
                {
                    "description": "新方法",
                    "baseline_used": "ViT",
                    "stitched_modules": ["CBAM"],
                    "stitching_plan": ["step1", "step2"],  # list, should be coerced
                    "candidate_ids": ["ev-0", "ev-1", "ev-2"],
                }
            ],
            "evidence_contexts": [
                {"candidate_id": "ev-0"},
                {"candidate_id": "ev-1"},
                {"candidate_id": "ev-2"},
            ],
            "baseline_candidates": [{"title": "ViT"}],
        }
        # Should not raise AttributeError
        drafts = _heuristic_draft(state)
        assert len(drafts) >= 1
        assert isinstance(drafts[0]["insight"], str)


class TestNoveltyDraftValidator:
    """Test the has_novelty_drafts validator."""

    def test_valid_drafts(self):
        from apps.api.app.services.router.validators import get_validator
        validator = get_validator("has_novelty_drafts")
        assert validator is not None
        data = {
            "novelty_drafts": [
                {"status": "draft", "problem": "gap"},
                {"status": "needs_evidence", "problem": "gap2"},
            ]
        }
        ok, msg = validator(data)
        assert ok, msg

    def test_empty_drafts_rejected(self):
        from apps.api.app.services.router.validators import get_validator
        validator = get_validator("has_novelty_drafts")
        ok, msg = validator({"novelty_drafts": []})
        assert not ok
        assert "empty" in msg

    def test_accepted_status_rejected(self):
        from apps.api.app.services.router.validators import get_validator
        validator = get_validator("has_novelty_drafts")
        data = {
            "novelty_drafts": [
                {"status": "accepted"},
            ]
        }
        ok, msg = validator(data)
        assert not ok
        assert "forbidden" in msg

    def test_missing_field_rejected(self):
        from apps.api.app.services.router.validators import get_validator
        validator = get_validator("has_novelty_drafts")
        ok, msg = validator({})
        assert not ok
        assert "missing" in msg

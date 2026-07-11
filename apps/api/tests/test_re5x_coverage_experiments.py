"""Re5.X: Coverage Gate + experiment controller tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.validators.coverage_gate import (
    check_coverage, _default_role_policy, _count_roles,
)
from apps.api.app.services.agents.prompts.experiment_a import (
    ActionSelection, parse_action_selection, build_experiment_a_prompt,
)
from apps.api.app.services.agents.prompts.experiment_c import (
    parse_plan_revision, build_experiment_c_prompt,
)
from apps.api.app.services.agents.prompts.experiment_b import (
    parse_diagnosis, parse_writer_output, build_critic_prompt, build_writer_prompt,
)


class TestCoverageGate:
    def test_pass_when_all_required_met(self):
        """All required roles satisfied → pass."""
        state = {
            "verified_papers": [{"verification_verdict": "accept"}] * 3,
            "baseline_candidates": [{"title": "b1"}],
            "parallel_candidates": [],
            "dataset_candidates": [],
            "repo_candidates": [],
            "topic_atoms": {"domain": "computer vision"},
        }
        gate = check_coverage(state, budget_remaining=0, last_two_card_gains=[0, 0])
        assert gate.decision == "pass"

    def test_reflect_when_gap_and_budget(self):
        """Required gap exists + budget remaining → reflect."""
        state = {
            "verified_papers": [],
            "baseline_candidates": [],
            "parallel_candidates": [],
            "dataset_candidates": [],
            "repo_candidates": [],
            "topic_atoms": {"domain": "computer vision"},
        }
        gate = check_coverage(state, budget_remaining=3)
        assert gate.decision == "reflect"
        assert "core" in gate.gaps or "baseline" in gate.gaps

    def test_stop_with_gap_when_budget_exhausted(self):
        """Required gap + no budget → stop_with_gap."""
        state = {
            "verified_papers": [],
            "baseline_candidates": [],
            "parallel_candidates": [],
            "dataset_candidates": [],
            "repo_candidates": [],
            "topic_atoms": {"domain": "unknown"},
        }
        gate = check_coverage(state, budget_remaining=0)
        assert gate.decision == "stop_with_gap"

    def test_repo_optional_for_medical(self):
        """repo should be optional (0) for non-CV/NLP domains."""
        policy = _default_role_policy("medical_ai")
        assert policy["optional"].get("repo", 0) == 0

    def test_repo_optional_for_cv(self):
        """repo should be optional (1) for CV domains."""
        policy = _default_role_policy("computer vision detection")
        assert policy["optional"].get("repo") == 1

    def test_count_roles(self):
        state = {
            "verified_papers": [
                {"verification_verdict": "accept"},
                {"verification_verdict": "accept"},
                {"verification_verdict": "weak_reject"},
            ],
            "baseline_candidates": [{"title": "b1"}],
            "parallel_candidates": [{"title": "p1"}],
            "dataset_candidates": [{"name": "d1"}],
            "repo_candidates": [{"full_name": "r1"}],
        }
        roles = _count_roles(state)
        assert roles["core"] == 2  # only accept
        assert roles["baseline"] == 1
        assert roles["parallel"] == 1
        assert roles["dataset"] == 1
        assert roles["repo"] == 1


class TestExperimentA:
    def test_valid_action_selection(self):
        sel = ActionSelection(
            action="execute_query",
            query_id="q1",
            diagnosis_code="role_gap",
            evidence_ids=["obs-1"],
            reason="need baseline",
        )
        assert sel.action == "execute_query"

    def test_invalid_action_rejected(self):
        import pytest
        with pytest.raises(Exception):
            ActionSelection(
                action="bogus", query_id="q1",
                diagnosis_code="role_gap", reason="x"
            )

    def test_parse_valid(self):
        raw = {"action": "execute_query", "query_id": "q1",
               "diagnosis_code": "role_gap", "evidence_ids": ["e1"], "reason": "test"}
        sel = parse_action_selection(raw)
        assert sel is not None
        assert sel.action == "execute_query"

    def test_parse_invalid_returns_none(self):
        sel = parse_action_selection({"action": "bogus"})
        assert sel is None

    def test_build_prompt_has_allowed_actions(self):
        prompt = build_experiment_a_prompt(
            allowed_actions=[{"query_id": "q1", "source": "arxiv", "query": "test"}],
            observations=[],
            required_roles={"core": 2},
            current_coverage={"core": 0},
            gaps=["core"],
            last_two_gains=[],
            budget_remaining=3,
        )
        assert "q1" in prompt
        assert "arxiv" in prompt


class TestExperimentC:
    def test_parse_valid_revision(self):
        raw = {
            "edits": [{
                "operation": "append",
                "card_id": "sc-001",
                "replacement": {"source": "arxiv", "query": "test", "target_role": "baseline"},
                "evidence_ids": ["obs-1"],
                "expected_increment": "+2 papers"
            }],
            "unresolved_gaps": []
        }
        rev = parse_plan_revision(raw)
        assert rev is not None
        assert len(rev.edits) == 1
        assert rev.edits[0].operation == "append"

    def test_parse_invalid_returns_none(self):
        rev = parse_plan_revision({"edits": [{"operation": "bogus"}]})
        assert rev is None

    def test_build_prompt_has_cards(self):
        prompt = build_experiment_c_prompt(
            current_cards=[{"card_id": "sc-001", "source": "arxiv", "query": "test"}],
            observations=[],
            gaps=["baseline"],
            allowed_sources=["arxiv", "crossref"],
            alternate_map={"semantic_scholar": "crossref"},
        )
        assert "sc-001" in prompt
        assert "baseline" in prompt


class TestExperimentB:
    def test_parse_valid_diagnosis(self):
        raw = {
            "diagnosis_id": "d1",
            "diagnosis_code": "role_gap",
            "confidence": 0.8,
            "action": "rewrite_query",
            "target_role": "baseline",
            "evidence_ids": ["obs-1"],
            "must_keep_terms": ["YOLO"],
            "avoid_terms": ["transformer"],
            "source_preference": ["arxiv"],
        }
        d = parse_diagnosis(raw)
        assert d is not None
        assert d.diagnosis_code == "role_gap"

    def test_parse_invalid_diagnosis_returns_none(self):
        d = parse_diagnosis({"diagnosis_code": "bogus", "action": "bogus",
                             "evidence_ids": ["x"], "confidence": 0.5,
                             "diagnosis_id": "d1"})
        assert d is None

    def test_parse_valid_writer_output(self):
        raw = {
            "cards": [{
                "source": "arxiv",
                "query": "YOLO defect detection baseline",
                "target_role": "baseline",
                "expected_signal": ">=2 verified baseline papers"
            }],
            "abstain_reason": None
        }
        out = parse_writer_output(raw)
        assert out is not None
        assert len(out.cards) == 1
        assert out.cards[0].source == "arxiv"

    def test_parse_invalid_writer_returns_none(self):
        # source is not validated at parse level (allowed_sources is runtime)
        # but empty query should fail
        out2 = parse_writer_output({"cards": [{"source": "arxiv", "query": ""}]})
        assert out2 is None

    def test_build_critic_prompt(self):
        prompt = build_critic_prompt(
            observations=[{"query_id": "q1", "source": "arxiv", "source_status": "empty"}],
            required_roles={"core": 2},
            current_coverage={"core": 0},
            gaps=["core"],
            allowed_sources=["arxiv", "crossref"],
        )
        assert "q1" in prompt
        assert "empty" in prompt

    def test_build_writer_prompt(self):
        prompt = build_writer_prompt(
            diagnosis={"diagnosis_code": "role_gap", "target_role": "baseline"},
            allowed_sources=["arxiv"],
            prior_fingerprints=["abc123"],
            atoms={"method": ["YOLO"], "object": ["defect"], "task": []},
            accepted_seeds=["paper1"],
        )
        assert "YOLO" in prompt
        assert "abc123" in prompt

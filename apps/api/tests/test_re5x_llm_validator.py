"""Re5.X: LLM output validator + auto-repair tests."""
from __future__ import annotations

import pytest

from apps.api.app.services.agents.graph.validators.llm_output_validator import (
    validate_node_output,
    _check_wrong_node,
    call_json_with_validation,
    _NODE_SCHEMAS,
)


class TestWrongNodeDetection:
    def test_verify_signature_detected(self):
        """Dict with verify keys should be flagged as wrong node."""
        data = {"verdict": "reject", "hit_keywords": [], "relation_to_topic": "none"}
        source = _check_wrong_node(data)
        assert source == "verify"

    def test_search_agent_signature_detected(self):
        data = {"action": "search", "tool": "arxiv", "query": "test", "reason": "test"}
        source = _check_wrong_node(data)
        assert source == "search_agent"

    def test_correct_feasibility_not_flagged(self):
        data = {"verdict": "feasible", "score": 85, "reason": "good"}
        source = _check_wrong_node(data)
        assert source is None

    def test_empty_dict_not_flagged(self):
        source = _check_wrong_node({})
        assert source is None


class TestValidateNodeOutput:
    def test_valid_feasibility(self):
        data = {"verdict": "feasible", "score": 85, "reason": "3 baselines + dataset"}
        is_valid, _ = validate_node_output("feasibility_assessor", data)
        assert is_valid

    def test_verify_leak_rejected(self):
        """Verify output format leaking into feasibility should be rejected."""
        data = {"verdict": "reject", "hit_keywords": [], "relation_to_topic": "none"}
        is_valid, error = validate_node_output("feasibility_assessor", data)
        assert not is_valid
        assert "verify" in error

    def test_missing_score_rejected(self):
        data = {"verdict": "feasible", "reason": "good"}
        is_valid, error = validate_node_output("feasibility_assessor", data)
        assert not is_valid
        assert "score" in error

    def test_valid_innovation(self):
        data = {"innovation_points": [{"description": "test"}], "stitching_plan": {}}
        is_valid, _ = validate_node_output("innovation_extractor", data)
        assert is_valid

    def test_valid_narrative(self):
        data = {"nick_model_name": "YOLO-Net", "narrative_summary": "test"}
        is_valid, _ = validate_node_output("narrative_builder", data)
        assert is_valid

    def test_valid_devils_advocate(self):
        data = {"overall_verdict": "ACCEPT", "dimension_scores": []}
        is_valid, _ = validate_node_output("devils_advocate", data)
        assert is_valid

    def test_non_dict_rejected(self):
        is_valid, error = validate_node_output("feasibility_assessor", "not a dict")
        assert not is_valid
        assert "dict" in error

    def test_unknown_node_accepted(self):
        """Unknown nodes should pass (no schema registered)."""
        is_valid, _ = validate_node_output("unknown_node", {"anything": True})
        assert is_valid


class TestCallJsonWithValidation:
    def test_fallback_used_on_llm_failure(self):
        """When LLM is unavailable, fallback should be used."""
        # This test doesn't call real LLM; it tests the fallback path
        # by using a non-existent profile
        from apps.api.app.services.agents.graph.validators.llm_output_validator import (
            call_json_with_validation,
        )
        result = call_json_with_validation(
            "test",
            system="test",
            node_name="feasibility_assessor",
            profile="nonexistent_profile",
            max_tokens=10,
            timeout=1,
            fallback={"verdict": "risky", "score": 50, "reason": "fallback"},
        )
        assert result["verdict"] == "risky"
        assert result["score"] == 50

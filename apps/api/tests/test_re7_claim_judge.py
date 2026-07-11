"""Unit tests for claim_judge node (unified router migration)."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.claim_judge import (
    build_claim_judge_prompt,
    parse_claim_judge_output,
    claim_judge_node,
)


SAMPLE_JUDGE_OUTPUT = {
    "judgements": [
        {
            "candidate_id": "nd-001",
            "pmi_valid": True,
            "evidence_complete": True,
            "differentiation_valid": True,
            "first_claim_correctly_downgraded": True,
            "falsifiability_defined": True,
            "verdict": "ACCEPT",
            "issues": [],
            "required_fixes": [],
        }
    ],
    "overall_verdict": "ACCEPT",
    "blocked_items": [],
    "summary": "all claims accepted",
}


def test_build_prompt_contains_topic_and_evidence():
    state = {
        "topic": "钢材表面缺陷检测",
        "innovation_points": [{"description": "test"}],
        "evidence_contexts": [
            {"role": "method", "snippet": "CBAM attention"},
        ],
    }
    prompt = build_claim_judge_prompt(state)
    assert "钢材表面缺陷检测" in prompt
    assert "CBAM attention" in prompt


def test_parse_output_maps_fields():
    parsed = parse_claim_judge_output(SAMPLE_JUDGE_OUTPUT)
    assert parsed["claim_judge_verdict"] == "ACCEPT"
    assert len(parsed["claim_judgements"]) == 1
    assert parsed["claim_judge_summary"] == "all claims accepted"


def test_node_returns_accept_when_llm_succeeds():
    state = {
        "topic": "test",
        "innovation_points": [{"description": "innovation"}],
        "evidence_contexts": [],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=SAMPLE_JUDGE_OUTPUT,
    ):
        result = claim_judge_node(state)
    assert result["claim_judge_verdict"] == "ACCEPT"
    assert len(result["claim_judgements"]) == 1


def test_node_returns_reject_when_no_innovation_points():
    result = claim_judge_node({
        "topic": "test",
        "innovation_points": [],
        "evidence_contexts": [],
    })
    assert result["claim_judge_verdict"] == "REJECT"
    assert result["claim_judgements"] == []


def test_node_falls_back_on_llm_failure():
    state = {
        "topic": "test",
        "innovation_points": [{"description": "innovation"}],
        "evidence_contexts": [],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        side_effect=RuntimeError("unified router unavailable"),
    ):
        result = claim_judge_node(state)
    assert result["claim_judge_verdict"] == "REJECT"


def test_validate_claim_judge_rejects_invalid_verdict():
    """Semantic validator must reject invalid verdict values."""
    from apps.api.app.services.router.validators.novelty_validators import (
        validate_claim_judge,
    )
    ok, err = validate_claim_judge({
        "judgements": [{"candidate_id": "nd-001", "verdict": "MAYBE"}],
        "overall_verdict": "MAYBE",
        "blocked_items": [],
        "summary": "bad verdict",
    })
    assert not ok
    assert "overall_verdict" in (err or "")


def test_node_overall_verdict_matches_judgements():
    state = {
        "topic": "test",
        "innovation_points": [{"description": "innovation"}],
        "evidence_contexts": [],
    }
    revise_output = dict(SAMPLE_JUDGE_OUTPUT)
    revise_output["overall_verdict"] = "REVISE"
    revise_output["judgements"][0]["verdict"] = "REVISE"
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=revise_output,
    ):
        result = claim_judge_node(state)
    assert result["claim_judge_verdict"] == "REVISE"

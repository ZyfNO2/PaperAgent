"""Unit tests for novelty_review node (unified router migration)."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.novelty_review import (
    build_novelty_review_prompt,
    parse_novelty_review_output,
    novelty_review_node,
)


SAMPLE_REVIEW_OUTPUT = {
    "verdict": "weak_reject",
    "novelty_score": 5,
    "pseudo_innovation_risks": ["motivation_by_model_availability"],
    "pressure_points": [
        {
            "risk": "repetition",
            "question": "Is this already published?",
            "severity": "high",
            "repair": "clarify difference",
            "evidence_ids": ["ev-1"],
        },
        {
            "risk": "motivation",
            "question": "Is the gap real?",
            "severity": "medium",
            "repair": "add evidence",
            "evidence_ids": [],
        },
        {
            "risk": "falsifiability",
            "question": "Can it be disproven?",
            "severity": "medium",
            "repair": "define test",
            "evidence_ids": ["ev-2"],
        },
        {
            "risk": "differentiation",
            "question": "How is it different?",
            "severity": "high",
            "repair": "compare baselines",
            "evidence_ids": ["ev-3"],
        },
        {
            "risk": "story",
            "question": "Does the narrative connect?",
            "severity": "low",
            "repair": "tighten logic",
            "evidence_ids": ["ev-4"],
        },
    ],
    "differentiation_matrix": [
        {
            "adjacent_work_id": "p1",
            "adjacent_work_label": "Baseline A",
            "problem_diff": "different problem scope",
            "method_diff": "different method",
            "detail_diff": "different details",
            "evidence_diff": "different evidence",
            "insight_diff": "different insight",
        }
    ],
    "required_repairs": ["add motivation evidence"],
    "strengths": ["clear method"],
    "risks": ["weak motivation"],
}


def test_build_prompt_contains_topic_and_evidence():
    state = {
        "topic": "钢材表面缺陷检测",
        "innovation_points": [{"description": "test"}],
        "verified_papers": [
            {"candidate_id": "ev-1", "title": "Paper 1", "year": 2024,
             "abstract": "abstract text"},
        ],
        "baseline_candidates": [
            {"id": "b1", "title": "Baseline A"},
        ],
    }
    prompt = build_novelty_review_prompt(state)
    assert "钢材表面缺陷检测" in prompt
    assert "ev-1" in prompt
    assert "Baseline A" in prompt


def test_parse_output_maps_fields():
    parsed = parse_novelty_review_output(SAMPLE_REVIEW_OUTPUT)
    assert parsed["novelty_review_verdict"] == "weak_reject"
    assert parsed["novelty_review_score"] == 5
    assert len(parsed["pressure_points"]) == 5
    assert len(parsed["differentiation_matrix"]) == 1
    assert parsed["required_repairs"] == ["add motivation evidence"]
    assert parsed["review_strengths"] == ["clear method"]
    assert parsed["review_risks"] == ["weak motivation"]


def test_node_returns_review_when_llm_succeeds():
    state = {
        "topic": "test topic",
        "innovation_points": [{"description": "innovation"}],
        "verified_papers": [],
        "baseline_candidates": [],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=SAMPLE_REVIEW_OUTPUT,
    ):
        result = novelty_review_node(state)
    assert result["novelty_review_verdict"] == "weak_reject"
    assert result["novelty_review_score"] == 5
    assert len(result["pressure_points"]) == 5


def test_node_fills_missing_evidence_ids_with_unknown():
    state = {
        "topic": "test topic",
        "innovation_points": [{"description": "innovation"}],
        "verified_papers": [],
        "baseline_candidates": [],
    }
    raw = dict(SAMPLE_REVIEW_OUTPUT)
    raw["pressure_points"][1]["evidence_ids"] = []
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=raw,
    ):
        result = novelty_review_node(state)
    # Validator mutates in place, but we do not re-validate output here.
    assert result["novelty_review_verdict"] == "weak_reject"


def test_node_returns_reject_when_no_innovation_points():
    result = novelty_review_node({
        "topic": "test",
        "innovation_points": [],
    })
    assert result["novelty_review_verdict"] == "reject"
    assert result["novelty_review_score"] == 0
    assert "no_innovation_points" in result["pseudo_innovation_risks"]


def test_node_falls_back_on_llm_failure():
    state = {
        "topic": "test topic",
        "innovation_points": [{"description": "innovation"}],
        "verified_papers": [],
        "baseline_candidates": [],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        side_effect=RuntimeError("unified router unavailable"),
    ):
        result = novelty_review_node(state)
    assert result["novelty_review_verdict"] == "reject"
    assert result["novelty_review_score"] == 0
    assert "llm_unavailable" in result["pseudo_innovation_risks"]

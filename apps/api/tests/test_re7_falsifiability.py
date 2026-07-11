"""Unit tests for falsifiability node (unified router migration)."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.falsifiability import (
    build_falsifiability_prompt,
    parse_falsifiability_output,
    falsifiability_node,
)


SAMPLE_FALSIFIABILITY_OUTPUT = {
    "propositions": [
        {
            "proposition_id": "fp-001",
            "proposition": "Adding CBAM improves small-defect recall.",
            "scoped_setting": "NEU-DET steel surface defects",
            "observable_effect": "Recall of defects < 32px increases.",
            "support_condition": "Recall improves by > 3% on small defects.",
            "refute_condition": "Recall does not improve or drops.",
            "required_test": "Ablation: ViT vs ViT+CBAM on small-defect subset.",
            "evidence_ids": ["ev-cbam-1"],
            "status": "planned_not_verified",
        }
    ]
}


def test_build_prompt_uses_accepted_insights():
    state = {
        "topic": "test",
        "innovation_points": [
            {"description": "A", "status": "accepted"},
            {"description": "B", "status": "needs_evidence"},
        ],
    }
    prompt = build_falsifiability_prompt(state)
    assert "A" in prompt
    assert "B" not in prompt  # only accepted/verified


def test_parse_output_extracts_propositions():
    parsed = parse_falsifiability_output(SAMPLE_FALSIFIABILITY_OUTPUT)
    assert len(parsed["falsifiable_propositions"]) == 1
    prop = parsed["falsifiable_propositions"][0]
    assert prop["proposition_id"] == "fp-001"
    assert prop["status"] == "planned_not_verified"


def test_parse_output_downgrades_verified_without_evidence():
    raw = {
        "propositions": [
            {
                "proposition_id": "fp-002",
                "support_condition": "s",
                "refute_condition": "r",
                "required_test": "t",
                "status": "verified",
                "evidence_ids": [],
            }
        ]
    }
    parsed = parse_falsifiability_output(raw)
    assert parsed["falsifiable_propositions"][0]["status"] == "planned_not_verified"


def test_node_returns_propositions_when_llm_succeeds():
    state = {
        "topic": "test",
        "innovation_points": [
            {"description": "innovation", "status": "accepted"},
        ],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=SAMPLE_FALSIFIABILITY_OUTPUT,
    ):
        result = falsifiability_node(state)
    assert len(result["falsifiable_propositions"]) == 1


def test_node_returns_empty_when_no_innovation_points():
    result = falsifiability_node({"topic": "test", "innovation_points": []})
    assert result["falsifiable_propositions"] == []


def test_node_returns_empty_when_no_accepted_insights():
    state = {
        "topic": "test",
        "innovation_points": [
            {"description": "innovation", "status": "needs_evidence"},
        ],
    }
    result = falsifiability_node(state)
    assert result["falsifiable_propositions"] == []


def test_node_falls_back_on_llm_failure():
    state = {
        "topic": "test",
        "innovation_points": [
            {"description": "innovation", "status": "accepted"},
        ],
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        side_effect=RuntimeError("unified router unavailable"),
    ):
        result = falsifiability_node(state)
    assert result["falsifiable_propositions"] == []

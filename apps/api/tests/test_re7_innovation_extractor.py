"""Re7.7: innovation_extractor type safety + downstream prompt defense tests."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.innovation_extractor import (
    innovation_extractor_node,
)


def test_innovation_extractor_filters_string_items():
    """Re7.7: LLM may return innovation_points containing strings instead of
    dicts. The node must filter them out so downstream consumers (which call
    ip.get(...)) don't crash with AttributeError."""
    state = {
        "topic": "test topic",
        "baseline_candidates": [{"title": "baseline-A", "paper_id": "b-1"}],
        "parallel_candidates": [{"title": "parallel-B", "paper_id": "p-1"}],
    }
    # LLM returns a mixed list: a string + a valid dict
    llm_out = {
        "innovation_points": ["这是一个纯字符串创新点", {"description": "valid dict item"}],
        "stitching_plan": {"baseline_model": "baseline-A", "module_b": "parallel-B"},
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=llm_out,
    ):
        result = innovation_extractor_node(state)
    inn = result["innovation_points"]
    assert isinstance(inn, list)
    # String item must be filtered out
    assert all(isinstance(ip, dict) for ip in inn)
    assert len(inn) == 1
    assert inn[0]["description"] == "valid dict item"


def test_innovation_extractor_handles_all_string_items():
    """Re7.7: when LLM returns all strings, result should be empty list, not crash."""
    state = {
        "topic": "test topic",
        "baseline_candidates": [{"title": "baseline-A"}],
        "parallel_candidates": [],
    }
    llm_out = {
        "innovation_points": ["string1", "string2"],
        "stitching_plan": {},
    }
    with patch(
        "apps.api.app.services.agents.graph.validators.llm_output_validator.call_json_with_validation",
        return_value=llm_out,
    ):
        result = innovation_extractor_node(state)
    assert result["innovation_points"] == []


def test_narrative_builder_prompt_handles_string_items():
    """Re7.7: P.build() must not crash when innovations contains strings
    (defensive filter in prompts/narrative_builder.py)."""
    from apps.api.app.services.agents.prompts.narrative_builder import build

    # Mixed list: string + dict
    innovations = ["纯字符串", {"description": "valid", "baseline_used": "B"}]
    result = build("test topic", innovations, {"verdict": "feasible", "score": 80, "reason": "ok"})
    assert "system" in result
    assert "user" in result
    # The valid dict item should appear in the prompt, the string should be skipped
    assert "valid" in result["user"]
    assert "纯字符串" not in result["user"]


def test_devils_advocate_prompt_handles_string_items():
    """Re7.7: P.build() must not crash when innovations contains strings
    (defensive filter in prompts/devils_advocate_graph.py)."""
    from apps.api.app.services.agents.prompts.devils_advocate_graph import build

    innovations = ["纯字符串", {"description": "valid", "baseline_used": "B"}]
    narrative = {"three_problems": [], "nick_model_name": "Test-Net", "narrative_summary": "..."}
    work_packages = [{"title": "wp-1", "description": "do something"}]
    result = build(
        "test topic",
        {"verdict": "feasible", "score": 80, "reason": "ok"},
        innovations,
        narrative,
        work_packages,
    )
    assert "system" in result
    assert "user" in result
    assert "valid" in result["user"]
    assert "纯字符串" not in result["user"]

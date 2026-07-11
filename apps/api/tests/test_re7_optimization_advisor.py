"""Re7.6 optimization_advisor unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.optimization_advisor import (
    optimization_advisor_node,
)

PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.llm_router.call_json"


def _make_unified_result(content: dict[str, Any]) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.content = content
    result.error = None
    return result


def _base_state() -> dict[str, Any]:
    return {
        "topic": "Retrieval-augmented generation",
        "feasibility_report": {"verdict": "feasible", "score": 8},
        "innovation_points": [{"title": "novel idea"}],
        "baseline_candidates": [{"title": "Baseline"}],
        "parallel_candidates": [{"title": "Parallel"}],
        "trace_events": [],
    }


def test_unified_router_used_by_default(monkeypatch: Any) -> None:
    """OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER default=1 -> call_with_contract."""
    monkeypatch.delenv("OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER", raising=False)
    advisory = {
        "optimization_paths": [
            {"direction": "test", "expected_gain": "x", "difficulty": "低",
             "action_items": ["a"], "ref_parallel": "p"}
        ],
        "degradation_paths": [{"path": "d", "trade_off": "t", "survival_rate": "高"}],
        "risk_mitigation": ["m"],
    }

    with patch(PATCH_CONTRACT, return_value=_make_unified_result(advisory)) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = optimization_advisor_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["optimization_directions"] == advisory
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "optimization-advisory/v1"
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert trace["tool_calls"][0] == {"tool": "optimization-advisory/v1"}


def test_legacy_when_flag_off(monkeypatch: Any) -> None:
    """OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER", "0")
    legacy_response = {
        "optimization_paths": [
            {"direction": "legacy", "expected_gain": "x", "difficulty": "低",
             "action_items": ["a"]}
        ],
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        result = optimization_advisor_node(_base_state())

    assert mock_legacy.called
    assert not mock_unified.called
    trace = result["trace_events"][0]
    assert trace["provider"] == "fast_json"
    assert trace["tool_calls"][0] == {"tool": "optimization_advisor.llm"}


def test_unified_failure_falls_back_to_heuristic(monkeypatch: Any) -> None:
    """When unified router fails, node falls back to heuristic."""
    monkeypatch.setenv("OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER", "1")
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "contract failed"

    with patch(PATCH_CONTRACT, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = optimization_advisor_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert "optimization_paths" in result["optimization_directions"]
    trace = result["trace_events"][0]
    assert trace["provider"] == "heuristic"
    assert trace["tool_calls"][0] == {"tool": "heuristic"}


def test_exception_falls_back_to_heuristic(monkeypatch: Any) -> None:
    """Exception during LLM call falls back to heuristic."""
    monkeypatch.setenv("OPTIMIZATION_ADVISOR_USE_UNIFIED_ROUTER", "1")

    with patch(PATCH_CONTRACT, side_effect=RuntimeError("boom")), \
         patch(PATCH_LEGACY) as mock_legacy:
        result = optimization_advisor_node(_base_state())

    assert not mock_legacy.called
    assert "optimization_paths" in result["optimization_directions"]
    trace = result["trace_events"][0]
    assert trace["provider"] == "heuristic"

"""Re7.6 topic_parser unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.topic_parser import topic_parser_node

PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.agents.graph.nodes.topic_parser.call_json"


def _make_contract_result(content: dict[str, Any]) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.content = content
    result.error = None
    return result


def _base_state() -> dict[str, Any]:
    return {
        "topic": "Retrieval-augmented generation for enterprise knowledge base question answering",
        "trace_events": [],
    }


def test_unified_router_used_by_default(monkeypatch: Any) -> None:
    """TOPIC_PARSER_USE_UNIFIED_ROUTER default=1 -> call_with_contract."""
    monkeypatch.delenv("TOPIC_PARSER_USE_UNIFIED_ROUTER", raising=False)
    atoms = {
        "method": ["retrieval-augmented generation"],
        "object": ["knowledge base"],
        "task": ["question answering"],
        "scenario": ["enterprise deployment"],
        "domain": "nlp_llm",
        "dataset_terms": [],
        "baseline_terms": ["retrieval-augmented generation"],
        "avoid_terms": [],
    }

    with patch(PATCH_CONTRACT, return_value=_make_contract_result(atoms)) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = topic_parser_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "topic-parse/v1"
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert any(t.get("mode") == "unified_router" for t in trace["tool_calls"])


def test_legacy_when_flag_off(monkeypatch: Any) -> None:
    """TOPIC_PARSER_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("TOPIC_PARSER_USE_UNIFIED_ROUTER", "0")
    legacy_atoms = {
        "method": ["legacy method"],
        "object": ["legacy object"],
        "task": ["legacy task"],
        "scenario": [],
        "domain": "nlp_llm",
        "dataset_terms": [],
        "baseline_terms": [],
        "avoid_terms": [],
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_atoms) as mock_legacy:
        result = topic_parser_node(_base_state())

    assert mock_legacy.called
    assert not mock_unified.called
    assert result["provider_profile"] == "fast_json"
    trace = result["trace_events"][0]
    assert trace["provider"] == "fast_json"


def test_unified_failure_uses_heuristic(monkeypatch: Any) -> None:
    """When unified router fails, topic_parser falls back to heuristic parsing."""
    monkeypatch.setenv("TOPIC_PARSER_USE_UNIFIED_ROUTER", "1")
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "contract failed"

    with patch(PATCH_CONTRACT, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = topic_parser_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    atoms = result["topic_atoms"]
    # heuristic should extract some English terms from topic
    assert atoms.get("method")
    assert atoms.get("domain") == "nlp_llm"


def test_exception_falls_back_to_heuristic(monkeypatch: Any) -> None:
    """Exception during unified router call falls back to heuristic parsing."""
    monkeypatch.setenv("TOPIC_PARSER_USE_UNIFIED_ROUTER", "1")

    with patch(PATCH_CONTRACT, side_effect=RuntimeError("boom")), \
         patch(PATCH_LEGACY) as mock_legacy:
        result = topic_parser_node(_base_state())

    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    errors = result.get("errors") or []
    assert any(e.get("node") == "topic_parser" for e in errors)

"""Re7.6 targeted_repair unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.targeted_repair import (
    targeted_repair_node,
)

PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json"


def _make_unified_result(content: dict[str, Any]) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.content = content
    result.error = None
    return result


def _base_state() -> dict[str, Any]:
    return {
        "topic": "Retrieval-augmented generation",
        "paper_candidates": [
            {"title": "Rejected paper", "abstract": "abs"},
        ],
        "verified_papers": [
            {"title": "Verified paper", "abstract": "abs"},
        ],
        "baseline_candidates": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "search_plan": {"queries": [{"tool": "arxiv", "query": "initial query"}]},
        "evidence_audit": {"repair_rounds": 0},
        "trace_events": [],
    }


def test_unified_router_used_by_default(monkeypatch: Any) -> None:
    """TARGETED_REPAIR_USE_UNIFIED_ROUTER default=1 -> call_with_contract."""
    monkeypatch.delenv("TARGETED_REPAIR_USE_UNIFIED_ROUTER", raising=False)
    decision = {
        "queries": [
            {"tool": "openalex", "query": "rag llm", "why": "broaden",
             "expected_evidence": "paper", "stop_condition": "5 hits"}
        ],
        "strategy": "broaden",
    }

    with patch(PATCH_CONTRACT, return_value=_make_unified_result(decision)) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = targeted_repair_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    assert result["repair_outcome"] == "queries_ready"
    assert len(result["search_plan"]["queries"]) == 1
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "targeted-repair/v1"


def test_legacy_when_flag_off(monkeypatch: Any) -> None:
    """TARGETED_REPAIR_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("TARGETED_REPAIR_USE_UNIFIED_ROUTER", "0")
    legacy_response = {
        "queries": [
            {"tool": "arxiv", "query": "legacy repair", "why": "legacy"}
        ],
        "strategy": "synonym",
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        result = targeted_repair_node(_base_state())

    assert mock_legacy.called
    assert not mock_unified.called
    assert result["provider_profile"] == "fast_json"
    assert result["repair_outcome"] == "queries_ready"


def test_unified_failure_falls_back_to_empty_plan(monkeypatch: Any) -> None:
    """When unified router fails, node emits no_query outcome."""
    monkeypatch.setenv("TARGETED_REPAIR_USE_UNIFIED_ROUTER", "1")
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "contract failed"

    with patch(PATCH_CONTRACT, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = targeted_repair_node(_base_state())

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    assert result["repair_outcome"] == "no_query"
    assert result["search_plan"]["queries"] == []


def test_trace_records_unified_provider(monkeypatch: Any) -> None:
    """Trace should record targeted-repair/v1 tool and unified_router provider."""
    monkeypatch.setenv("TARGETED_REPAIR_USE_UNIFIED_ROUTER", "1")
    decision = {
        "queries": [
            {"tool": "crossref", "query": "trace test", "why": "trace"}
        ],
        "strategy": "switch_tool",
    }

    with patch(PATCH_CONTRACT, return_value=_make_unified_result(decision)):
        result = targeted_repair_node(_base_state())

    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert trace["tool_calls"][0] == {"tool": "targeted-repair/v1",
                                       "attempts": 1, "mode": "unified_router"}


def test_prior_queries_are_deduplicated(monkeypatch: Any) -> None:
    """Queries matching prior search_plan queries are dropped."""
    monkeypatch.setenv("TARGETED_REPAIR_USE_UNIFIED_ROUTER", "1")
    decision = {
        "queries": [
            {"tool": "arxiv", "query": "Initial Query", "why": "duplicate"},
            {"tool": "openalex", "query": "new query", "why": "fresh"},
        ],
        "strategy": "synonym",
    }

    with patch(PATCH_CONTRACT, return_value=_make_unified_result(decision)):
        result = targeted_repair_node(_base_state())

    queries = result["search_plan"]["queries"]
    assert len(queries) == 1
    assert queries[0]["query"] == "new query"
    assert result["repair_outcome"] == "queries_ready"


def test_round_cap_returns_exhausted(monkeypatch: Any) -> None:
    """When repair_rounds >= MAX_REPAIR_ROUNDS, node returns exhausted."""
    monkeypatch.setenv("PAPERAGENT_MAX_REPAIR_ROUNDS", "2")
    state = _base_state()
    state["evidence_audit"]["repair_rounds"] = 2

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = targeted_repair_node(state)

    assert not mock_unified.called
    assert not mock_legacy.called
    assert result["repair_outcome"] == "exhausted"
    assert result["repair_exhausted"] is True

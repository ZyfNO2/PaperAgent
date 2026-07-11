"""Re7.6 search_agent unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.search_agent import (
    _llm_decide,
    search_agent_node,
)

PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.llm_router.call_json"
PATCH_CATALOG = "apps.api.app.services.search_catalog.get_source_catalog"
PATCH_RUN_TOOL = "apps.api.app.services.agents.graph.nodes.search_agent._run_tool_sync"


def _make_catalog() -> MagicMock:
    catalog = MagicMock()
    catalog.allowed_source_names.return_value = ["arxiv", "openalex", "crossref", "github"]
    catalog.source_list_for_prompt.return_value = "- arxiv: arXiv\n- openalex: OpenAlex"
    catalog.is_available.return_value = True
    return catalog


def _make_unified_result(decision: dict[str, Any]) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.content = decision
    result.error = None
    return result


def test_llm_decide_uses_unified_router_by_default(monkeypatch: Any) -> None:
    """SEARCH_AGENT_USE_UNIFIED_ROUTER default=1 -> call_with_contract."""
    monkeypatch.delenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", raising=False)
    decision = {"action": "search", "tool": "arxiv", "query": "rag qa", "reason": "test"}

    with patch(PATCH_CATALOG, return_value=_make_catalog()), \
         patch(PATCH_CONTRACT, return_value=_make_unified_result(decision)) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result, prov = _llm_decide("topic", {"method": ["rag"]}, [], [], [], {})

    assert mock_unified.called
    assert not mock_legacy.called
    assert prov == "unified_router"
    assert result["action"] == "search"
    assert result["tool"] == "arxiv"
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "search-decision/v1"


def test_llm_decide_legacy_when_flag_off(monkeypatch: Any) -> None:
    """SEARCH_AGENT_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
    legacy_response = {"action": "search", "tool": "openalex", "query": "rag", "reason": "legacy"}

    with patch(PATCH_CATALOG, return_value=_make_catalog()), \
         patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        result, prov = _llm_decide("topic", {"method": ["rag"]}, [], [], [], {})

    assert mock_legacy.called
    assert not mock_unified.called
    assert prov == "fast_json"
    assert result["tool"] == "openalex"


def test_llm_decide_unified_failure_falls_back(monkeypatch: Any) -> None:
    """When unified router fails, _llm_decide falls back to deterministic plan."""
    monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "1")
    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "contract failed"

    search_plan = {
        "queries": [
            {"tool": "crossref", "query": "fallback query"},
        ],
    }

    with patch(PATCH_CATALOG, return_value=_make_catalog()), \
         patch(PATCH_CONTRACT, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result, prov = _llm_decide("topic", {"method": ["rag"]}, [], [], [], search_plan)

    assert mock_unified.called
    assert not mock_legacy.called
    assert prov == "local"
    assert result["action"] == "search"
    assert result["tool"] == "crossref"


def test_node_records_unified_provider_in_trace(monkeypatch: Any) -> None:
    """When search_agent uses unified router, trace records provider."""
    monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "1")

    # First call searches arxiv, second call stops.
    decisions = [
        {"action": "search", "tool": "arxiv", "query": "rag", "reason": "go"},
        {"action": "stop", "reason": "enough"},
    ]
    decision_iter = iter(decisions)

    def _fake_contract(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _make_unified_result(next(decision_iter))

    state = {
        "topic": "Retrieval-augmented generation",
        "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
        "search_plan": {"queries": []},
        "trace_events": [],
    }

    with patch(PATCH_CATALOG, return_value=_make_catalog()), \
         patch(PATCH_CONTRACT, side_effect=_fake_contract), \
         patch(PATCH_RUN_TOOL, return_value=[{"title": "RAG paper", "abstract": "abs"}]) as mock_tool:
        result = search_agent_node(state)

    assert mock_tool.called
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert trace["input_summary"]["provider"] == "unified_router"
    assert trace["tool_calls"][0] == {"tool": "search-decision/v1", "mode": "unified_router"}
    assert result["provider_profile"] == "unified_router"


def test_node_legacy_provider_when_flag_off(monkeypatch: Any) -> None:
    """SEARCH_AGENT_USE_UNIFIED_ROUTER=0 -> trace provider is fast_json."""
    monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")

    decisions = [
        {"action": "search", "tool": "arxiv", "query": "rag", "reason": "go"},
        {"action": "stop", "reason": "enough"},
    ]
    decision_iter = iter(decisions)

    state = {
        "topic": "Retrieval-augmented generation",
        "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
        "search_plan": {"queries": []},
        "trace_events": [],
    }

    with patch(PATCH_CATALOG, return_value=_make_catalog()), \
         patch(PATCH_LEGACY, side_effect=lambda *a, **k: next(decision_iter)), \
         patch(PATCH_RUN_TOOL, return_value=[{"title": "RAG paper", "abstract": "abs"}]):
        result = search_agent_node(state)

    trace = result["trace_events"][0]
    assert trace["provider"] == "fast_json"
    assert trace["tool_calls"][0] == {"tool": "llm_decide", "mode": "fast_json"}
    assert result["provider_profile"] == "fast_json"

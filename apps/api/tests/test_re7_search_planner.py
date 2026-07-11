"""Re7.6 search_planner unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes import search_planner as sp

PATCH_ROUTER = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.agents.graph.nodes.search_planner.call_json"


def _make_contract_result(content: dict[str, Any]) -> MagicMock:
    result = MagicMock()
    result.success = True
    result.content = content
    result.error = None
    return result


@pytest.fixture
def atoms() -> dict[str, Any]:
    return {
        "method": ["retrieval-augmented generation"],
        "object": ["knowledge base"],
        "task": ["question answering"],
        "scenario": ["enterprise deployment"],
        "domain": "nlp_llm",
        "dataset_terms": [],
        "baseline_terms": ["retrieval-augmented generation"],
        "avoid_terms": [],
    }


@pytest.fixture
def minimal_state(atoms: dict[str, Any]) -> dict[str, Any]:
    return {
        "topic": "Retrieval-augmented generation for enterprise knowledge base question answering",
        "topic_atoms": atoms,
        "trace_events": [],
        "errors": [],
    }


def test_default_template_path_skips_llm(minimal_state: dict[str, Any]) -> None:
    """Default template mode should not call any LLM and return a local plan."""
    with patch(PATCH_LEGACY) as mock_legacy, \
         patch(PATCH_ROUTER) as mock_unified:
        result = sp.search_planner_node(minimal_state)

    assert not mock_legacy.called
    assert not mock_unified.called
    plan = result["search_plan"]
    assert plan["queries"]
    assert plan["rounds"]
    trace = result["trace_events"][0]
    assert trace["provider"] == "local"


def test_llm_mode_uses_unified_router(minimal_state: dict[str, Any], monkeypatch: Any) -> None:
    """PAPERAGENT_SEARCH_PLANNER=llm + unified router flag → call_with_contract."""
    monkeypatch.setenv("PAPERAGENT_SEARCH_PLANNER", "llm")
    monkeypatch.setenv("SEARCH_PLANNER_USE_UNIFIED_ROUTER", "1")

    contract_response = {
        "queries": [
            {
                "tool": "openalex",
                "query": "rag enterprise knowledge base",
                "why": "baseline",
                "expected_evidence": "papers",
                "stop_condition": "n>=5",
            },
        ],
        "rounds": ["broad"],
        "negative_feedback": "",
    }

    with patch(PATCH_LEGACY) as mock_legacy, \
         patch(PATCH_ROUTER, return_value=_make_contract_result(contract_response)) as mock_unified:
        result = sp.search_planner_node(minimal_state)

    assert mock_unified.called
    assert not mock_legacy.called
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "search-plan/v1"
    plan = result["search_plan"]
    assert any(q["tool"] == "openalex" for q in plan["queries"])
    assert result["provider_profile"] == "unified_router"
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert any(t.get("mode") == "unified_router" for t in trace["tool_calls"])


def test_llm_mode_legacy_fallback_when_flag_off(minimal_state: dict[str, Any], monkeypatch: Any) -> None:
    """SEARCH_PLANNER_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("PAPERAGENT_SEARCH_PLANNER", "llm")
    monkeypatch.setenv("SEARCH_PLANNER_USE_UNIFIED_ROUTER", "0")

    def fake_legacy(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "queries": [
                {
                    "tool": "arxiv",
                    "query": "rag qa",
                    "why": "recent",
                    "expected_evidence": "preprints",
                    "stop_condition": "n>=5",
                },
            ],
            "rounds": ["broad"],
            "negative_feedback": "",
        }

    with patch(PATCH_LEGACY, side_effect=fake_legacy) as mock_legacy, \
         patch(PATCH_ROUTER) as mock_unified:
        result = sp.search_planner_node(minimal_state)

    assert mock_legacy.called
    assert not mock_unified.called
    assert result["provider_profile"] == "fast_json"


def test_unified_router_failure_records_error(minimal_state: dict[str, Any], monkeypatch: Any) -> None:
    """Unified router raises → search_planner records error and returns empty plan."""
    monkeypatch.setenv("PAPERAGENT_SEARCH_PLANNER", "llm")
    monkeypatch.setenv("SEARCH_PLANNER_USE_UNIFIED_ROUTER", "1")

    with patch(PATCH_ROUTER, side_effect=RuntimeError("router unavailable")):
        result = sp.search_planner_node(minimal_state)

    errors = result.get("errors", [])
    assert any("search_planner" in e.get("node", "") for e in errors)
    plan = result["search_plan"]
    assert plan["queries"] == []


def test_unified_router_unsuccessful_result_falls_back(minimal_state: dict[str, Any], monkeypatch: Any) -> None:
    """Unified router returns unsuccessful ContractResult → empty plan, no exception."""
    monkeypatch.setenv("PAPERAGENT_SEARCH_PLANNER", "llm")
    monkeypatch.setenv("SEARCH_PLANNER_USE_UNIFIED_ROUTER", "1")

    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "validation failed"

    with patch(PATCH_ROUTER, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = sp.search_planner_node(minimal_state)

    assert mock_unified.called
    assert not mock_legacy.called
    assert result["provider_profile"] == "unified_router"
    plan = result["search_plan"]
    assert plan["queries"] == []

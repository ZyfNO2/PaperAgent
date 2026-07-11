"""Re7.6 quality_filter unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from apps.api.app.services.agents.graph.nodes.quality_filter import (
    _call_llm_batch,
    quality_filter_node,
)


PATCH_CONTRACT_LIST = "apps.api.app.services.router.call_with_contract_list"
PATCH_LEGACY = "apps.api.app.services.llm_router.call_json"


def test_call_llm_batch_uses_unified_router_by_default(monkeypatch: Any) -> None:
    """QUALITY_FILTER_USE_UNIFIED default=1 → call_with_contract_list."""
    monkeypatch.delenv("QUALITY_FILTER_USE_UNIFIED", raising=False)
    candidates = [{"title": "Some paper", "abstract": "abstract"}]

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = [
        {"index": 0, "is_paper": True, "reason": "looks like a paper"},
    ]

    with patch(PATCH_CONTRACT_LIST, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        out, prov = _call_llm_batch(candidates)

    assert prov == "unified_router"
    assert out == [{"index": 0, "is_paper": True, "reason": "looks like a paper"}]
    assert mock_unified.called
    assert not mock_legacy.called
    # contract_id should be explicit to avoid role collision
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "query-filter-batch/v1"


def test_call_llm_batch_legacy_when_flag_off(monkeypatch: Any) -> None:
    """QUALITY_FILTER_USE_UNIFIED=0 falls back to legacy call_json."""
    monkeypatch.setenv("QUALITY_FILTER_USE_UNIFIED", "0")
    candidates = [{"title": "Some paper", "abstract": "abstract"}]

    legacy_response = [
        {"index": 0, "is_paper": False, "reason": "term entry"},
    ]

    with patch(PATCH_CONTRACT_LIST) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        out, prov = _call_llm_batch(candidates)

    assert prov == "fast_json"
    assert out == legacy_response
    assert mock_legacy.called
    assert not mock_unified.called


def test_call_llm_batch_unified_failure_returns_none(monkeypatch: Any) -> None:
    """Unified router returns failed ContractResult → None, heuristic fallback in node."""
    monkeypatch.setenv("QUALITY_FILTER_USE_UNIFIED", "1")
    candidates = [{"title": "Some paper", "abstract": "abstract"}]

    mock_result = MagicMock()
    mock_result.success = False
    mock_result.content = None
    mock_result.error = "semantic validation failed"

    with patch(PATCH_CONTRACT_LIST, return_value=mock_result):
        out, prov = _call_llm_batch(candidates)

    assert out is None
    assert prov == "unified_router"


def test_node_records_unified_provider_in_trace(monkeypatch: Any) -> None:
    """When gray-area candidates exist and unified router succeeds, trace records provider."""
    monkeypatch.setenv("QUALITY_FILTER_USE_UNIFIED", "1")
    # Candidate has no trusted URL/source so it reaches LLM gray-area.
    candidates = [
        {"title": "A genuinely ambiguous academic manuscript title", "abstract": "", "url": "", "source": ""},
    ]

    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = [
        {"index": 0, "is_paper": True, "reason": "academic title structure"},
    ]

    with patch(PATCH_CONTRACT_LIST, return_value=mock_result):
        result = quality_filter_node({
            "paper_candidates": candidates,
            "trace_events": [],
        })

    trace = result["trace_events"][0]
    llm_calls = [t for t in trace["tool_calls"] if t.get("tool") == "re13_quality_filter.llm"]
    assert llm_calls
    assert llm_calls[0].get("provider") == "unified_router"

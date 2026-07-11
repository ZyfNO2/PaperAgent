"""Re7.6 baseline_classifier unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from apps.api.app.services.agents.graph.nodes.baseline_classifier import (
    _llm_reclassify,
    baseline_classifier_node,
)


PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract"
PATCH_LEGACY = "apps.api.app.services.llm_router.call_json"


def _make_papers(n: int = 3) -> list[dict[str, Any]]:
    return [
        {"title": f"Paper {i}", "abstract": "abstract", "relation_to_topic": "baseline"}
        for i in range(n)
    ]


def test_llm_reclassify_uses_unified_router_by_default(monkeypatch: Any) -> None:
    """BASELINE_CLASSIFIER_USE_UNIFIED_ROUTER default=1 → call_with_contract."""
    monkeypatch.delenv("BASELINE_CLASSIFIER_USE_UNIFIED_ROUTER", raising=False)
    papers = _make_papers(3)
    classifications = [
        {"idx": 0, "role": "baseline"},
        {"idx": 1, "role": "parallel"},
        {"idx": 2, "role": "baseline"},
    ]
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = {"classifications": classifications}

    with patch(PATCH_CONTRACT, return_value=mock_result) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = _llm_reclassify(papers, "topic", ["method"], ["object"])

    assert mock_unified.called
    assert not mock_legacy.called
    assert result is not None
    assert len(result["baseline"]) == 2
    assert len(result["parallel"]) == 1
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "baseline-classify/v1"


def test_llm_reclassify_legacy_when_flag_off(monkeypatch: Any) -> None:
    """BASELINE_CLASSIFIER_USE_UNIFIED_ROUTER=0 falls back to legacy call_json."""
    monkeypatch.setenv("BASELINE_CLASSIFIER_USE_UNIFIED_ROUTER", "0")
    papers = _make_papers(3)
    legacy_response = {
        "classifications": [
            {"idx": 0, "role": "baseline"},
            {"idx": 1, "role": "parallel"},
            {"idx": 2, "role": "baseline"},
        ],
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        result = _llm_reclassify(papers, "topic", ["method"], ["object"])

    assert mock_legacy.called
    assert not mock_unified.called
    assert result is not None
    assert len(result["parallel"]) == 1


def test_llm_reclassify_returns_none_on_single_bucket() -> None:
    """If LLM puts everything in one bucket, keep original rule-based classification."""
    papers = _make_papers(3)
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = {
        "classifications": [
            {"idx": 0, "role": "baseline"},
            {"idx": 1, "role": "baseline"},
            {"idx": 2, "role": "baseline"},
        ],
    }

    with patch(PATCH_CONTRACT, return_value=mock_result):
        result = _llm_reclassify(papers, "topic", ["method"], ["object"])

    assert result is None


def test_node_skips_reclassify_when_disabled(monkeypatch: Any) -> None:
    """BASELINE_CLASSIFIER_DISABLE_LLM_RECLASSIFY=1 skips LLM call."""
    monkeypatch.setenv("BASELINE_CLASSIFIER_DISABLE_LLM_RECLASSIFY", "1")
    # All papers are baseline -> would normally trigger reclassify.
    papers = _make_papers(3)

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = baseline_classifier_node({
            "verified_papers": papers,
            "topic_atoms": {"method": ["m"], "object": ["o"]},
            "topic": "topic",
            "trace_events": [],
        })

    assert not mock_unified.called
    assert not mock_legacy.called
    assert len(result["baseline_candidates"]) == 3


def test_node_records_unified_provider_on_reclassify(monkeypatch: Any) -> None:
    """When reclassify triggers with unified router, trace records provider."""
    monkeypatch.setenv("BASELINE_CLASSIFIER_USE_UNIFIED_ROUTER", "1")
    monkeypatch.setenv("BASELINE_CLASSIFIER_DISABLE_LLM_RECLASSIFY", "0")
    papers = _make_papers(3)
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.content = {
        "classifications": [
            {"idx": 0, "role": "baseline"},
            {"idx": 1, "role": "parallel"},
            {"idx": 2, "role": "baseline"},
        ],
    }

    with patch(PATCH_CONTRACT, return_value=mock_result):
        result = baseline_classifier_node({
            "verified_papers": papers,
            "topic_atoms": {"method": ["m"], "object": ["o"]},
            "topic": "topic",
            "trace_events": [],
        })

    trace = result["trace_events"][0]
    assert trace["output_summary"]["llm_reclassified"] is True
    tool_call = trace["tool_calls"][0]
    assert tool_call.get("provider") == "unified_router"

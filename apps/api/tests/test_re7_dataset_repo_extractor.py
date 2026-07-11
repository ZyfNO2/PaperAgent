"""Re7.6 dataset_repo_extractor unified router migration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.dataset_repo_extractor import (
    dataset_repo_extractor_node,
)

PATCH_CONTRACT = "apps.api.app.services.router.call_with_contract_list"
PATCH_LEGACY = "apps.api.app.services.llm_router.call_json"


def _make_contract_result(content: list[dict[str, Any]] | None, success: bool = True, error: str | None = None) -> MagicMock:
    result = MagicMock()
    result.success = success
    result.content = content
    result.error = error
    return result


def test_default_uses_unified_router(monkeypatch: Any) -> None:
    """DATASET_REPO_USE_UNIFIED default=1 -> call_with_contract_list."""
    monkeypatch.delenv("DATASET_REPO_USE_UNIFIED", raising=False)
    extraction = {
        "dataset_name": "CrackTree",
        "official_code_url": "https://github.com/x/y",
        "status": "found",
    }

    state = {
        "verified_papers": [
            {"title": "Paper One", "abstract": "abstract"},
        ],
        "trace_events": [],
        "errors": [],
    }

    with patch(PATCH_CONTRACT, return_value=_make_contract_result([extraction])) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = dataset_repo_extractor_node(state)

    assert mock_unified.called
    assert not mock_legacy.called
    _, kwargs = mock_unified.call_args
    assert kwargs.get("contract_id") == "dataset-repo-list/v1"
    assert len(result["dataset_candidates"]) == 1
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert trace["tool_calls"][0]["mode"] == "unified_router"


def test_flag_off_uses_legacy_call_json(monkeypatch: Any) -> None:
    """DATASET_REPO_USE_UNIFIED=0 -> legacy llm_router.call_json."""
    monkeypatch.setenv("DATASET_REPO_USE_UNIFIED", "0")
    legacy_response = [
        {
            "dataset_name": "CrackTree",
            "official_code_url": "https://github.com/x/y",
            "status": "found",
        },
    ]

    state = {
        "verified_papers": [
            {"title": "Paper One", "abstract": "abstract"},
        ],
        "trace_events": [],
        "errors": [],
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY, return_value=legacy_response) as mock_legacy:
        result = dataset_repo_extractor_node(state)

    assert mock_legacy.called
    assert not mock_unified.called
    trace = result["trace_events"][0]
    assert trace["provider"] == "fast_json"
    assert trace["tool_calls"][0]["mode"] == "fast_json"


def test_unified_failure_returns_empty_and_records_fallback(monkeypatch: Any) -> None:
    """When unified router fails, extraction returns empty but trace stays unified."""
    monkeypatch.setenv("DATASET_REPO_USE_UNIFIED", "1")

    state = {
        "verified_papers": [
            {"title": "Paper One", "abstract": "abstract"},
        ],
        "trace_events": [],
        "errors": [],
    }

    with patch(PATCH_CONTRACT, return_value=_make_contract_result(None, success=False, error="router unavailable")) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = dataset_repo_extractor_node(state)

    assert mock_unified.called
    assert not mock_legacy.called
    assert len(result["dataset_candidates"]) == 0
    trace = result["trace_events"][0]
    assert trace["provider"] == "unified_router"
    assert trace["output_summary"]["llm_success_rate"] == "0/1"


def test_empty_papers_still_records_trace() -> None:
    """No verified papers -> no LLM call, trace provider defaults to fast_json."""
    state = {
        "verified_papers": [],
        "trace_events": [],
        "errors": [],
    }

    with patch(PATCH_CONTRACT) as mock_unified, \
         patch(PATCH_LEGACY) as mock_legacy:
        result = dataset_repo_extractor_node(state)

    assert not mock_unified.called
    assert not mock_legacy.called
    trace = result["trace_events"][0]
    assert trace["node"] == "dataset_repo"

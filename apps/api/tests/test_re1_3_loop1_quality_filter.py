"""Loop 1: Quality Filter unit test — 6 candidate types."""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.quality_filter import (
    quality_filter_node,
    _heuristic_filter,
)


def _make_state(candidates):
    return {
        "paper_candidates": candidates,
        "trace_events": [],
    }


CANDIDATES = [
    # 1. Normal paper
    {"title": "YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection",
     "abstract": "We propose an improved YOLOv5s model for bridge crack detection...",
     "url": "https://arxiv.org/abs/2401.12345", "source": "arxiv"},
    # 2. Term Entry
    {"title": "Deep Learning Core Term Entry",
     "abstract": "A glossary entry defining deep learning terminology.",
     "url": "https://example.com/term", "source": "openalex"},
    # 3. Core Concept
    {"title": "Core Concept: Convolutional Neural Networks",
     "abstract": "Core concept definition page for CNN.",
     "url": "https://example.com/concept", "source": "crossref"},
    # 4. Directory entry / Reference Entry
    {"title": "Reference Entry: Machine Learning Bibliography",
     "abstract": "A reference directory entry.",
     "url": "https://example.com/ref", "source": "openalex"},
    # 5. Title too short
    {"title": "CNN",
     "abstract": "Short title paper.",
     "url": "https://arxiv.org/abs/2010.001", "source": "arxiv"},
    # 6. Edge case: title only, no abstract, from arxiv
    {"title": "A Novel Approach to Monocular Depth Estimation Using Self-Supervised Learning",
     "abstract": "", "url": "https://arxiv.org/abs/2303.456", "source": "arxiv"},
]


def test_heuristic_filter_catches_non_papers():
    """Heuristic fallback should catch Term Entry, Core Concept, short title."""
    results = _heuristic_filter(CANDIDATES)
    is_paper_map = {idx: is_paper for idx, is_paper, _ in results}

    assert is_paper_map[0] is True   # normal paper
    assert is_paper_map[1] is False  # Term Entry
    assert is_paper_map[2] is False  # Core Concept
    assert is_paper_map[4] is False  # too short
    assert is_paper_map[5] is True   # edge case — has arxiv URL, keep


def test_heuristic_filter_has_reasons():
    results = _heuristic_filter(CANDIDATES)
    for idx, is_paper, reason in results:
        assert isinstance(reason, str) and len(reason) > 0


def test_quality_filter_node_with_llm_mock():
    """Test quality_filter_node with mocked LLM returning correct judgments.

    With the pre-filter architecture:
    - Index 0 (arxiv URL) → pre-filter keeps, LLM not called
    - Index 1 (Term Entry, pattern match) → pre-filter drops
    - Index 2 (Core Concept, pattern match) → pre-filter drops
    - Index 3 (source=openalex) → pre-filter keeps (academic source)
    - Index 4 (arxiv URL, title short but URL trusted) → pre-filter keeps
    - Index 5 (arxiv URL) → pre-filter keeps
    So LLM is not called at all — all candidates resolved by pre-filter.
    """
    # LLM mock is set but should NOT be called (all candidates resolved by pre-filter)
    llm_response = [
        {"index": 0, "is_paper": False, "reason": "should not be used"},
    ]

    with patch("apps.api.app.services.agents.graph.nodes.quality_filter._call_llm_batch",
               return_value=llm_response):
        result = quality_filter_node(_make_state(CANDIDATES))

    result["paper_candidates"]
    filter_results = result["filter_results"]

    assert filter_results["total"] == 6
    # Pre-filter keeps 0, 3, 4, 5 (arxiv URLs / openalex source), drops 1, 2 (patterns)
    assert filter_results["kept"] == 4  # indices 0, 3, 4, 5
    assert filter_results["dropped"] == 2  # indices 1, 2

    dropped_titles = [d["title"] for d in filter_results["dropped_items"]]
    assert "Deep Learning Core Term Entry" in dropped_titles
    assert "Core Concept: Convolutional Neural Networks" in dropped_titles

    # Each dropped item has a reason
    for d in filter_results["dropped_items"]:
        assert "reason" in d and d["reason"]


def test_quality_filter_node_llm_failure_fallback():
    """When LLM fails, heuristic fallback works for gray-area candidates.

    In this test data, all candidates are resolved by pre-filter (trusted URLs
    or pattern matches), so LLM is never called. This test verifies the node
    handles the case correctly even with LLM failure.
    """
    with patch("apps.api.app.services.agents.graph.nodes.quality_filter._call_llm_batch",
               return_value=None):
        result = quality_filter_node(_make_state(CANDIDATES))

    filter_results = result["filter_results"]
    # Pre-filter drops Term Entry and Core Concept
    assert filter_results["dropped"] >= 2
    dropped_titles = [d["title"] for d in filter_results["dropped_items"]]
    assert "Deep Learning Core Term Entry" in dropped_titles
    assert "Core Concept: Convolutional Neural Networks" in dropped_titles


def test_quality_filter_never_drops_all():
    """Safety: quality_filter should never drop all candidates.

    Both candidates match non-paper patterns (Term Entry, Input Classification)
    but the safety check keeps all when everything would be dropped.
    """
    candidates = [
        {"title": "Question Answering Input Classification", "abstract": "", "url": "", "source": "openalex"},
        {"title": "Deep Learning Term Entry", "abstract": "", "url": "", "source": "openalex"},
    ]
    with patch("apps.api.app.services.agents.graph.nodes.quality_filter._call_llm_batch",
               return_value=None):
        result = quality_filter_node(_make_state(candidates))

    # Should keep all as safety
    assert len(result["paper_candidates"]) >= 1


def test_quality_filter_empty_candidates():
    result = quality_filter_node(_make_state([]))
    assert result["paper_candidates"] == []
    assert result["filter_results"]["total"] == 0


def test_quality_filter_trace_recorded():
    # Candidate 0 has arxiv URL → pre-filter keeps it, LLM not needed
    result = quality_filter_node(_make_state([CANDIDATES[0]]))

    traces = result["trace_events"]
    assert len(traces) == 1
    assert traces[0]["node"] == "quality_filter"
    assert "kept" in traces[0]["output_summary"]
    assert "dropped" in traces[0]["output_summary"]

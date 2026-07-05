"""Loop 6: Auto seed selection test — verify seeds are auto-selected from verified_papers."""
from __future__ import annotations

import pytest
from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.citation_expander import (
    _select_seeds,
    citation_expander_node,
)


def test_auto_seed_selection_basic():
    """Seeds should be auto-selected from verified_papers without user input."""
    verified = [
        {
            "title": "YOLOv5 Paper",
            "hit_keywords": ["yolov5", "detection"],
            "relation_to_topic": "baseline",
            "paper_id": "pid1",
            "doi": "10.1/a",
            "citation_count": 100,
        },
        {
            "title": "Second Paper",
            "hit_keywords": ["detection"],
            "relation_to_topic": "parallel",
            "paper_id": "pid2",
            "citation_count": 20,
        },
    ]
    topic_atoms = {"method": ["yolov5"], "object": ["defect"], "task": ["detection"]}

    seeds = _select_seeds(verified, topic_atoms, top_n=5)

    assert len(seeds) > 0
    # Top seed should be YOLOv5 (more keyword overlap)
    assert "YOLOv5" in seeds[0]["title"]


def test_auto_seed_has_relevance_score():
    verified = [
        {
            "title": "Test Paper",
            "hit_keywords": ["test"],
            "relation_to_topic": "baseline",
            "paper_id": "pid1",
        },
    ]
    topic_atoms = {"method": ["test"]}

    seeds = _select_seeds(verified, topic_atoms, top_n=5)
    assert len(seeds) == 1
    assert "relevance_score" in seeds[0]
    assert isinstance(seeds[0]["relevance_score"], int)
    assert seeds[0]["relevance_score"] > 0


def test_auto_seed_has_selection_reason():
    verified = [
        {
            "title": "Test",
            "hit_keywords": ["test"],
            "relation_to_topic": "baseline",
            "paper_id": "pid1",
        },
    ]
    topic_atoms = {"method": ["test"]}

    seeds = _select_seeds(verified, topic_atoms, top_n=5)
    assert "seed_selection_reason" in seeds[0]
    assert "relevance_score=" in seeds[0]["seed_selection_reason"]


def test_auto_seed_requires_identifier():
    """Papers without paperId/DOI/arXiv ID should be skipped."""
    verified = [
        {"title": "No ID", "hit_keywords": ["test"], "relation_to_topic": "baseline"},
        {"title": "Has DOI", "hit_keywords": ["test"], "relation_to_topic": "baseline", "doi": "10.1/x"},
    ]
    topic_atoms = {"method": ["test"]}

    seeds = _select_seeds(verified, topic_atoms, top_n=5)
    assert len(seeds) == 1
    assert "Has DOI" in seeds[0]["title"]


def test_auto_seed_top1_is_highest_score():
    """The first seed should have the highest relevance score."""
    verified = [
        {"title": "Low Score", "hit_keywords": [], "relation_to_topic": "none", "paper_id": "p1"},
        {"title": "High Score", "hit_keywords": ["match1", "match2"], "relation_to_topic": "baseline", "paper_id": "p2"},
    ]
    topic_atoms = {"method": ["match1", "match2"]}

    seeds = _select_seeds(verified, topic_atoms, top_n=5)
    assert len(seeds) == 2
    assert seeds[0]["relevance_score"] >= seeds[1]["relevance_score"]
    assert "High Score" in seeds[0]["title"]


def test_citation_expander_auto_selects_seeds():
    """Full node should auto-select seeds and populate seed_papers in state."""
    verified = [
        {
            "title": "YOLOv5 Detection",
            "hit_keywords": ["yolov5"],
            "relation_to_topic": "baseline",
            "paper_id": "pid1",
            "citation_count": 50,
        },
    ]
    state = {
        "verified_papers": verified,
        "topic_atoms": {"method": ["yolov5"]},
        "trace_events": [],
    }

    async def mock_refs(*args, **kwargs):
        return [{"title": "Ref Paper", "paper_id": "r1"}]

    async def mock_cits(*args, **kwargs):
        return [{"title": "Cit Paper", "paper_id": "c1"}]

    with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_references",
               side_effect=mock_refs):
        with patch("apps.api.app.services.retrieval.adapters.semantic_scholar_search.semantic_scholar_citations",
                   side_effect=mock_cits):
            result = citation_expander_node(state)

    assert len(result["seed_papers"]) >= 1
    assert result["seed_papers"][0]["relevance_score"] > 0
    assert result["citation_expansion_done"] is True

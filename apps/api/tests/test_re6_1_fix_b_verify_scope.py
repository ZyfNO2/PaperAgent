"""Re6.1 Fix B: empty expansion skips verify — unit tests.

Acceptance criteria from SOP §3:
  1. Input: 7 accepted + expanded_papers=[] → verify call count = 0, 7 papers preserved.
  2. Input: 1 new expanded paper → verify only that one, deduped-merged with existing.
  3. quality_filter → verify always sets verify_scope="search".
  4. citation_expander → verify always sets verify_scope="expanded".
"""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.citation_expander import (
    citation_expander_node,
)
from apps.api.app.services.agents.graph.nodes.verify import verify_node
from apps.api.app.services.agents.graph.nodes.quality_filter import (
    quality_filter_node,
)
from apps.api.app.services.agents.graph.research_graph import (
    _route_after_citation_expander,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_verified(title: str, **kw) -> dict:
    return {
        "title": title,
        "hit_keywords": kw.get("hit_keywords", ["YOLO"]),
        "relation_to_topic": kw.get("relation_to_topic", "baseline"),
        "paper_id": kw.get("paper_id", f"pid_{title[:8]}"),
        "doi": kw.get("doi"),
        "arxiv_id": kw.get("arxiv_id"),
        "citation_count": kw.get("citation_count", 10),
        "verdict": "accept",
    }


SEVEN_ACCEPTED = [_make_verified(f"Accepted Paper {i}") for i in range(7)]

ONE_EXPANDED = [
    {
        "title": "New Expanded Paper",
        "paper_id": "expanded_001",
        "hit_keywords": ["YOLO"],
        "relation_to_topic": "baseline",
        "citation_count": 5,
    },
]


# ---------------------------------------------------------------------------
# _route_after_citation_expander
# ---------------------------------------------------------------------------

def test_route_after_citation_expander_verify_when_expanded():
    state = {"expanded_papers": ONE_EXPANDED}
    assert _route_after_citation_expander(state) == "verify"


def test_route_after_citation_expander_skip_when_empty():
    state = {"expanded_papers": []}
    assert _route_after_citation_expander(state) == "skip"


def test_route_after_citation_expander_skip_when_missing_key():
    state = {}
    assert _route_after_citation_expander(state) == "skip"


# ---------------------------------------------------------------------------
# verify_scope propagation
# ---------------------------------------------------------------------------

def test_quality_filter_sets_verify_scope_search():
    state = {
        "paper_candidates": [_make_verified("Test Paper")],
        "topic_atoms": {"method": ["YOLO"], "object": [], "task": []},
        "trace_events": [],
    }
    result = quality_filter_node(state)
    assert result.get("verify_scope") == "search"


def test_citation_expander_sets_verify_scope_expanded():
    """Even when expansion is empty, verify_scope must be 'expanded'."""
    state = {
        "verified_papers": [_make_verified("No Expansion Seed", paper_id=None, doi=None, arxiv_id=None)],
        "topic_atoms": {},
        "trace_events": [],
    }
    result = citation_expander_node(state)
    assert result.get("verify_scope") == "expanded"


# ---------------------------------------------------------------------------
# verify_node: empty expansion preserves accepted papers
# ---------------------------------------------------------------------------

def test_verify_empty_expansion_preserves_7_accepted():
    """SOP §3 acceptance #1: 7 accepted + [] expanded → 0 verify calls, 7 preserved.

    With verify_scope="expanded" and expanded_papers=[], verify_node should
    produce an empty candidates list (no LLM call), and the existing
    verified_papers must remain untouched.
    """
    state = {
        "topic": "YOLO-based steel defect detection",
        "topic_atoms": {"method": ["YOLO"], "object": ["steel"], "task": ["detection"]},
        "citation_expansion_done": True,
        "verify_scope": "expanded",
        "expanded_papers": [],
        "verified_papers": [dict(p) for p in SEVEN_ACCEPTED],
        "paper_candidates": [dict(p) for p in SEVEN_ACCEPTED],
        "weak_papers": [],
        "trace_events": [],
        "errors": [],
    }
    result = verify_node(state)
    assert len(result["verified_papers"]) == 7, \
        f"Expected 7 preserved, got {len(result['verified_papers'])}"
    # No new papers added
    assert result["verified_papers"] == SEVEN_ACCEPTED


def test_verify_search_scope_uses_paper_candidates():
    """verify_scope='search' → candidates come from paper_candidates."""
    state = {
        "topic": "YOLO-based steel defect detection",
        "topic_atoms": {"method": ["YOLO"], "object": ["steel"], "task": ["detection"]},
        "citation_expansion_done": False,
        "verify_scope": "search",
        "paper_candidates": [dict(p) for p in SEVEN_ACCEPTED],
        "verified_papers": [],
        "weak_papers": [],
        "trace_events": [],
        "errors": [],
    }
    # Mock the LLM to avoid actual calls; just check candidates path
    with patch(
        "apps.api.app.services.agents.graph.nodes.verify._call_verifier",
        return_value=[],  # LLM returns nothing
    ):
        result = verify_node(state)
    # verify was called with candidates from paper_candidates
    # (7 candidates sent to LLM, all lost because LLM returned empty)
    assert result["trace_events"][0]["input_summary"]["n_candidates"] == 7


def test_verify_expanded_scope_only_verifies_expanded():
    """SOP §3 acceptance #2: 1 expanded paper → verify only that one.

    Uses verify_scope='expanded' so expanded_papers are the candidates,
    not paper_candidates (which held the 7 already-accepted).
    """
    state = {
        "topic": "YOLO-based steel defect detection",
        "topic_atoms": {"method": ["YOLO"], "object": ["steel"], "task": ["detection"]},
        "citation_expansion_done": True,
        "verify_scope": "expanded",
        "expanded_papers": [dict(p) for p in ONE_EXPANDED],
        "verified_papers": [dict(p) for p in SEVEN_ACCEPTED],
        "paper_candidates": [dict(p) for p in SEVEN_ACCEPTED],
        "weak_papers": [],
        "trace_events": [],
        "errors": [],
    }

    # Mock LLM to accept the one expanded paper
    def _fake_verifier(topic, atoms, candidates):
        return [{"title": c["title"], "verdict": "accept",
                 "hit_keywords": ["YOLO"], "relation_to_topic": "baseline",
                 "reason": "LLM stub"} for c in candidates]

    with patch(
        "apps.api.app.services.agents.graph.nodes.verify._call_verifier",
        side_effect=_fake_verifier,
    ):
        result = verify_node(state)

    # 7 existing + 1 new = 8 total
    assert len(result["verified_papers"]) == 8, \
        f"Expected 8 total, got {len(result['verified_papers'])}"
    titles = [p["title"] for p in result["verified_papers"]]
    assert "New Expanded Paper" in titles
    # Trace shows only 1 candidate was sent to LLM
    assert result["trace_events"][0]["input_summary"]["n_candidates"] == 1

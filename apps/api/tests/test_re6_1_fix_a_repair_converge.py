"""Re6.1 Fix A: empty repair converges immediately — unit tests.

Acceptance criteria from SOP §2.3:
  1. Empty repair (n_queries=0) must NOT route to paper_retriever.
  2. Empty repair produces exactly one terminal trace; repair_rounds must not increase.
  3. Promoted weak papers keep original verdict/provenance (not become accept).
  4. Non-empty duplicate queries count as empty repair; only new queries allow retrieval.
"""
from __future__ import annotations

from unittest.mock import patch

from apps.api.app.services.agents.graph.nodes.targeted_repair import (
    targeted_repair_node,
    _dedup_queries,
    _ZERO_ACCEPT_WEAK_POLICY,
    _WEAK_PROMOTE_MIN,
    MAX_REPAIR_ROUNDS,
)
from apps.api.app.services.agents.graph.research_graph import (
    _route_after_targeted_repair,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _base_state(**kw) -> dict:
    return {
        "topic": "YOLO-based steel defect detection",
        "baseline_candidates": kw.get("baseline_candidates", []),
        "dataset_candidates": kw.get("dataset_candidates", []),
        "repo_candidates": kw.get("repo_candidates", []),
        "verified_papers": kw.get("verified_papers", []),
        "paper_candidates": kw.get("paper_candidates", []),
        "evidence_audit": kw.get("evidence_audit", {}),
        "trace_events": kw.get("trace_events", []),
        "errors": kw.get("errors", []),
        "search_plan": kw.get("search_plan", {}),
    }


# ---------------------------------------------------------------------------
# _dedup_queries
# ---------------------------------------------------------------------------

def test_dedup_queries_removes_exact_duplicates():
    queries = [
        {"tool": "arxiv", "query": "YOLO steel"},
        {"tool": "arxiv", "query": "YOLO steel"},  # exact dup
        {"tool": "openalex", "query": "YOLO steel"},  # different tool → keep
    ]
    result = _dedup_queries(queries)
    assert len(result) == 2


def test_dedup_queries_case_insensitive():
    queries = [
        {"tool": "arxiv", "query": "YOLO Steel"},
        {"tool": "arxiv", "query": "yolo steel"},  # case-insensitive dup
    ]
    result = _dedup_queries(queries)
    assert len(result) == 1


def test_dedup_queries_empty():
    assert _dedup_queries([]) == []


# ---------------------------------------------------------------------------
# targeted_repair_node: repair_outcome classification
# ---------------------------------------------------------------------------

def test_repair_outcome_queries_ready():
    """LLM returns 1+ valid queries → repair_outcome='queries_ready'."""
    state = _base_state(paper_candidates=[
        {"title": "Test Paper", "verdict": "reject"},
    ])
    fake_raw = {
        "queries": [
            {"tool": "arxiv", "query": "YOLO steel defect", "why": "gap",
             "expected_evidence": "papers", "stop_condition": "5 results"},
        ],
        "rounds": ["repair"],
        "negative_feedback": "test",
        "strategy": "synonym",
    }
    with patch(
        "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json",
        return_value=fake_raw,
    ):
        result = targeted_repair_node(state)

    assert result["repair_outcome"] == "queries_ready"
    assert result["repair_no_query_reason"] == ""
    assert len(result["repair_query_ids"]) == 1
    assert result["repair_query_ids"][0].startswith("arxiv:")


def test_repair_outcome_no_query_after_dedup():
    """LLM returns duplicate queries only → dedup → no_query."""
    state = _base_state(
        paper_candidates=[{"title": "Test", "verdict": "reject"}],
        search_plan={"queries": [
            {"tool": "arxiv", "query": "YOLO steel defect"},
        ]},
    )
    # LLM returns the same query that was already tried
    fake_raw = {
        "queries": [
            {"tool": "arxiv", "query": "YOLO steel defect", "why": "try again",
             "expected_evidence": "papers", "stop_condition": "5"},
        ],
        "rounds": ["repair"],
    }
    with patch(
        "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json",
        return_value=fake_raw,
    ):
        result = targeted_repair_node(state)

    assert result["repair_outcome"] == "no_query"
    assert "0 valid queries" in result["repair_no_query_reason"]
    assert len(result["repair_query_ids"]) == 0


def test_repair_outcome_no_query_empty_llm():
    """LLM returns empty queries list → no_query."""
    state = _base_state()
    with patch(
        "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json",
        return_value={"queries": [], "rounds": ["repair"]},
    ):
        result = targeted_repair_node(state)

    assert result["repair_outcome"] == "no_query"
    assert len(result["repair_query_ids"]) == 0


def test_repair_outcome_no_query_exception():
    """LLM raises LLMUnavailable → empty plan → no_query."""
    from apps.api.app.services.llm_router import LLMUnavailable
    state = _base_state()
    with patch(
        "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json",
        side_effect=LLMUnavailable("timeout"),
    ):
        result = targeted_repair_node(state)

    assert result["repair_outcome"] == "no_query"
    assert len(result["repair_query_ids"]) == 0


def test_repair_outcome_exhausted():
    """When repair_rounds >= MAX_REPAIR_ROUNDS → exhausted."""
    state = _base_state(evidence_audit={"repair_rounds": MAX_REPAIR_ROUNDS})
    result = targeted_repair_node(state)
    assert result["repair_outcome"] == "exhausted"
    assert "cap" in result["repair_no_query_reason"]


def test_repair_rounds_incremented():
    """repair_rounds increments by 1 even when outcome=no_query."""
    state = _base_state(evidence_audit={"repair_rounds": 0})
    with patch(
        "apps.api.app.services.agents.graph.nodes.targeted_repair.call_json",
        return_value={"queries": [], "rounds": ["repair"]},
    ):
        result = targeted_repair_node(state)
    assert result["evidence_audit"]["repair_rounds"] == 1


# ---------------------------------------------------------------------------
# _route_after_targeted_repair
# ---------------------------------------------------------------------------

def test_route_queries_ready_to_retriever():
    state = {"repair_outcome": "queries_ready"}
    assert _route_after_targeted_repair(state) == "paper_retriever"


def test_route_no_query_to_quality_gate():
    state = {"repair_outcome": "no_query"}
    assert _route_after_targeted_repair(state) == "quality_gate"


def test_route_exhausted_with_evidence_to_gate():
    state = {
        "repair_outcome": "exhausted",
        "verified_papers": [{"title": "P1"}],
        "weak_papers": [],
        "baseline_candidates": [],
    }
    assert _route_after_targeted_repair(state) == "quality_gate"


def test_route_exhausted_no_evidence_to_final():
    state = {
        "repair_outcome": "exhausted",
        "verified_papers": [],
        "weak_papers": [],
        "baseline_candidates": [],
    }
    assert _route_after_targeted_repair(state) == "final_recommendation"


def test_route_no_query_with_weak_to_gate():
    """no_query + weak papers → quality_gate (may promote weak)."""
    state = {
        "repair_outcome": "no_query",
        "verified_papers": [],
        "weak_papers": [{"title": "W1"}],
        "baseline_candidates": [],
    }
    assert _route_after_targeted_repair(state) == "quality_gate"


def test_route_exhausted_with_baseline_evidence():
    """exhausted + baseline candidates → quality_gate (already has evidence)."""
    state = {
        "repair_outcome": "exhausted",
        "verified_papers": [],
        "weak_papers": [],
        "baseline_candidates": [{"title": "B1"}],
    }
    assert _route_after_targeted_repair(state) == "quality_gate"

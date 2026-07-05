"""Unit tests for json_graph_builder node."""
from __future__ import annotations

from apps.api.app.services.agents.graph.nodes.json_graph_builder import (
    json_graph_builder_node,
)
from apps.api.app.services.agents.graph.state import ResearchState


def _base_state() -> ResearchState:
    return {
        "case_id": "test",
        "topic": "test topic",
        "verified_papers": [
            {"title": "Paper A", "relation_to_topic": "baseline"},
            {"title": "Paper B", "relation_to_topic": "parallel"},
        ],
        "dataset_candidates": [
            {"name": "Dataset X", "linked_paper_id": "paper-a", "url": "http://x"},
        ],
        "repo_candidates": [
            {"url": "https://github.com/owner/repo", "linked_paper_id": "paper-b"},
        ],
        "baseline_candidates": [
            {"title": "Paper A"},
            {"title": "Paper C"},
        ],
        "parallel_candidates": [
            {"title": "Paper B", "improved_module_source": "Paper A"},
        ],
        "work_packages": [
            {"slug": "wp-1", "title": "WP 1", "baseline": "Paper A",
             "data_source": "Dataset X", "experiment_metrics": "Paper B"},
        ],
        "evidence_audit": {"repair_rounds": 1},
        "trace_events": [],
        "errors": [],
    }


def test_graph_builder_produces_nodes_and_edges() -> None:
    state = _base_state()
    out = json_graph_builder_node(state)
    g = out["evidence_graph"]
    assert "nodes" in g
    assert "edges" in g
    # 2 paper + 1 dataset + 1 repo + 2 baseline (paper-a, paper-c) + 1 parallel + 1 workpkg
    assert len(g["nodes"]) >= 5
    # edges: dataset-linked, repo-linked, implements, cites×3, needs_repair×?
    assert len(g["edges"]) >= 3


def test_graph_builder_ids_are_kebab() -> None:
    state = _base_state()
    out = json_graph_builder_node(state)
    g = out["evidence_graph"]
    for n in g["nodes"]:
        assert ":" in n["id"], f"missing prefix in {n['id']}"
        # kebab-case: only lowercase, digits, hyphens
        cid = n["id"].split(":", 1)[1]
        assert cid == cid.lower() and " " not in cid, f"bad id fragment: {cid}"


def test_graph_builder_no_duplicate_edges() -> None:
    state = _base_state()
    out = json_graph_builder_node(state)
    g = out["evidence_graph"]
    seen = set()
    for e in g["edges"]:
        key = (e["source"], e["target"], e["type"])
        assert key not in seen, f"duplicate edge: {key}"
        seen.add(key)


def test_graph_builder_edge_types_valid() -> None:
    from apps.api.app.services.agents.graph.nodes.json_graph_builder import _EDGE_TYPES
    state = _base_state()
    out = json_graph_builder_node(state)
    for e in out["evidence_graph"]["edges"]:
        assert e["type"] in _EDGE_TYPES, f"invalid edge type: {e['type']}"


def test_graph_builder_empty_state() -> None:
    state: ResearchState = {
        "case_id": "empty", "topic": "", "verified_papers": [],
        "dataset_candidates": [], "repo_candidates": [],
        "baseline_candidates": [], "parallel_candidates": [],
        "work_packages": [], "evidence_audit": {}, "trace_events": [], "errors": [],
    }
    out = json_graph_builder_node(state)
    assert out["evidence_graph"] == {"nodes": [], "edges": []}
    assert out["evidence_audit"]["graph_built"] is True


def test_graph_builder_quarantine() -> None:
    state = _base_state()
    state["verified_papers"] = [
        {"title": "Paper A", "relation_to_topic": "baseline", "quarantined": True},
        {"title": "Paper B", "relation_to_topic": "parallel"},
    ]
    out = json_graph_builder_node(state)
    g = out["evidence_graph"]
    q_nodes = [n for n in g["nodes"] if n["type"] == "quarantine"]
    assert len(q_nodes) == 1
    assert q_nodes[0]["id"] == "quarantine:<paper-a>"

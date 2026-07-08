"""Re3.3 P0 verification: final_recommendation_node must produce non-zero counts.

The audit found state.json files where final_recommendation had all-zero
counts despite verified_papers/repo_candidates containing data. This was
caused by old code reading from evidence_audit field names that didn't exist.
The fix reads directly from state lists. This test proves the fix works.
"""
from __future__ import annotations

import sys
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))

from apps.api.app.services.agents.graph.nodes.content import final_recommendation_node  # noqa: E402


def test_final_recommendation_counts_match_state_lists():
    """Counts in final_recommendation must equal len() of corresponding state lists."""
    state = {
        "verified_papers": [{"title": "a"}, {"title": "b"}, {"title": "c"}, {"title": "d"}],
        "baseline_candidates": [{"title": "baseline-1"}, {"title": "baseline-2"}],
        "parallel_candidates": [{"title": "parallel-1"}],
        "dataset_candidates": [{"name": "COCO"}, {"name": "VOC"}],
        "repo_candidates": [{"url": "github.com/x"}, {"url": "github.com/y"}, {"url": "github.com/z"}],
        "work_packages": [{"id": "wp1"}, {"id": "wp2"}],
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "topic": "test topic",
        "trace_events": [],
        "errors": [],
    }
    result = final_recommendation_node(state)
    rec = result["final_recommendation"]

    assert rec["n_papers"] == 4, f"n_papers should be 4, got {rec['n_papers']}"
    assert rec["n_baseline"] == 2, f"n_baseline should be 2, got {rec['n_baseline']}"
    assert rec["n_parallel"] == 1, f"n_parallel should be 1, got {rec['n_parallel']}"
    assert rec["n_dataset"] == 2, f"n_dataset should be 2, got {rec['n_dataset']}"
    assert rec["n_repo"] == 3, f"n_repo should be 3, got {rec['n_repo']}"
    assert rec["n_work_packages"] == 2, f"n_work_packages should be 2, got {rec['n_work_packages']}"


def test_final_recommendation_empty_state():
    """Empty state should produce all-zero counts without crashing."""
    state = {
        "verified_papers": [],
        "baseline_candidates": [],
        "parallel_candidates": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "work_packages": [],
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "trace_events": [],
        "errors": [],
    }
    result = final_recommendation_node(state)
    rec = result["final_recommendation"]

    assert rec["n_papers"] == 0
    assert rec["n_baseline"] == 0
    assert rec["n_repo"] == 0
    assert rec["n_work_packages"] == 0


def test_final_recommendation_v_yolo_33_scenario():
    """Replicate V-YOLO-33 scenario: 4 papers, 2 baselines, 12 repos, 0 datasets."""
    state = {
        "verified_papers": [{"title": f"paper-{i}"} for i in range(4)],
        "baseline_candidates": [{"title": "baseline-1"}, {"title": "baseline-2"}],
        "parallel_candidates": [],
        "dataset_candidates": [],
        "repo_candidates": [{"url": f"github.com/repo-{i}"} for i in range(12)],
        "work_packages": [{"id": f"wp-{i}"} for i in range(4)],
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "topic": "yolo crop recognition",
        "trace_events": [],
        "errors": [],
    }
    result = final_recommendation_node(state)
    rec = result["final_recommendation"]

    # The key assertion: these must NOT be zero
    assert rec["n_papers"] == 4, f"n_papers should be 4 (was 0 in stale state.json), got {rec['n_papers']}"
    assert rec["n_baseline"] == 2, f"n_baseline should be 2, got {rec['n_baseline']}"
    assert rec["n_repo"] == 12, f"n_repo should be 12 (was 0 in stale state.json), got {rec['n_repo']}"
    assert rec["n_work_packages"] == 4

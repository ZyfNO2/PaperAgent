"""Self-test validator: end-to-end completeness.

Checks that the research graph ran all expected nodes and produced a final recommendation.
"""
from __future__ import annotations

from typing import Any


EXPECTED_NODES = [
    "intake",
    "topic_parser",
    "search_planner",
    "retrieve",
    "quality_filter",
    "verify",
    "quality_gate",
    "dataset_repo",
    "json_graph_builder",
    "evidence_auditor",
    "work_package",
    "low_bar_review",
    "human_gate",
    "final_recommendation",
    "feasibility_assessor",
    "innovation_extractor",
    "sota_matcher",
    "narrative_builder",
    "optimization_advisor",
    "devils_advocate",
]


def validate(state: dict[str, Any]) -> dict[str, Any]:
    """Validate that the graph executed completely.

    Returns:
        dict with keys: pass (bool), n_expected, n_found, missing_nodes,
        has_final, n_trace_events, details
    """
    traces = state.get("trace_events") or []
    found_nodes = {t.get("node", "") for t in traces}

    missing = [n for n in EXPECTED_NODES if n not in found_nodes]
    has_final = bool(state.get("final_recommendation"))
    n_trace = len(traces)

    passed = len(missing) == 0 and has_final and n_trace >= len(EXPECTED_NODES)

    return {
        "pass": passed,
        "n_expected": len(EXPECTED_NODES),
        "n_found": len(found_nodes & set(EXPECTED_NODES)),
        "missing_nodes": missing,
        "has_final": has_final,
        "n_trace_events": n_trace,
        "details": (
            f"All {len(EXPECTED_NODES)} expected nodes present, final_recommendation exists"
            if passed
            else f"Missing nodes: {missing}, has_final={has_final}, n_trace={n_trace}"
        ),
    }

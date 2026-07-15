"""Re8.2 additive final-recommendation audit wrapper.

The legacy final recommendation remains the source of truth for verdicts and
the seven canonical package sections. Gate execution metadata is attached under
``gate_results._execution`` and on the recommendation object, so reuse remains
auditable without turning the canonical seven-section package into an eighth
section.
"""
from __future__ import annotations

import copy
import time
from typing import Any

from apps.api.app.services.agents.graph.state import ResearchState
from . import content as _legacy
from ._util import emit_trace as _emit


def _gate_execution_summary(state: ResearchState) -> dict[str, Any]:
    return {
        "last_gate_pass": copy.deepcopy(state.get("last_gate_pass") or {}),
        "cycle_id": copy.deepcopy(state.get("gate_cycle_id") or {}),
        "cycle_start_index": copy.deepcopy(state.get("gate_cycle_start_index") or {}),
        "input_fingerprint": copy.deepcopy(state.get("gate_input_fingerprint") or {}),
        "reuse_count": copy.deepcopy(state.get("gate_reuse_count") or {}),
        "evaluation_events": copy.deepcopy(state.get("gate_evaluation_events") or []),
        "reuse_events": copy.deepcopy(state.get("gate_reuse_events") or []),
    }


def final_recommendation_node(state: ResearchState) -> dict[str, Any]:
    t0 = time.time()
    patch = dict(_legacy.final_recommendation_node(state))
    package = copy.deepcopy(patch.get("final_research_package") or {})
    execution = _gate_execution_summary(state)

    # Gate execution is extension metadata, not an eighth canonical section.
    package.pop("gate_execution", None)
    gate_results = package.get("gate_results")
    if not isinstance(gate_results, dict):
        gate_results = {}
    gate_results = copy.deepcopy(gate_results)
    gate_results["_execution"] = execution
    package["gate_results"] = gate_results

    recommendation = copy.deepcopy(patch.get("final_recommendation") or {})
    recommendation["research_package"] = package
    recommendation["gate_execution"] = execution

    trace = _emit(
        "final_recommendation_re82_gate_audit",
        t0,
        {
            "n_evaluation_events": len(state.get("gate_evaluation_events") or []),
            "n_reuse_events": len(state.get("gate_reuse_events") or []),
        },
        {
            "gate_execution_present": True,
            "canonical_package_section_count": len(package),
            "reuse_count": execution["reuse_count"],
        },
        [],
        "local",
        [],
        state_keys=["final_recommendation", "final_research_package", "trace_events"],
    )

    patch["final_research_package"] = package
    patch["final_recommendation"] = recommendation
    patch["trace_events"] = list(patch.get("trace_events") or []) + [trace]
    return patch


__all__ = ["final_recommendation_node"]

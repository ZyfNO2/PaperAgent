"""Re8.2 additive final-recommendation audit wrapper.

The legacy final recommendation remains the source of truth for verdicts and
the seven canonical package sections. Tailor execution metadata is nested on
the Tailor Gate result and on the recommendation object, so reuse remains
auditable without creating either an eighth package section or a pseudo Gate.
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

    # Gate execution is extension metadata, not an eighth canonical section or
    # a fourth pseudo Gate. Attach it to the Tailor Gate result it describes.
    package.pop("gate_execution", None)
    gate_results = package.get("gate_results")
    if not isinstance(gate_results, dict):
        gate_results = {}
    gate_results = copy.deepcopy(gate_results)
    gate_results.pop("_execution", None)  # migrate the short-lived review shape
    tailor_result = gate_results.get("tailor_gate")
    if not isinstance(tailor_result, dict):
        tailor_result = {}
    tailor_result = copy.deepcopy(tailor_result)
    tailor_result["execution"] = execution
    gate_results["tailor_gate"] = tailor_result
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
            "gate_result_keys": sorted(gate_results),
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

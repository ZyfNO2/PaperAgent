"""Re8.2 WP1 final research package audit tests."""
from __future__ import annotations

import copy

from apps.api.app.services.agents.graph.nodes import final_recommendation_re82 as wrapper


def _legacy_patch():
    package = {"gate_results": {"tailor_gate": {"verdict": "pass"}}}
    return {
        "final_recommendation": {"research_package": copy.deepcopy(package)},
        "final_research_package": copy.deepcopy(package),
        "fused_verdict": "GO",
        "fused_verdict_rationale": "all checks passed",
        "trace_events": [{"node": "legacy"}],
    }


def test_gate_execution_is_added_to_both_package_locations(monkeypatch):
    monkeypatch.setattr(wrapper._legacy, "final_recommendation_node", lambda state: _legacy_patch())
    state = {
        "last_gate_pass": {"tailor_gate": {"verdict": "pass", "cycle_id": 0}},
        "gate_cycle_id": {"tailor_gate": 0},
        "gate_cycle_start_index": {"tailor_gate": 0},
        "gate_input_fingerprint": {"tailor_gate": "sha256:abc"},
        "gate_reuse_count": {"tailor_gate": 2},
        "gate_evaluation_events": [{"event_type": "gate_evaluated"}],
        "gate_reuse_events": [{"event_type": "gate_pass_reused"}],
    }

    patch = wrapper.final_recommendation_node(state)
    top = patch["final_research_package"]["gate_execution"]
    nested = patch["final_recommendation"]["research_package"]["gate_execution"]

    assert top == nested
    assert top["reuse_count"]["tailor_gate"] == 2
    assert top["input_fingerprint"]["tailor_gate"] == "sha256:abc"
    assert top["reuse_events"][0]["event_type"] == "gate_pass_reused"
    assert len(patch["trace_events"]) == 2


def test_missing_gate_metadata_degrades_to_empty_collections(monkeypatch):
    monkeypatch.setattr(wrapper._legacy, "final_recommendation_node", lambda state: _legacy_patch())
    patch = wrapper.final_recommendation_node({})
    audit = patch["final_research_package"]["gate_execution"]

    assert audit["last_gate_pass"] == {}
    assert audit["cycle_id"] == {}
    assert audit["reuse_count"] == {}
    assert audit["evaluation_events"] == []
    assert audit["reuse_events"] == []


def test_wrapper_does_not_mutate_source_state(monkeypatch):
    monkeypatch.setattr(wrapper._legacy, "final_recommendation_node", lambda state: _legacy_patch())
    state = {
        "gate_reuse_count": {"tailor_gate": 1},
        "gate_reuse_events": [{"event_type": "gate_pass_reused"}],
    }
    before = copy.deepcopy(state)
    wrapper.final_recommendation_node(state)
    assert state == before

"""Re8.2 WP1 final research package audit tests."""
from __future__ import annotations

import copy

from apps.api.app.services.agents.graph.nodes import final_recommendation_re82 as wrapper


_CANONICAL_SECTIONS = {
    "seed_audit_summary": [],
    "tailor_summary": {},
    "gate_results": {"tailor_gate": {"verdict": "pass"}},
    "ledger_entries": [],
    "evidence_gap_status": {"counts": {}, "open_gaps": []},
    "falsifiable_hypothesis": "hypothesis",
    "fused_verdict": {"verdict": "GO", "rationale": "ok"},
}


def _legacy_patch(package=None):
    package = copy.deepcopy(package or _CANONICAL_SECTIONS)
    return {
        "final_recommendation": {"research_package": copy.deepcopy(package)},
        "final_research_package": copy.deepcopy(package),
        "fused_verdict": "GO",
        "fused_verdict_rationale": "all checks passed",
        "trace_events": [{"node": "legacy"}],
    }


def _state():
    return {
        "last_gate_pass": {"tailor_gate": {"verdict": "pass", "cycle_id": 0}},
        "gate_cycle_id": {"tailor_gate": 0},
        "gate_cycle_start_index": {"tailor_gate": 0},
        "gate_input_fingerprint": {"tailor_gate": "sha256:abc"},
        "gate_reuse_count": {"tailor_gate": 2},
        "gate_evaluation_events": [{"event_type": "gate_evaluated"}],
        "gate_reuse_events": [{"event_type": "gate_pass_reused"}],
    }


def test_gate_execution_is_nested_without_creating_eighth_section(monkeypatch):
    monkeypatch.setattr(wrapper._legacy, "final_recommendation_node", lambda state: _legacy_patch())

    patch = wrapper.final_recommendation_node(_state())
    package = patch["final_research_package"]
    execution = package["gate_results"]["_execution"]

    assert set(package) == set(_CANONICAL_SECTIONS)
    assert len(package) == 7
    assert "gate_execution" not in package
    assert execution["reuse_count"]["tailor_gate"] == 2
    assert patch["final_recommendation"]["gate_execution"] == execution
    assert patch["final_recommendation"]["research_package"] == package
    assert len(patch["trace_events"]) == 2


def test_legacy_top_level_gate_execution_is_migrated(monkeypatch):
    legacy_package = copy.deepcopy(_CANONICAL_SECTIONS)
    legacy_package["gate_execution"] = {"legacy": True}
    monkeypatch.setattr(
        wrapper._legacy,
        "final_recommendation_node",
        lambda state: _legacy_patch(legacy_package),
    )

    package = wrapper.final_recommendation_node(_state())["final_research_package"]

    assert "gate_execution" not in package
    assert package["gate_results"]["_execution"]["reuse_count"]["tailor_gate"] == 2


def test_missing_gate_metadata_degrades_to_empty_collections(monkeypatch):
    monkeypatch.setattr(wrapper._legacy, "final_recommendation_node", lambda state: _legacy_patch())
    patch = wrapper.final_recommendation_node({})
    audit = patch["final_research_package"]["gate_results"]["_execution"]

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

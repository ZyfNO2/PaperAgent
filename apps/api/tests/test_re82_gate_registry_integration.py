"""Registry-level integration for Re8.2 Tailor pass reuse."""
from __future__ import annotations

import copy

from apps.api.app.services.agents.graph.nodes import REGISTRY
from apps.api.app.services.agents.graph.nodes import reflection_gate_reuse as reuse
from apps.api.app.services.agents.graph.nodes import reflection_gates as legacy


_APPEND = {"trace_events", "reasoning_ledger", "gate_evaluation_events", "gate_reuse_events"}


def _apply(state, patch):
    out = copy.deepcopy(state)
    for key, value in patch.items():
        if key in _APPEND:
            out[key] = list(out.get(key) or []) + list(value or [])
        else:
            out[key] = copy.deepcopy(value)
    return out


def test_registry_reuses_tailor_pass_and_router_stays_forward(monkeypatch):
    calls = []

    def fake_evaluator(state):
        round_idx = legacy._get_gate_rounds(state, legacy.GATE_TAILOR)
        calls.append(round_idx)
        result = legacy._normalize_gate_output(
            {"verdict": "pass", "rationale": "verified Tailor contract"},
            gate_name=legacy.GATE_TAILOR,
            round_idx=round_idx,
            generated_by="llm",
        )
        return {
            "reflection_gate_results": legacy._append_gate_result(
                state, legacy.GATE_TAILOR, result
            ),
            "reasoning_ledger": [],
            "trace_events": [],
        }

    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", fake_evaluator)
    state = {
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "tailored_method": {
            "verdict": "GO",
            "assembly_plan": {"description": "stable method"},
            "ablation_matrix": [
                {"experiment_id": "baseline"},
                {"experiment_id": "a"},
                {"experiment_id": "b"},
                {"experiment_id": "a+b"},
            ],
        },
        "evidence_gaps": [],
        "seed_cards": [],
        "reflection_gate_results": {},
        "trace_events": [],
        "reasoning_ledger": [],
    }

    state = _apply(state, REGISTRY["tailor_gate"](state))
    assert legacy.route_after_gate(state, legacy.GATE_TAILOR) == "innovation_extractor"
    assert len(state["reflection_gate_results"][legacy.GATE_TAILOR]) == 1

    reuse_patch = REGISTRY["tailor_gate"](state)
    assert "reflection_gate_results" not in reuse_patch
    state = _apply(state, reuse_patch)

    assert calls == [0]
    assert legacy.route_after_gate(state, legacy.GATE_TAILOR) == "innovation_extractor"
    assert len(state["reflection_gate_results"][legacy.GATE_TAILOR]) == 1
    assert state["gate_reuse_count"][legacy.GATE_TAILOR] == 1
    assert state["gate_reuse_events"][-1]["event_type"] == "gate_pass_reused"

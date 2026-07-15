"""Post-merge code-review regressions for the Re8.2 Gate contract."""
from __future__ import annotations

import copy
from typing import Any

from apps.api.app.services.agents.graph.nodes import reflection_gate_reuse as reuse
from apps.api.app.services.agents.graph.nodes import reflection_gates as legacy
from apps.api.app.services.agents.graph.nodes import tailor_gate_entry as entry

_APPEND = {"trace_events", "reasoning_ledger", "gate_evaluation_events", "gate_reuse_events"}


def _state() -> dict[str, Any]:
    return {
        "entry_mode": "seeded_research",
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "tailored_method": {
            "verdict": "GO",
            "assembly_plan": {"description": "method A"},
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


def _apply(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(state)
    for key, value in patch.items():
        if key in _APPEND:
            out[key] = list(out.get(key) or []) + list(value or [])
        elif key in {
            "last_gate_pass",
            "gate_cycle_id",
            "gate_cycle_start_index",
            "gate_input_fingerprint",
            "gate_reuse_count",
        }:
            merged = dict(out.get(key) or {})
            merged.update(copy.deepcopy(value or {}))
            out[key] = merged
        else:
            out[key] = copy.deepcopy(value)
    return out


def _result(verdict: str, round_idx: int, generated_by: str) -> dict[str, Any]:
    return legacy._normalize_gate_output(
        {"verdict": verdict, "rationale": f"{verdict} r{round_idx}"},
        gate_name=legacy.GATE_TAILOR,
        round_idx=round_idx,
        generated_by=generated_by,
    )


def _evaluator(verdicts: list[str], rounds: list[int]):
    queue = list(verdicts)

    def run(state: dict[str, Any]) -> dict[str, Any]:
        round_idx = legacy._get_gate_rounds(state, legacy.GATE_TAILOR)
        rounds.append(round_idx)
        verdict = queue.pop(0)
        result = _result(verdict, round_idx, "llm")
        return {
            "reflection_gate_results": legacy._append_gate_result(
                state, legacy.GATE_TAILOR, result
            ),
            "reasoning_ledger": [],
            "trace_events": [],
        }

    return run


def test_legacy_skip_only_history_does_not_consume_real_round(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _state()
    state["reflection_gate_results"] = {
        legacy.GATE_TAILOR: [
            _result("pass", 0, "skip"),
            _result("pass", 1, "skip"),
        ]
    }

    patch = reuse.tailor_gate_node(state)
    log = patch["reflection_gate_results"][legacy.GATE_TAILOR]

    assert rounds == [0]
    assert [item["generated_by"] for item in log] == ["skip", "skip", "llm"]
    assert patch["gate_cycle_start_index"][legacy.GATE_TAILOR] == 2
    assert patch["last_gate_pass"][legacy.GATE_TAILOR]["result_log_index"] == 2


def test_mixed_legacy_history_counts_only_real_evaluations(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _state()
    state["reflection_gate_results"] = {
        legacy.GATE_TAILOR: [
            _result("revise", 0, "llm"),
            _result("pass", 1, "skip"),
        ]
    }

    patch = reuse.tailor_gate_node(state)
    log = patch["reflection_gate_results"][legacy.GATE_TAILOR]

    assert rounds == [1]
    assert len(log) == 3
    assert log[-1]["verdict"] == "pass"
    assert log[-1]["round_idx"] == 1


def test_failed_new_cycle_invalidates_old_pass_and_reversion_re_evaluates(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(
        reuse._legacy,
        "tailor_gate_node",
        _evaluator(["pass", "revise", "pass"], rounds),
    )
    state = _state()

    state = _apply(state, reuse.tailor_gate_node(state))
    state["tailored_method"]["assembly_plan"]["description"] = "method B"
    state = _apply(state, reuse.tailor_gate_node(state))
    assert state["last_gate_pass"][legacy.GATE_TAILOR] == {}

    state["tailored_method"]["assembly_plan"]["description"] = "method A"
    patch = reuse.tailor_gate_node(state)

    assert rounds == [0, 0, 0]
    assert "gate_reuse_events" not in patch
    assert patch["gate_cycle_id"][legacy.GATE_TAILOR] == 2
    assert patch["reflection_gate_results"][legacy.GATE_TAILOR][-1]["verdict"] == "pass"


def test_cache_requires_matching_active_cycle_metadata(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _state()
    fingerprint = reuse.tailor_gate_input_fingerprint(state)
    state["reflection_gate_results"] = {
        legacy.GATE_TAILOR: [_result("pass", 0, "llm")]
    }
    state["last_gate_pass"] = {
        legacy.GATE_TAILOR: {
            "verdict": "pass",
            "generated_by": "llm",
            "cycle_id": 0,
            "evaluation_round_idx": 0,
            "input_fingerprint": fingerprint,
            "result_log_index": 0,
        }
    }
    state["gate_input_fingerprint"] = {legacy.GATE_TAILOR: "sha256:other"}
    state["gate_cycle_id"] = {legacy.GATE_TAILOR: 0}
    state["gate_cycle_start_index"] = {legacy.GATE_TAILOR: 0}

    patch = reuse.tailor_gate_node(state)

    assert rounds == [0]
    assert "gate_reuse_events" not in patch
    assert patch["gate_cycle_id"][legacy.GATE_TAILOR] == 1


def test_trailing_skip_log_does_not_hide_latest_evaluated_pass(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _apply(_state(), reuse.tailor_gate_node(_state()))
    state["reflection_gate_results"][legacy.GATE_TAILOR].append(
        _result("pass", 1, "skip")
    )

    def should_not_run(_state):
        raise AssertionError("real evaluator must not run for a valid active pass")

    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", should_not_run)
    patch = reuse.tailor_gate_node(state)

    assert patch["gate_reuse_count"][legacy.GATE_TAILOR] == 1
    assert patch["gate_reuse_events"][0]["source_result_log_index"] == 0
    assert "reflection_gate_results" not in patch


def test_entry_persists_skip_cache_invalidation_when_real_gate_does_not_pass(monkeypatch):
    monkeypatch.setattr(
        entry._reuse,
        "tailor_gate_node",
        lambda state: {
            "reflection_gate_results": {
                legacy.GATE_TAILOR: [_result("revise", 0, "llm")]
            }
        },
    )
    state = _state()
    state["last_gate_pass"] = {
        legacy.GATE_TAILOR: {
            "verdict": "pass",
            "generated_by": "skip",
            "input_fingerprint": "sha256:obsolete",
        }
    }

    patch = entry.tailor_gate_node(state)

    assert patch["last_gate_pass"][legacy.GATE_TAILOR] == {}

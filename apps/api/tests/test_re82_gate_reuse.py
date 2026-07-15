"""Re8.2 WP1: Tailor Gate evaluation/reuse/cycle contract tests."""
from __future__ import annotations

import copy
from typing import Any

import pytest

from apps.api.app.services.agents.graph.nodes import reflection_gate_reuse as reuse
from apps.api.app.services.agents.graph.nodes import reflection_gates as legacy
from apps.api.app.services.agents.graph.re80_schema import REFLECTION_GATE_MAX_ROUNDS


_APPEND = {"trace_events", "reasoning_ledger", "gate_evaluation_events", "gate_reuse_events"}


def _state() -> dict[str, Any]:
    return {
        "entry_mode": "seeded_research",
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "tailored_method": {
            "verdict": "GO",
            "candidate_modules": [
                {"module_id": "m2", "name": "B"},
                {"module_id": "m1", "name": "A"},
            ],
            "assembly_plan": {
                "description": "A plus B",
                "modules": [{"name": "B"}, {"name": "A"}],
                "connections": [
                    {"from": "B", "to": "head"},
                    {"from": "A", "to": "B"},
                ],
            },
            "ablation_matrix": [
                {"experiment_id": "ab"},
                {"experiment_id": "base"},
                {"experiment_id": "b"},
                {"experiment_id": "a"},
            ],
        },
        "evidence_gaps": [
            {
                "gap_id": "g2",
                "status": "partially_satisfied",
                "evidence_delta": {"n_papers": 1},
                "evidence_ids": ["p2", "p1"],
            },
            {
                "gap_id": "g1",
                "status": "satisfied",
                "evidence_delta": {"n_papers": 2},
                "evidence_ids": ["p3"],
            },
        ],
        "seed_cards": [
            {
                "seed_id": "s2",
                "resolved_title": "Paper B",
                "authors": ["B"],
                "year": 2022,
                "doi": "10.2/b",
                "existence_status": "verified",
                "role": "module",
                "raw_input": {"pdf_bytes": b"old", "local_pdf_path": "/tmp/b.pdf"},
            },
            {
                "seed_id": "s1",
                "resolved_title": "Paper A",
                "authors": ["A"],
                "year": 2020,
                "arxiv_id": "2001.1",
                "existence_status": "verified",
                "role": "baseline",
            },
        ],
        "reflection_gate_results": {},
        "trace_events": [],
        "reasoning_ledger": [],
    }


def _apply(state: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(state)
    for key, value in patch.items():
        if key in _APPEND:
            out[key] = list(out.get(key) or []) + list(value or [])
        else:
            out[key] = copy.deepcopy(value)
    return out


def _evaluator(verdicts: list[str], rounds: list[int]):
    queue = list(verdicts)

    def run(state: dict[str, Any]) -> dict[str, Any]:
        round_idx = legacy._get_gate_rounds(state, legacy.GATE_TAILOR)
        rounds.append(round_idx)
        verdict = queue.pop(0) if queue else "pass"
        result = legacy._normalize_gate_output(
            {"verdict": verdict, "rationale": f"{verdict} r{round_idx}"},
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

    return run


def _cap_evaluator(rounds: list[int]):
    def run(state: dict[str, Any]) -> dict[str, Any]:
        round_idx = legacy._get_gate_rounds(state, legacy.GATE_TAILOR)
        rounds.append(round_idx)
        verdict = "unresolved" if round_idx >= REFLECTION_GATE_MAX_ROUNDS else "revise"
        result = legacy._normalize_gate_output(
            {"verdict": verdict, "rationale": f"{verdict} r{round_idx}"},
            gate_name=legacy.GATE_TAILOR,
            round_idx=round_idx,
            generated_by="rule" if verdict == "unresolved" else "llm",
        )
        return {
            "reflection_gate_results": legacy._append_gate_result(
                state, legacy.GATE_TAILOR, result
            ),
            "reasoning_ledger": [],
            "trace_events": [],
        }

    return run


def test_fingerprint_excludes_raw_input_bytes_and_local_paths():
    state = _state()
    before = reuse.tailor_gate_input_fingerprint(state)
    state["seed_cards"][0]["raw_input"] = {
        "pdf_bytes": b"new",
        "local_pdf_path": "D:/another/b.pdf",
    }
    assert before == reuse.tailor_gate_input_fingerprint(state)


def test_fingerprint_is_order_insensitive_for_business_collections():
    state = _state()
    before = reuse.tailor_gate_input_fingerprint(state)
    state["seed_cards"].reverse()
    state["evidence_gaps"].reverse()
    state["tailored_method"]["candidate_modules"].reverse()
    state["tailored_method"]["assembly_plan"]["modules"].reverse()
    state["tailored_method"]["assembly_plan"]["connections"].reverse()
    state["tailored_method"]["ablation_matrix"].reverse()
    for gap in state["evidence_gaps"]:
        gap["evidence_ids"].reverse()
    assert before == reuse.tailor_gate_input_fingerprint(state)


@pytest.mark.parametrize(
    "change",
    [
        lambda s: s["tailored_method"]["assembly_plan"].update({"description": "changed"}),
        lambda s: s["evidence_gaps"][0].update({"status": "satisfied"}),
        lambda s: s["evidence_gaps"][0]["evidence_delta"].update({"n_papers": 4}),
        lambda s: s["seed_cards"][0].update({"role": "baseline"}),
    ],
)
def test_fingerprint_changes_for_semantic_inputs(change):
    state = _state()
    before = reuse.tailor_gate_input_fingerprint(state)
    change(state)
    assert before != reuse.tailor_gate_input_fingerprint(state)


def test_pass_is_recorded_with_cycle_and_round(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    patch = reuse.tailor_gate_node(_state())
    saved = patch["last_gate_pass"][legacy.GATE_TAILOR]
    assert rounds == [0]
    assert saved["cycle_id"] == 0
    assert saved["evaluation_round_idx"] == 0
    assert saved["input_fingerprint"].startswith("sha256:")


def test_same_input_reuses_without_round_append_or_delegate(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _state()
    state = _apply(state, reuse.tailor_gate_node(state))
    size = len(state["reflection_gate_results"][legacy.GATE_TAILOR])
    patch = reuse.tailor_gate_node(state)
    assert rounds == [0]
    assert "reflection_gate_results" not in patch
    assert len(state["reflection_gate_results"][legacy.GATE_TAILOR]) == size
    assert patch["gate_reuse_count"][legacy.GATE_TAILOR] == 1
    assert patch["gate_reuse_events"][0]["source_cycle_id"] == 0
    assert patch["gate_reuse_events"][0]["source_round_idx"] == 0


def test_reuse_count_grows_but_evaluation_log_does_not(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], rounds))
    state = _state()
    state = _apply(state, reuse.tailor_gate_node(state))
    state = _apply(state, reuse.tailor_gate_node(state))
    state = _apply(state, reuse.tailor_gate_node(state))
    assert rounds == [0]
    assert len(state["reflection_gate_results"][legacy.GATE_TAILOR]) == 1
    assert state["gate_reuse_count"][legacy.GATE_TAILOR] == 2


def test_same_cycle_advances_only_current_cycle_rounds(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["revise", "pass"], rounds))
    state = _state()
    state = _apply(state, reuse.tailor_gate_node(state))
    state = _apply(state, reuse.tailor_gate_node(state))
    assert rounds == [0, 1]
    assert [x["round_idx"] for x in state["reflection_gate_results"][legacy.GATE_TAILOR]] == [0, 1]


def test_changed_input_starts_new_cycle_at_round_zero(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass", "pass"], rounds))
    state = _state()
    state = _apply(state, reuse.tailor_gate_node(state))
    state["tailored_method"]["assembly_plan"]["description"] = "new method"
    state = _apply(state, reuse.tailor_gate_node(state))
    log = state["reflection_gate_results"][legacy.GATE_TAILOR]
    assert rounds == [0, 0]
    assert [x["round_idx"] for x in log] == [0, 0]
    assert state["gate_cycle_id"][legacy.GATE_TAILOR] == 1
    assert state["gate_cycle_start_index"][legacy.GATE_TAILOR] == 1


def test_new_cycle_keeps_two_evaluation_round_cap(monkeypatch):
    first_rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _evaluator(["pass"], first_rounds))
    state = _apply(_state(), reuse.tailor_gate_node(_state()))
    state["evidence_gaps"][0]["status"] = "open"
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _cap_evaluator(rounds))
    for _ in range(3):
        state = _apply(state, reuse.tailor_gate_node(state))
    start = state["gate_cycle_start_index"][legacy.GATE_TAILOR]
    current = state["reflection_gate_results"][legacy.GATE_TAILOR][start:]
    assert rounds == [0, 1, 2]
    assert [x["verdict"] for x in current] == ["revise", "revise", "unresolved"]
    assert REFLECTION_GATE_MAX_ROUNDS == 2


def test_legacy_log_without_cycle_metadata_does_not_reset_cap(monkeypatch):
    rounds: list[int] = []
    monkeypatch.setattr(reuse._legacy, "tailor_gate_node", _cap_evaluator(rounds))
    state = _state()
    state["reflection_gate_results"] = {legacy.GATE_TAILOR: []}
    for idx in (0, 1):
        state["reflection_gate_results"][legacy.GATE_TAILOR].append(
            legacy._normalize_gate_output(
                {"verdict": "revise", "rationale": "legacy"},
                gate_name=legacy.GATE_TAILOR,
                round_idx=idx,
            )
        )
    patch = reuse.tailor_gate_node(state)
    assert rounds == [2]
    assert patch["reflection_gate_results"][legacy.GATE_TAILOR][-1]["verdict"] == "unresolved"
    assert patch["gate_cycle_start_index"][legacy.GATE_TAILOR] == 0

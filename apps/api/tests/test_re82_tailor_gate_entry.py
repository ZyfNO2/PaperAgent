"""Re8.2 WP1 tests for the Tailor Gate activation-safe entrypoint."""
from __future__ import annotations

from apps.api.app.services.agents.graph.nodes import tailor_gate_entry as entry
from apps.api.app.services.agents.graph.nodes import reflection_gates as legacy


def test_chain_only_uses_legacy_skip_and_never_calls_reuse(monkeypatch):
    calls = {"legacy": 0, "reuse": 0}

    def legacy_node(state):
        calls["legacy"] += 1
        return {"reflection_gate_results": {legacy.GATE_TAILOR: [{"verdict": "pass", "generated_by": "skip"}]}}

    def reuse_node(state):
        calls["reuse"] += 1
        return {"unexpected": True}

    monkeypatch.setattr(entry._legacy, "tailor_gate_node", legacy_node)
    monkeypatch.setattr(entry._reuse, "tailor_gate_node", reuse_node)

    patch = entry.tailor_gate_node(
        {"run_mode": "full_agent", "reasoning_policy": "chain_only"}
    )

    assert calls == {"legacy": 1, "reuse": 0}
    assert "last_gate_pass" not in patch


def test_offline_mode_uses_legacy_skip(monkeypatch):
    calls = {"legacy": 0, "reuse": 0}

    monkeypatch.setattr(
        entry._legacy,
        "tailor_gate_node",
        lambda state: calls.__setitem__("legacy", calls["legacy"] + 1) or {},
    )
    monkeypatch.setattr(
        entry._reuse,
        "tailor_gate_node",
        lambda state: calls.__setitem__("reuse", calls["reuse"] + 1) or {},
    )

    entry.tailor_gate_node(
        {"run_mode": "offline_replay", "reasoning_policy": "react_reflection"}
    )
    assert calls == {"legacy": 1, "reuse": 0}


def test_react_mode_calls_reuse_path(monkeypatch):
    calls = {"legacy": 0, "reuse": 0}

    monkeypatch.setattr(
        entry._legacy,
        "tailor_gate_node",
        lambda state: calls.__setitem__("legacy", calls["legacy"] + 1) or {},
    )

    def reuse_node(state):
        calls["reuse"] += 1
        assert state["run_mode"] == "full_agent"
        assert state["reasoning_policy"] == "react_reflection"
        return {"ok": True}

    monkeypatch.setattr(entry._reuse, "tailor_gate_node", reuse_node)
    patch = entry.tailor_gate_node(
        {"run_mode": "full_agent", "reasoning_policy": "react_reflection"}
    )

    assert calls == {"legacy": 0, "reuse": 1}
    assert patch == {"ok": True}


def test_cached_skip_pass_is_removed_and_invalidation_is_persisted(monkeypatch):
    captured = {}

    def reuse_node(state):
        captured.update(state)
        return {"evaluated": True}

    monkeypatch.setattr(entry._reuse, "tailor_gate_node", reuse_node)
    source = {
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "last_gate_pass": {
            legacy.GATE_TAILOR: {
                "verdict": "pass",
                "generated_by": "skip",
                "input_fingerprint": "sha256:old",
            },
            legacy.GATE_SEED_AUDIT: {"verdict": "pass", "generated_by": "llm"},
        },
    }

    patch = entry.tailor_gate_node(source)

    assert patch["evaluated"] is True
    assert legacy.GATE_TAILOR not in captured["last_gate_pass"]
    assert legacy.GATE_SEED_AUDIT in captured["last_gate_pass"]
    assert patch["last_gate_pass"][legacy.GATE_TAILOR] == {}
    assert patch["last_gate_pass"][legacy.GATE_SEED_AUDIT]["verdict"] == "pass"
    assert legacy.GATE_TAILOR in source["last_gate_pass"]


def test_real_cached_pass_is_preserved_for_reuse(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        entry._reuse,
        "tailor_gate_node",
        lambda state: captured.update(state) or {"reused": True},
    )
    previous = {
        "verdict": "pass",
        "generated_by": "llm",
        "input_fingerprint": "sha256:real",
    }
    source = {
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "last_gate_pass": {legacy.GATE_TAILOR: previous},
    }

    assert entry.tailor_gate_node(source) == {"reused": True}
    assert captured["last_gate_pass"][legacy.GATE_TAILOR] == previous

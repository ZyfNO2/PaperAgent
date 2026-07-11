"""Unit tests for final_recommendation verdict computation."""
from __future__ import annotations

from apps.api.app.services.agents.graph.nodes.content import (
    _compute_final_verdict,
    _compute_stop_reason,
    final_recommendation_node,
)


def test_compute_verdict_go():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    }) == "GO"


def test_compute_verdict_stop_low_bar():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    }) == "STOP"


def test_compute_verdict_stop_claim_reject():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
    }) == "STOP"


def test_compute_verdict_stop_human_gate_blocked():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "blocked"},
        "claim_judge_verdict": "ACCEPT",
    }) == "STOP"


def test_compute_verdict_risky_revise():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REVISE",
    }) == "RISKY"


def test_compute_verdict_risky_blocked_items():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
        "blocked_items": ["nd-001: missing evidence"],
    }) == "RISKY"


def test_stop_reason_collects_reasons():
    reasons = _compute_stop_reason({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "blocked"},
        "claim_judge_verdict": "REJECT",
        "blocked_items": ["x"],
    })
    assert len(reasons) == 3
    assert any("low-bar" in r for r in reasons)


def test_final_recommendation_includes_verdict():
    result = final_recommendation_node({
        "topic": "test",
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    })
    rec = result["final_recommendation"]
    assert rec["verdict"] == "GO"
    assert rec["stop_reason"] == []
    assert rec["claim_judge_verdict"] == "ACCEPT"


def test_final_recommendation_has_feedback_bar():
    result = final_recommendation_node({
        "case_id": "case-42",
        "topic": "test",
        "low_bar_review": {"status": "passed"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    })
    rec = result["final_recommendation"]
    assert "artifact_id" in rec
    assert rec["artifact_id"].startswith("rec-")
    fb = rec.get("feedback_bar")
    assert fb is not None
    assert fb["artifact_type"] == "final_recommendation"
    assert fb["artifact_id"] == rec["artifact_id"]
    assert len(fb["idempotency_key"]) == 24
    assert "options" in fb

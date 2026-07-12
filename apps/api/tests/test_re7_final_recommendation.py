"""Unit tests for final_recommendation verdict computation."""
from __future__ import annotations

from apps.api.app.services.agents.graph.nodes.content import (
    _compute_final_verdict,
    _compute_stop_reason,
    final_recommendation_node,
)


def test_compute_verdict_go():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    }) == "GO"


def test_compute_verdict_stop_low_bar():
    """Re7.7: low_bar blocked + ACCEPT → CONDITIONAL (not STOP; can proceed with caveats)."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
    }) == "CONDITIONAL"


def test_compute_verdict_stop_claim_reject():
    """Re7.7: REJECT alone → RISKY (not STOP; claim judge may be overly strict)."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
    }) == "RISKY"


def test_compute_verdict_stop_low_bar_and_reject():
    """Re7.7 round-5: low_bar blocked + REJECT in LOW-risk domain → RISKY (not STOP).

    Only medium/high-risk domains escalate REJECT+blocked to STOP.
    """
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
        "user_constraints": {"domain": "工业视觉"},
        "topic": "钢材缺陷检测",
    }) == "RISKY"


def test_compute_verdict_stop_medium_risk_reject_blocked():
    """Re7.7 round-6: medium-risk domain + REJECT + low_bar blocked → RISKY (not STOP).

    Round-5 incorrectly escalated to STOP; XD-04 (medical AI) expects RISKY.
    Only high-risk domains escalate REJECT to STOP; medium-risk behaves like low-risk.
    """
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
        "user_constraints": {"domain": "医学AI"},
        "topic": "医学影像分割",
    }) == "RISKY"


def test_compute_verdict_stop_high_risk_reject_pass():
    """Re7.7 round-5: high-risk domain + REJECT + low_bar pass → STOP."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
        "user_constraints": {"domain": "高风险对话"},
        "topic": "心理咨询辅助问答",
    }) == "STOP"


def test_compute_verdict_stop_high_risk_revise_blocked():
    """Re7.7 round-5: high-risk domain + REVISE + low_bar blocked → STOP."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REVISE",
        "user_constraints": {"domain": "生物信息"},
        "topic": "罕见病药物反应预测",
    }) == "STOP"


def test_compute_verdict_medium_risk_reject_pass():
    """Re7.7 round-5: medium-risk + REJECT + low_bar pass → RISKY (not STOP).

    This is XD-04's core path: medical AI domain, claim judge rejects,
    but low_bar passes. Should stay RISKY, not escalate to STOP.
    """
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REJECT",
        "user_constraints": {"domain": "医学AI"},
        "topic": "医学影像分割模型在跨医院数据上的可信评估",
    }) == "RISKY"


def test_compute_verdict_conditional_high_risk_accept():
    """Re7.7 round-6: high-risk domain + ACCEPT + low_bar pass → CONDITIONAL (not GO).

    High-risk domains (rare-disease, mental health, malicious use) never get a
    clean GO even if claim_judge ACCEPTs — XD-09 must not be GO.
    """
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
        "user_constraints": {"domain": "生物信息"},
        "topic": "利用公开转录组数据预测罕见病药物反应",
    }) == "CONDITIONAL"


def test_compute_verdict_risky_low_bar_blocked_revise():
    """Re7.7: low_bar blocked + REVISE → RISKY (not STOP; evidence partial but direction ok)."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "blocked"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REVISE",
    }) == "RISKY"


def test_compute_verdict_stop_human_gate_blocked():
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "blocked"},
        "claim_judge_verdict": "ACCEPT",
    }) == "STOP"


def test_compute_verdict_risky_revise():
    """Re7.7 round-5: REVISE + low_bar pass → CONDITIONAL (was RISKY).

    Incremental work with partial evidence deserves a conditional green light.
    """
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REVISE",
    }) == "CONDITIONAL"


def test_compute_verdict_conditional_accept_with_blocked_items():
    """Re7.7: ACCEPT + blocked_items → CONDITIONAL (not RISKY)."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "ACCEPT",
        "blocked_items": ["nd-001: missing evidence"],
    }) == "CONDITIONAL"


def test_compute_verdict_risky_unavailable():
    """Re7.7: claim judge UNAVAILABLE → RISKY (not STOP)."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "UNAVAILABLE",
    }) == "RISKY"


def test_compute_verdict_pivot_revise_with_fundamental_flaw():
    """Re7.7: REVISE + devils_advocate fundamental_flaw → PIVOT."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "REVISE",
        "devils_advocate": {"fundamental_flaw": True},
    }) == "PIVOT"


def test_compute_verdict_risky_blocked_items_no_accept():
    """blocked_items with non-ACCEPT verdict (and not REJECT/UNAVAILABLE/REVISE) → RISKY."""
    assert _compute_final_verdict({
        "low_bar_review": {"status": "pass"},
        "human_gate": {"status": "pass_through"},
        "claim_judge_verdict": "",
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
        "low_bar_review": {"status": "pass"},
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
        "low_bar_review": {"status": "pass"},
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

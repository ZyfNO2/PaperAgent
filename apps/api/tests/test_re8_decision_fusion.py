"""Tests for Re8.0 Task 6 — Decision Fusion (P1-2).

Covers ``_compute_fused_verdict`` in
``apps/api.app.services.agents.graph.nodes.content``. The function is PURE
(no I/O, no side effects): it takes a state dict and returns
``(fused_verdict, rationale)``.

Fusion rules (spec §"Decision Fusion", evaluated in order, first match wins):
  1. seed_audit_gate unresolved   → BLOCKED
  2. tailor_gate unresolved       → BLOCKED
  3. final_review_gate unresolved → BLOCKED
  4. novelty=reject + tailor=GO   → RISKY
  5. any gate=revise              → CONDITIONAL
  6. open critical gap            → CONDITIONAL
  7. all gates pass + novelty accepted + no open critical gaps → GO
  8. default                      → CONDITIONAL

Critical gap types (block GO when status="open"): current_baseline,
competing_method, dataset, mechanism. repo / environment / counter_evidence /
existence gaps do NOT block GO on their own.

Spec scenario: "3 gates revise but low_bar pass → fused_verdict=CONDITIONAL
(not GO)" — covered by TestAnyGateReviseConditional.
"""
from __future__ import annotations

from typing import Any

import pytest

from apps.api.app.services.agents.graph.nodes.content import (
    _compute_fused_verdict,
    _has_open_critical_gap,
)
from apps.api.app.services.agents.graph.nodes.reflection_gates import (
    GATE_FINAL_REVIEW,
    GATE_SEED_AUDIT,
    GATE_TAILOR,
)


# ── State builders ─────────────────────────────────────────────────────────


def _gate_entry(verdict: str, **extra: Any) -> dict[str, Any]:
    """Build a single reflection_gate_results entry."""
    entry = {"verdict": verdict, "round_idx": 0, "generated_by": "llm"}
    entry.update(extra)
    return entry


def _go_state() -> dict[str, Any]:
    """A state where every signal is green → fused_verdict should be GO.

    Used as the base for negative tests; each negative test mutates one
    signal and asserts the corresponding rule fires.
    """
    return {
        "reflection_gate_results": {
            GATE_SEED_AUDIT: [_gate_entry("pass")],
            GATE_TAILOR: [_gate_entry("pass")],
            GATE_FINAL_REVIEW: [_gate_entry("pass")],
        },
        "novelty_review_verdict": "accepted",
        "tailored_method": {"verdict": "GO", "core_method": "method-X"},
        "evidence_gaps": [
            {"gap_id": "G1", "gap_type": "current_baseline", "status": "satisfied"},
            {"gap_id": "G2", "gap_type": "repo", "status": "open"},
        ],
        # Legacy fields — must NOT influence the fused verdict.
        "low_bar_status": "pass",
        "human_gate": {"status": "pass_through"},
    }


# ── Rule 7: GO ─────────────────────────────────────────────────────────────


class TestFusedVerdictGO:
    def test_all_pass_plus_accepted_plus_no_open_critical_gaps_is_go(self):
        state = _go_state()
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "GO"
        assert rationale == "all checks passed"

    def test_lite_chain_skip_passes_produce_go(self):
        """Lite Chain / Offline Replay short-circuit gates to pass with
        generated_by='skip'. With novelty accepted + no open critical gaps,
        the fused verdict must still be GO."""
        state = _go_state()
        state["run_mode"] = "lite_chain"
        state["reflection_gate_results"] = {
            GATE_SEED_AUDIT: [_gate_entry("pass", generated_by="skip")],
            GATE_TAILOR: [_gate_entry("pass", generated_by="skip")],
            GATE_FINAL_REVIEW: [_gate_entry("pass", generated_by="skip")],
        }
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"

    def test_missing_gate_treated_as_pass(self):
        """A gate with no entries (wasn't run) is treated as 'pass' and
        does not block GO (Re8.0 P1-2 constraint)."""
        state = _go_state()
        # Drop two of the three gates entirely.
        state["reflection_gate_results"] = {
            GATE_SEED_AUDIT: [_gate_entry("pass")],
        }
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"

    def test_noncritical_open_gap_does_not_block_go(self):
        """Open gaps of non-critical types (repo / environment /
        counter_evidence / existence) must NOT block a clean GO."""
        state = _go_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "gap_type": "repo", "status": "open"},
            {"gap_id": "G2", "gap_type": "environment", "status": "open"},
            {"gap_id": "G3", "gap_type": "counter_evidence", "status": "open"},
            {"gap_id": "G4", "gap_type": "existence", "status": "open"},
        ]
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"


# ── Rules 1-3: BLOCKED ─────────────────────────────────────────────────────


class TestFusedVerdictBlocked:
    def test_seed_audit_unresolved_is_blocked(self):
        state = _go_state()
        state["reflection_gate_results"][GATE_SEED_AUDIT] = [_gate_entry("unresolved")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "BLOCKED"
        assert rationale == "seed audit unresolved"

    def test_tailor_gate_unresolved_is_blocked(self):
        state = _go_state()
        state["reflection_gate_results"][GATE_TAILOR] = [_gate_entry("unresolved")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "BLOCKED"
        assert rationale == "tailor unresolved"

    def test_final_review_gate_unresolved_is_blocked(self):
        state = _go_state()
        state["reflection_gate_results"][GATE_FINAL_REVIEW] = [_gate_entry("unresolved")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "BLOCKED"
        assert rationale == "final review unresolved"

    def test_rule1_beats_rule2_seed_audit_wins(self):
        """First-match-wins: if both seed_audit and tailor are unresolved,
        rule 1 fires first → 'seed audit unresolved'."""
        state = _go_state()
        state["reflection_gate_results"][GATE_SEED_AUDIT] = [_gate_entry("unresolved")]
        state["reflection_gate_results"][GATE_TAILOR] = [_gate_entry("unresolved")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "BLOCKED"
        assert rationale == "seed audit unresolved"


# ── Rule 4: RISKY ──────────────────────────────────────────────────────────


class TestFusedVerdictRisky:
    def test_novelty_reject_plus_tailor_go_is_risky(self):
        state = _go_state()
        state["novelty_review_verdict"] = "reject"
        state["tailored_method"] = {"verdict": "GO"}
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "RISKY"
        assert rationale == "novelty rejected but engineering viable"

    def test_novelty_reject_without_tailor_go_is_not_risky(self):
        """Rule 4 requires BOTH novelty=reject AND tailor verdict=GO.
        novelty=reject + tailor=CONDITIONAL falls through to later rules."""
        state = _go_state()
        state["novelty_review_verdict"] = "reject"
        state["tailored_method"] = {"verdict": "CONDITIONAL"}
        # gates still pass, no open critical gaps, but novelty != accepted
        # → rule 7 fails → default CONDITIONAL.
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"

    def test_novelty_weak_reject_is_not_risky(self):
        """Only 'reject' triggers rule 4; 'weak_reject' does not."""
        state = _go_state()
        state["novelty_review_verdict"] = "weak_reject"
        state["tailored_method"] = {"verdict": "GO"}
        verdict, _ = _compute_fused_verdict(state)
        # weak_reject ≠ accepted → rule 7 fails → default CONDITIONAL.
        assert verdict == "CONDITIONAL"

    def test_rule4_beats_rule5_risky_before_conditional(self):
        """First-match-wins: novelty=reject + tailor=GO + a gate=revise →
        rule 4 (RISKY) fires before rule 5 (CONDITIONAL)."""
        state = _go_state()
        state["novelty_review_verdict"] = "reject"
        state["tailored_method"] = {"verdict": "GO"}
        state["reflection_gate_results"][GATE_TAILOR] = [_gate_entry("revise")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "RISKY"
        assert rationale == "novelty rejected but engineering viable"


# ── Rule 5: CONDITIONAL (gate revise) ──────────────────────────────────────


class TestFusedVerdictConditionalRevise:
    @pytest.mark.parametrize(
        "gate_name",
        [GATE_SEED_AUDIT, GATE_TAILOR, GATE_FINAL_REVIEW],
        ids=["seed_audit", "tailor", "final_review"],
    )
    def test_any_gate_revise_is_conditional_not_go(self, gate_name: str):
        """Spec scenario: 3 gates revise but low_bar pass → CONDITIONAL.
        The fused verdict must NOT be GO even when the legacy low_bar
        status is 'pass' (low_bar is not an input to the fusion)."""
        state = _go_state()
        state["low_bar_status"] = "pass"  # legacy field, must not force GO
        state["reflection_gate_results"][gate_name] = [_gate_entry("revise")]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"
        assert verdict != "GO"
        assert rationale == "gates requested revision"

    def test_all_three_gates_revise_is_conditional(self):
        state = _go_state()
        state["reflection_gate_results"] = {
            GATE_SEED_AUDIT: [_gate_entry("revise")],
            GATE_TAILOR: [_gate_entry("revise")],
            GATE_FINAL_REVIEW: [_gate_entry("revise")],
        }
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"

    def test_rule5_beats_rule6_revise_before_gap(self):
        """First-match-wins: a gate=revise AND an open critical gap →
        rule 5 fires first → 'gates requested revision'."""
        state = _go_state()
        state["reflection_gate_results"][GATE_SEED_AUDIT] = [_gate_entry("revise")]
        state["evidence_gaps"] = [
            {"gap_id": "G1", "gap_type": "dataset", "status": "open"},
        ]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"
        assert rationale == "gates requested revision"


# ── Rule 6: CONDITIONAL (critical gap) ─────────────────────────────────────


class TestFusedVerdictConditionalGap:
    @pytest.mark.parametrize(
        "gap_type",
        ["current_baseline", "competing_method", "dataset", "mechanism"],
    )
    def test_open_critical_gap_blocks_go(self, gap_type: str):
        state = _go_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "gap_type": gap_type, "status": "open"},
        ]
        verdict, rationale = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"
        assert verdict != "GO"
        assert rationale == "critical gaps open"

    def test_satisfied_critical_gap_does_not_block_go(self):
        """A critical-type gap with status='satisfied' (or
        'partially_satisfied' / 'blocked') does NOT block GO — only
        status='open' does."""
        state = _go_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "gap_type": "mechanism", "status": "satisfied"},
            {"gap_id": "G2", "gap_type": "dataset", "status": "partially_satisfied"},
            {"gap_id": "G3", "gap_type": "current_baseline", "status": "blocked"},
        ]
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"

    def test_has_open_critical_gap_helper(self):
        assert _has_open_critical_gap({
            "evidence_gaps": [{"gap_type": "dataset", "status": "open"}]
        }) is True
        assert _has_open_critical_gap({
            "evidence_gaps": [{"gap_type": "repo", "status": "open"}]
        }) is False
        assert _has_open_critical_gap({
            "evidence_gaps": [{"gap_type": "dataset", "status": "satisfied"}]
        }) is False
        assert _has_open_critical_gap({}) is False


# ── Rule 8: default ────────────────────────────────────────────────────────


class TestFusedVerdictDefault:
    def test_empty_state_is_conditional(self):
        """No signals at all → default CONDITIONAL ('insufficient signals
        for GO'). Missing gates are treated as 'pass', but novelty is empty
        so rule 7 fails."""
        verdict, rationale = _compute_fused_verdict({})
        assert verdict == "CONDITIONAL"
        assert rationale == "insufficient signals for GO"

    def test_novelty_missing_is_conditional(self):
        """Gates all pass but novelty verdict missing → rule 7 fails
        (novelty != 'accepted') → default CONDITIONAL."""
        state = _go_state()
        state["novelty_review_verdict"] = ""
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "CONDITIONAL"


# ── Last-entry-wins + purity ───────────────────────────────────────────────


class TestFusedVerdictSemantics:
    def test_last_gate_entry_wins(self):
        """When a gate has multiple entries (multi-round ReAct), the LAST
        entry's verdict is the one that counts."""
        state = _go_state()
        state["reflection_gate_results"][GATE_SEED_AUDIT] = [
            _gate_entry("revise", round_idx=0),
            _gate_entry("revise", round_idx=1),
            _gate_entry("pass", round_idx=2),  # final round passed
        ]
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"

    def test_malformed_verdict_treated_as_pass(self):
        """A gate entry with a non-canonical verdict string is treated as
        'pass' (conservative — never silently hard-stop on noise)."""
        state = _go_state()
        state["reflection_gate_results"][GATE_TAILOR] = [
            {"verdict": "maybe", "round_idx": 0},
        ]
        verdict, _ = _compute_fused_verdict(state)
        assert verdict == "GO"

    def test_function_is_pure_no_state_mutation(self):
        """_compute_fused_verdict must not mutate its input state."""
        import copy
        state = _go_state()
        snapshot = copy.deepcopy(state)
        _compute_fused_verdict(state)
        _compute_fused_verdict(state)
        assert state == snapshot


# ── Integration: final_recommendation_node carries fused_verdict ───────────


class TestFinalRecommendationCarriesFusedVerdict:
    def test_node_emits_fused_verdict_fields(self):
        """final_recommendation_node must add fused_verdict and
        fused_verdict_rationale to the recommendation dict, WITHOUT
        removing any legacy field (low_bar_status / human_gate_status /
        claim_judge_verdict / verdict / stop_reason)."""
        from apps.api.app.services.agents.graph.nodes.content import (
            final_recommendation_node,
        )

        state = _go_state()
        # Minimal legacy fields the node reads.
        state["topic"] = "test topic"
        state["verified_papers"] = []
        state["baseline_candidates"] = []
        state["parallel_candidates"] = []
        state["dataset_candidates"] = []
        state["repo_candidates"] = []
        state["work_packages"] = []
        state["low_bar_review"] = {"status": "pass"}
        state["human_gate"] = {"status": "pass_through"}
        state["claim_judge_verdict"] = "ACCEPT"

        patch = final_recommendation_node(state)
        rec = patch["final_recommendation"]

        # New fused fields present.
        assert rec["fused_verdict"] == "GO"
        assert rec["fused_verdict_rationale"] == "all checks passed"
        # Legacy fields preserved (additive, not replacing).
        for legacy_key in (
            "low_bar_status",
            "human_gate_status",
            "claim_judge_verdict",
            "verdict",
            "stop_reason",
        ):
            assert legacy_key in rec, f"legacy field {legacy_key!r} dropped"

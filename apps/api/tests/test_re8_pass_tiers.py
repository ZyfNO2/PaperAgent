"""Tests for Re8.0 Task 4 — Three-Tier PASS Standard.

Tests the ``_compute_contract_pass`` and ``_compute_quality_pass`` functions
in ``apps/api/scripts/re80_seeded_demo.py``. These functions are pure (no
I/O, no side effects) and take a ``final_state`` dict, returning
``(bool, list[str])``.

The Three-Tier PASS Standard (spec §"Three-Tier PASS Standard"):
  - ``runtime_pass``: pipeline completes without crash, final non-empty
  - ``contract_pass``: seed_cards / tailored_method / 3 gate_results /
    ledger all have expected fields populated
  - ``quality_pass``: ≥1 verified seed, core_method non-empty,
    ≥1 evidence gap closed, final verdict consistent with gate verdicts

Scenario from spec:
  - 6/6 seeds ambiguous + 3 gates revise → runtime_pass=true,
    contract_pass=false (seed_cards missing resolved_title),
    quality_pass=false
"""
from __future__ import annotations

import os
import sys

import pytest

# Ensure project root is on sys.path so the namespace package
# ``apps.api.scripts.re80_seeded_demo`` can be imported.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from apps.api.scripts.re80_seeded_demo import (
    _compute_contract_pass,
    _compute_quality_pass,
)


# ── Test fixtures ───────────────────────────────────────────────────────────


def _well_formed_final_state() -> dict:
    """A final_state that passes all contract and quality checks.

    Used as the base for negative tests — each negative test mutates one
    field and asserts the corresponding check fails.

    Re8.0 post-audit fix: added ``fused_verdict`` (top-level state field,
    P0-A) and ``search_steps`` (for traceable evidence_delta check in
    quality_pass Check 3). Without these the new quality_pass checks
    would fail on the well-formed baseline.
    """
    return {
        "entry_mode": "seeded_research",
        "candidate_seeds": [{"seed_id": "S1"}, {"seed_id": "S2"}],
        "seed_cards": [
            {
                "seed_id": "S1",
                "resolved_title": "YOLOv8 for real-time object detection",
                "existence_status": "verified",
                "role": "classic_anchor",
            },
            {
                "seed_id": "S2",
                "resolved_title": "Surface defect detection on steel strip",
                "existence_status": "ambiguous",
                "role": "reproduction_target",
            },
        ],
        "reflection_gate_results": {
            "seed_audit_gate": [
                {"verdict": "pass", "round_idx": 0, "generated_by": "llm"}
            ],
            "tailor_gate": [
                {"verdict": "pass", "round_idx": 0, "generated_by": "llm"}
            ],
            "final_review_gate": [
                {"verdict": "pass", "round_idx": 0, "generated_by": "llm"}
            ],
        },
        "reasoning_ledger": [
            {"decision_id": "D1", "stage": "seed_audit", "decision": "accept S1"}
        ],
        "tailored_method": {
            "verdict": "GO",
            "core_method": "YOLOv8 with FPN neck adapted for defect detection",
            "contribution_type": "method_transfer",
            "baseline_model": "YOLOv8n",
            "ablation_matrix": [],
        },
        "final_recommendation": {
            "n_papers": 5,
            "low_bar_status": "pass",
            "verdict": "GO",
        },
        "evidence_gaps": [
            {"gap_id": "G1", "status": "satisfied"},
            {"gap_id": "G2", "status": "open"},
        ],
        "novelty_review_verdict": "accepted",
        # Re8.0 post-audit: fused_verdict top-level field (P0-A).
        # Must NOT be BLOCKED for quality_pass to be true.
        "fused_verdict": "GO",
        # Re8.0 post-audit: search_steps with traceable evidence_delta.
        # G1 has a step with gap_id="G1" and n_new_papers=3, so the new
        # Check 3 (traceable evidence_delta) passes for G1.
        "search_steps": [
            {
                "step": 1,
                "gap_id": "G1",
                "evidence_delta": {"n_new_papers": 3, "n_new_repos": 0},
                "tool": "arxiv",
                "n_results": 3,
            },
        ],
    }


def _all_ambiguous_final_state() -> dict:
    """A final_state mimicking the spec's failure scenario.

    6 seeds all ambiguous, 3 gates return revise, 0 gaps closed.
    runtime_pass=true (final_rec exists) but contract_pass and
    quality_pass should both be false.

    Re8.0 post-audit fix: added ``fused_verdict=BLOCKED`` and
    ``search_steps=[]`` to mirror the real failure scenario where
    no evidence was traceable and the pipeline was blocked.
    """
    state = _well_formed_final_state()
    state["candidate_seeds"] = [{"seed_id": f"S{i}"} for i in range(1, 7)]
    state["seed_cards"] = [
        {
            "seed_id": f"S{i}",
            "resolved_title": "",  # no resolved title
            "existence_status": "ambiguous",
            "role": "unknown",
        }
        for i in range(1, 7)
    ]
    state["reflection_gate_results"] = {
        "seed_audit_gate": [{"verdict": "revise", "round_idx": 0}],
        "tailor_gate": [{"verdict": "revise", "round_idx": 0}],
        "final_review_gate": [{"verdict": "revise", "round_idx": 0}],
    }
    state["evidence_gaps"] = [
        {"gap_id": "G1", "status": "open"},
        {"gap_id": "G2", "status": "open"},
    ]
    state["tailored_method"] = {
        "verdict": "CONDITIONAL",
        "core_method": "",  # empty
    }
    # Re8.0 post-audit: blocked + no traceable evidence
    state["fused_verdict"] = "BLOCKED"
    state["search_steps"] = []  # no evidence_delta at all
    return state


# ── _compute_contract_pass tests ────────────────────────────────────────────


class TestComputeContractPass:
    """Tests for the contract_pass tier (field completeness)."""

    def test_well_formed_state_passes(self):
        """A well-formed final_state should pass all contract checks."""
        state = _well_formed_final_state()
        passed, reasons = _compute_contract_pass(state)
        assert passed is True
        assert reasons == []

    def test_empty_seed_cards_seeded_mode_fails(self):
        """Empty seed_cards in seeded_research mode → fails with exact reason."""
        state = _well_formed_final_state()
        state["seed_cards"] = []
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert reasons == ["seed_cards: no seed has resolved_title"]

    def test_seed_cards_without_resolved_title_fails(self):
        """seed_cards present but none has resolved_title → fails."""
        state = _well_formed_final_state()
        state["seed_cards"] = [
            {"seed_id": "S1", "resolved_title": "", "existence_status": "ambiguous"},
            {"seed_id": "S2", "resolved_title": None, "existence_status": "ambiguous"},
        ]
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert "seed_cards: no seed has resolved_title" in reasons

    def test_missing_gate_results_fails(self):
        """Missing reflection_gate_results → all 3 gates reported missing."""
        state = _well_formed_final_state()
        state["reflection_gate_results"] = {}
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("seed_audit_gate" in r for r in reasons)
        assert any("tailor_gate" in r for r in reasons)
        assert any("final_review_gate" in r for r in reasons)

    def test_partial_gate_results_fails(self):
        """Only 1 of 3 gates populated → 2 missing gates reported."""
        state = _well_formed_final_state()
        state["reflection_gate_results"] = {
            "seed_audit_gate": [{"verdict": "pass"}],
            "tailor_gate": [],  # empty list
            # final_review_gate missing entirely
        }
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("tailor_gate" in r for r in reasons)
        assert any("final_review_gate" in r for r in reasons)
        # seed_audit_gate has entries → should NOT be in reasons
        assert not any("seed_audit_gate" in r for r in reasons)

    def test_empty_ledger_fails(self):
        """Empty reasoning_ledger → fails."""
        state = _well_formed_final_state()
        state["reasoning_ledger"] = []
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("reasoning_ledger" in r for r in reasons)

    def test_empty_tailored_method_seeded_mode_fails(self):
        """Empty tailored_method in seeded_research → fails."""
        state = _well_formed_final_state()
        state["tailored_method"] = {}
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("tailored_method" in r for r in reasons)

    def test_tailored_method_not_dict_fails(self):
        """tailored_method is None (not a dict) in seeded_research → fails."""
        state = _well_formed_final_state()
        state["tailored_method"] = None
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("tailored_method" in r for r in reasons)

    def test_final_recommendation_zero_papers_fails(self):
        """final_recommendation with n_papers=0 → fails."""
        state = _well_formed_final_state()
        state["final_recommendation"] = {"n_papers": 0, "low_bar_status": "fail"}
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("final_recommendation" in r for r in reasons)

    def test_final_recommendation_missing_fails(self):
        """final_recommendation entirely missing → fails."""
        state = _well_formed_final_state()
        del state["final_recommendation"]
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        assert any("final_recommendation" in r for r in reasons)

    def test_topic_only_mode_skips_seed_and_tailor_checks(self):
        """In topic_only mode, seed_cards and tailored_method checks skip."""
        state = _well_formed_final_state()
        state["entry_mode"] = "topic_only"
        state["candidate_seeds"] = []
        state["seed_cards"] = []
        state["tailored_method"] = {}
        passed, reasons = _compute_contract_pass(state)
        # Gates, ledger, final_rec still OK → should pass
        assert passed is True
        assert reasons == []

    def test_spec_scenario_all_ambiguous(self):
        """Spec scenario: 6/6 ambiguous seeds, 3 gates revise → contract fails."""
        state = _all_ambiguous_final_state()
        passed, reasons = _compute_contract_pass(state)
        assert passed is False
        # seed_cards check should fail (no resolved_title)
        assert "seed_cards: no seed has resolved_title" in reasons


# ── _compute_quality_pass tests ─────────────────────────────────────────────


class TestComputeQualityPass:
    """Tests for the quality_pass tier (semantic correctness)."""

    def test_all_verified_seeds_closed_gaps_passes(self):
        """All seeds verified + gaps satisfied + low_bar pass → passes."""
        state = _well_formed_final_state()
        for c in state["seed_cards"]:
            c["existence_status"] = "verified"
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "satisfied"},
            {"gap_id": "G2", "status": "satisfied"},
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is True
        assert reasons == []

    def test_all_ambiguous_seeds_fails(self):
        """All seeds ambiguous → fails with 'no verified seed' reason."""
        state = _well_formed_final_state()
        for c in state["seed_cards"]:
            c["existence_status"] = "ambiguous"
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("no verified seed" in r for r in reasons)

    def test_novelty_reject_fails(self):
        """novelty_review_verdict='reject' → fails."""
        state = _well_formed_final_state()
        state["novelty_review_verdict"] = "reject"
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("novelty_review_verdict" in r and "reject" in r for r in reasons)

    def test_novelty_weak_reject_acceptable(self):
        """novelty_review_verdict='weak_reject' should NOT trigger reject check."""
        state = _well_formed_final_state()
        state["novelty_review_verdict"] = "weak_reject"
        passed, reasons = _compute_quality_pass(state)
        # weak_reject is acceptable — should not appear in failure reasons
        assert not any("novelty_review_verdict is 'reject'" in r for r in reasons)
        # And since the rest of the state is well-formed, it should pass
        assert passed is True

    def test_novelty_verdict_absent_acceptable(self):
        """Missing novelty_review_verdict should not cause failure."""
        state = _well_formed_final_state()
        del state["novelty_review_verdict"]
        passed, reasons = _compute_quality_pass(state)
        assert not any("novelty_review_verdict" in r for r in reasons)

    def test_empty_core_method_fails(self):
        """Empty tailored_method.core_method in seeded_research → fails."""
        state = _well_formed_final_state()
        state["tailored_method"]["core_method"] = ""
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("core_method" in r for r in reasons)

    def test_low_bar_not_pass_fails(self):
        """low_bar_status != 'pass' → fails."""
        state = _well_formed_final_state()
        state["final_recommendation"]["low_bar_status"] = "blocked"
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("low_bar_status" in r for r in reasons)

    def test_open_gaps_none_satisfied_fails(self):
        """All gaps open, none satisfied → fails."""
        state = _well_formed_final_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "open"},
            {"gap_id": "G2", "status": "open"},
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("evidence gap" in r.lower() for r in reasons)

    def test_no_gaps_at_all_passes(self):
        """No evidence_gaps at all → gap check skipped → passes (if rest OK)."""
        state = _well_formed_final_state()
        state["evidence_gaps"] = []
        passed, reasons = _compute_quality_pass(state)
        assert "evidence gap" not in " ".join(reasons).lower()

    def test_all_gaps_satisfied_passes(self):
        """All gaps satisfied (no open) → gap check skipped → passes."""
        state = _well_formed_final_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "satisfied"},
            {"gap_id": "G2", "status": "partially_satisfied"},
        ]
        passed, reasons = _compute_quality_pass(state)
        assert "evidence gap" not in " ".join(reasons).lower()

    def test_topic_only_mode_skips_seed_and_tailor_checks(self):
        """In topic_only mode, seed and tailored_method checks are skipped."""
        state = _well_formed_final_state()
        state["entry_mode"] = "topic_only"
        state["seed_cards"] = []
        state["tailored_method"] = {}
        # Still need: gaps handled, low_bar pass, novelty not reject
        state["evidence_gaps"] = [{"gap_id": "G1", "status": "satisfied"}]
        state["final_recommendation"]["low_bar_status"] = "pass"
        state["novelty_review_verdict"] = "accepted"
        passed, reasons = _compute_quality_pass(state)
        assert passed is True
        assert reasons == []

    def test_spec_scenario_all_ambiguous(self):
        """Spec scenario: 6/6 ambiguous + empty core_method + open gaps."""
        state = _all_ambiguous_final_state()
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        # Multiple quality issues
        assert any("no verified seed" in r for r in reasons)
        assert any("core_method" in r for r in reasons)
        assert any("evidence gap" in r.lower() for r in reasons)

    # ── Re8.0 post-audit: new checks for fused_verdict / gate unresolved /
    #    traceable evidence_delta ────────────────────────────────────────

    def test_fused_verdict_blocked_fails(self):
        """fused_verdict=BLOCKED → quality_pass=false (post-audit fix).

        Previously yolo_steel/xlm_r reported quality_pass=true with
        fused_verdict=BLOCKED — a self-contradictory result. The new
        Check 4 forbids this.
        """
        state = _well_formed_final_state()
        state["fused_verdict"] = "BLOCKED"
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("fused_verdict is BLOCKED" in r for r in reasons)

    def test_fused_verdict_absent_passes(self):
        """Missing fused_verdict should not cause failure (backward compat)."""
        state = _well_formed_final_state()
        del state["fused_verdict"]
        passed, reasons = _compute_quality_pass(state)
        # No BLOCKED check fires on empty/missing fused_verdict
        assert not any("fused_verdict" in r for r in reasons)

    def test_seed_audit_gate_unresolved_fails(self):
        """seed_audit_gate unresolved → quality_pass=false (post-audit fix)."""
        state = _well_formed_final_state()
        state["reflection_gate_results"]["seed_audit_gate"] = [
            {"verdict": "unresolved", "round_idx": 2}
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("seed_audit_gate" in r and "unresolved" in r for r in reasons)

    def test_tailor_gate_unresolved_fails(self):
        """tailor_gate unresolved → quality_pass=false (post-audit fix)."""
        state = _well_formed_final_state()
        state["reflection_gate_results"]["tailor_gate"] = [
            {"verdict": "unresolved", "round_idx": 2}
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("tailor_gate" in r and "unresolved" in r for r in reasons)

    def test_final_review_gate_unresolved_fails(self):
        """final_review_gate unresolved → quality_pass=false (post-audit fix)."""
        state = _well_formed_final_state()
        state["reflection_gate_results"]["final_review_gate"] = [
            {"verdict": "unresolved", "round_idx": 2}
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("final_review_gate" in r and "unresolved" in r for r in reasons)

    def test_gap_without_traceable_evidence_delta_fails(self):
        """Gap marked satisfied but no matching gap_id in search_steps → fails.

        This is the core anti-false-positive check: the P1-7b fallback
        marked all open gaps as partially_satisfied when any papers/repos
        were found, but search_steps had gap_id=null / evidence_delta=null.
        The new Check 3 requires the gap_id to appear in at least one
        search_step with non-zero evidence_delta.
        """
        state = _well_formed_final_state()
        # G1 is satisfied, but search_steps has NO gap_id match
        state["search_steps"] = [
            {"step": 1, "gap_id": None, "evidence_delta": {"n_new_papers": 5}},
        ]
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "satisfied"},
            {"gap_id": "G2", "status": "open"},
        ]
        passed, reasons = _compute_quality_pass(state)
        assert passed is False
        assert any("traceable evidence_delta" in r for r in reasons)

    def test_gap_with_traceable_evidence_delta_passes(self):
        """Gap satisfied AND gap_id appears in search_steps with evidence → passes."""
        state = _well_formed_final_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "satisfied"},
            {"gap_id": "G2", "status": "open"},
        ]
        state["search_steps"] = [
            {
                "step": 1,
                "gap_id": "G1",
                "evidence_delta": {"n_new_papers": 5, "n_new_repos": 0},
            },
        ]
        passed, reasons = _compute_quality_pass(state)
        assert not any("traceable evidence_delta" in r for r in reasons)

    def test_gap_with_only_repo_evidence_delta_passes(self):
        """Gap satisfied with repo evidence (n_new_repos > 0) → passes."""
        state = _well_formed_final_state()
        state["evidence_gaps"] = [
            {"gap_id": "G1", "status": "partially_satisfied"},
        ]
        state["search_steps"] = [
            {
                "step": 1,
                "gap_id": "G1",
                "evidence_delta": {"n_new_papers": 0, "n_new_repos": 2},
            },
        ]
        passed, reasons = _compute_quality_pass(state)
        assert not any("traceable evidence_delta" in r for r in reasons)


# ── Combined / integration-style tests ─────────────────────────────────────


class TestThreeTierPassScenario:
    """Tests combining both tiers to mirror the spec's scenario."""

    def test_spec_scenario_runtime_pass_but_contract_quality_fail(self):
        """Spec: 6 ambiguous seeds + 3 revise gates + 0 gaps closed.

        runtime_pass=true (final_rec exists),
        contract_pass=false (seed_cards missing resolved_title),
        quality_pass=false.
        """
        state = _all_ambiguous_final_state()
        # Ensure final_recommendation exists (runtime would pass)
        assert state.get("final_recommendation", {}).get("n_papers", 0) > 0

        contract_passed, contract_reasons = _compute_contract_pass(state)
        quality_passed, quality_reasons = _compute_quality_pass(state)

        assert contract_passed is False
        assert quality_passed is False
        assert "seed_cards: no seed has resolved_title" in contract_reasons
        assert any("no verified seed" in r for r in quality_reasons)

    def test_well_formed_state_passes_both_tiers(self):
        """A well-formed state passes both contract and quality tiers."""
        state = _well_formed_final_state()
        contract_passed, contract_reasons = _compute_contract_pass(state)
        quality_passed, quality_reasons = _compute_quality_pass(state)

        assert contract_passed is True
        assert contract_reasons == []
        assert quality_passed is True
        assert quality_reasons == []

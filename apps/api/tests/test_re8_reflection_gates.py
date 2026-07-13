"""Tests for Re8.0 WP6 — Reflection Gates + ReAct tool whitelist + Ledger.

Covers the Plan §8.5 capability matrix, §8.6 tool whitelist, §8.7 gate
semantics, §11 acceptance criteria.

Test classes:
  - TestReactToolWhitelist      — 10 whitelisted tools, hard reject off-list
  - TestIsReactReflectionEnabled — mode short-circuit logic
  - TestClampVerdict            — verdict normalization edge cases
  - TestNormalizeGateOutput     — 3-model schema stability (WP6 mirror of WP5)
  - TestRuleFallbacks           — each gate's deterministic rule layer
  - TestMakeGateLedger          — ledger entry shape + validate_ledger_entry
  - TestSeedAuditGateNode       — Lite/Offline short-circuit + Full path
  - TestTailorGateNode          — ditto for tailor gate
  - TestFinalReviewGateNode     — ditto for final review gate
  - TestRoundCapEnforcement     — 2-round cap emits unresolved
  - TestWP6Acceptance           — §11 A-09 / A-10 / A-11 acceptance
  - TestGatePromptBuilders      — prompt template formatting
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from apps.api.app.services.agents.graph.nodes import reflection_gates as rg
from apps.api.app.services.agents.graph.re80_schema import (
    LEDGER_STAGES,
    REACT_TOOL_WHITELIST,
    REFLECTION_GATE_MAX_ROUNDS,
    make_ledger_entry,
    make_reflection_gate_result,
    make_seed_card,
    make_evidence_gap,
    validate_ledger_entry,
    validate_reflection_gate_result,
)


# ── Test state builders ────────────────────────────────────────────────────


def _lite_state(**overrides: Any) -> dict[str, Any]:
    """Lite Chain mode — ReAct/Reflection must short-circuit."""
    base: dict[str, Any] = {
        "run_mode": "lite_chain",
        "reasoning_policy": "chain_only",
        "entry_mode": "seeded_research",
        "seed_cards": [],
        "evidence_gaps": [],
        "tailored_method": {},
        "novelty_review_verdict": "accepted",
        "falsifiable_hypothesis": "test hypothesis",
        "contribution_type": "methodological",
        "pressure_points": [],
        "reflection_gate_results": {},
    }
    base.update(overrides)
    return base


def _full_state(**overrides: Any) -> dict[str, Any]:
    """Full Agent mode — ReAct/Reflection may activate."""
    base: dict[str, Any] = {
        "run_mode": "full_agent",
        "reasoning_policy": "react_reflection",
        "entry_mode": "seeded_research",
        "seed_cards": [],
        "evidence_gaps": [],
        "tailored_method": {},
        "novelty_review_verdict": "accepted",
        "falsifiable_hypothesis": "test hypothesis",
        "contribution_type": "methodological",
        "pressure_points": [],
        "reflection_gate_results": {},
    }
    base.update(overrides)
    return base


def _offline_state(**overrides: Any) -> dict[str, Any]:
    """Offline Replay mode — ReAct/Reflection must short-circuit."""
    base: dict[str, Any] = {
        "run_mode": "offline_replay",
        "reasoning_policy": "chain_only",
        "entry_mode": "seeded_research",
        "seed_cards": [],
        "evidence_gaps": [],
        "tailored_method": {},
        "novelty_review_verdict": "accepted",
        "falsifiable_hypothesis": "test hypothesis",
        "contribution_type": "methodological",
        "pressure_points": [],
        "reflection_gate_results": {},
    }
    base.update(overrides)
    return base


def _verified_seed_card(seed_id: str = "S1", role: str = "classic_anchor") -> dict[str, Any]:
    return make_seed_card(
        seed_id=seed_id,
        input_form="title",
        resolved_title=f"Paper {seed_id}",
        existence_status="verified",
        fulltext_status="downloaded",
        role=role,
    )


def _gap(gap_id: str = "G1", question: str = "find 1+ baseline") -> dict[str, Any]:
    return make_evidence_gap(gap_id=gap_id, question=question)


# Mock target for call_json_with_validation
PATCH_CALL_JSON = (
    "apps.api.app.services.agents.graph.validators.llm_output_validator."
    "call_json_with_validation"
)


# ────────────────────────────────────────────────────────────────────────────
# 1. Tool whitelist
# ────────────────────────────────────────────────────────────────────────────


class TestReactToolWhitelist:
    def test_whitelist_has_10_tools(self):
        assert len(REACT_TOOL_WHITELIST) == 10

    def test_all_required_tools_present(self):
        required = {
            "resolve_paper", "fetch_metadata", "fetch_or_parse_pdf",
            "search_reference_chain", "search_method_family",
            "search_repo", "search_dataset",
            "extract_reproduction_environment",
            "compile_evidence", "request_tailor_review",
        }
        assert required.issubset(set(REACT_TOOL_WHITELIST))

    @pytest.mark.parametrize("tool", list(REACT_TOOL_WHITELIST))
    def test_allowed_tools_pass(self, tool):
        assert rg.is_tool_allowed(tool) is True

    @pytest.mark.parametrize("tool", [
        "arxiv", "pubmed", "semantic_scholar",  # legacy tools not in whitelist
        "openalex", "crossref", "huggingface",
        "execute_python", "browse_web",         # dangerous / unrestricted
        "", "unknown_tool",
    ])
    def test_off_whitelist_tools_rejected(self, tool):
        assert rg.is_tool_allowed(tool) is False


# ────────────────────────────────────────────────────────────────────────────
# 2. Mode short-circuit
# ────────────────────────────────────────────────────────────────────────────


class TestIsReactReflectionEnabled:
    def test_full_agent_with_react_reflection_enabled(self):
        assert rg.is_react_reflection_enabled(_full_state()) is True

    def test_lite_chain_short_circuits(self):
        assert rg.is_react_reflection_enabled(_lite_state()) is False

    def test_offline_replay_short_circuits(self):
        assert rg.is_react_reflection_enabled(_offline_state()) is False

    def test_full_agent_with_chain_only_short_circuits(self):
        state = _full_state(reasoning_policy="chain_only")
        assert rg.is_react_reflection_enabled(state) is False

    def test_lite_chain_with_react_reflection_short_circuits(self):
        state = _lite_state(reasoning_policy="react_reflection")
        assert rg.is_react_reflection_enabled(state) is False

    def test_missing_run_mode_short_circuits(self):
        state = _full_state()
        del state["run_mode"]
        assert rg.is_react_reflection_enabled(state) is False

    def test_missing_reasoning_policy_short_circuits(self):
        state = _full_state()
        del state["reasoning_policy"]
        assert rg.is_react_reflection_enabled(state) is False


# ────────────────────────────────────────────────────────────────────────────
# 3. Verdict clamping
# ────────────────────────────────────────────────────────────────────────────


class TestClampVerdict:
    @pytest.mark.parametrize("raw,expected", [
        ("pass", "pass"),
        ("Pass", "pass"),
        ("PASS", "pass"),
        ("ok", "pass"),
        ("accepted", "pass"),
        ("revise", "revise"),
        ("repair", "revise"),
        ("search", "revise"),
        ("unresolved", "unresolved"),
        ("fail", "unresolved"),
        ("stop", "unresolved"),
    ])
    def test_valid_verdicts_map_correctly(self, raw, expected):
        assert rg._clamp_verdict(raw) == expected

    @pytest.mark.parametrize("raw", [
        "", "yes", "no", "maybe", "go", "no-go",
        None, 123, [], {}, "garbage",
    ])
    def test_ambiguous_verdicts_default_to_unresolved(self, raw):
        """Conservative default — never silently downgrade to pass."""
        assert rg._clamp_verdict(raw) == "unresolved"


# ────────────────────────────────────────────────────────────────────────────
# 4. Schema stability across model output shapes (3-model test)
# ────────────────────────────────────────────────────────────────────────────


_MODEL_A_GATE = {  # well-behaved
    "verdict": "pass",
    "re_search_requests": [],
    "unresolved_gaps": [],
    "rationale": "all checks pass",
}

_MODEL_B_GATE = {  # sloppy — wrong types, missing fields, weird verdict
    "verdict": "OK",  # not in canonical set
    "re_search_requests": "none",  # not a list
    "rationale": None,  # None
    # unresolved_gaps missing
}

_MODEL_C_GATE = {  # minimal — only verdict
    "verdict": "unresolved",
}


class TestNormalizeGateOutput:
    REQUIRED_KEYS = {
        "gate_name", "verdict", "round_idx", "re_search_requests",
        "unresolved_gaps", "rationale", "generated_by",
    }

    def test_model_a_well_behaved(self):
        out = rg._normalize_gate_output(_MODEL_A_GATE, gate_name="seed_audit_gate", round_idx=0)
        assert self.REQUIRED_KEYS.issubset(out.keys())
        assert out["verdict"] == "pass"
        assert out["generated_by"] == "llm"

    def test_model_b_sloppy(self):
        out = rg._normalize_gate_output(_MODEL_B_GATE, gate_name="tailor_gate", round_idx=1)
        assert self.REQUIRED_KEYS.issubset(out.keys())
        assert out["verdict"] == "pass"  # "OK" → pass
        assert out["re_search_requests"] == []  # coerced to list
        assert out["unresolved_gaps"] == []  # missing → []
        assert out["rationale"] == "no rationale provided"  # None → fallback

    def test_model_c_minimal(self):
        out = rg._normalize_gate_output(_MODEL_C_GATE, gate_name="final_review_gate", round_idx=0)
        assert self.REQUIRED_KEYS.issubset(out.keys())
        assert out["verdict"] == "unresolved"
        assert out["re_search_requests"] == []
        assert out["unresolved_gaps"] == []

    def test_schema_stable_across_3_models(self):
        """WP6 acceptance: switching 3 model 'personalities' yields same key set."""
        outs = [
            rg._normalize_gate_output(m, gate_name="seed_audit_gate", round_idx=0)
            for m in (_MODEL_A_GATE, _MODEL_B_GATE, _MODEL_C_GATE)
        ]
        key_sets = [set(o.keys()) for o in outs]
        assert key_sets[0] == key_sets[1] == key_sets[2]
        assert self.REQUIRED_KEYS.issubset(key_sets[0])

    def test_none_input_handled(self):
        out = rg._normalize_gate_output(None, gate_name="tailor_gate", round_idx=0)
        assert out["verdict"] == "unresolved"
        assert out["rationale"] == "no rationale provided"

    def test_invalid_verdict_falls_back_to_unresolved(self):
        out = rg._normalize_gate_output(
            {"verdict": "garbage"}, gate_name="x", round_idx=0,
        )
        assert out["verdict"] == "unresolved"


# ────────────────────────────────────────────────────────────────────────────
# 5. Rule-based fallbacks
# ────────────────────────────────────────────────────────────────────────────


class TestRuleFallbackSeedAudit:
    def test_no_seeds_revise(self):
        state = _full_state(seed_cards=[])
        out = rg._rule_seed_audit_gate(state)
        assert out["verdict"] == "revise"
        assert "resolve_seed_identity" in out["re_search_requests"]

    def test_no_verified_seeds_revise(self):
        state = _full_state(seed_cards=[
            make_seed_card(seed_id="S1", existence_status="ambiguous"),
        ])
        out = rg._rule_seed_audit_gate(state)
        assert out["verdict"] == "revise"

    def test_verified_with_role_unknown_revise(self):
        state = _full_state(seed_cards=[
            make_seed_card(seed_id="S1", existence_status="verified", role="unknown"),
        ])
        out = rg._rule_seed_audit_gate(state)
        assert out["verdict"] == "revise"
        assert "classify_seed_role" in out["re_search_requests"]

    def test_verified_with_role_pass(self):
        state = _full_state(seed_cards=[_verified_seed_card()])
        out = rg._rule_seed_audit_gate(state)
        assert out["verdict"] == "pass"


class TestRuleFallbackTailor:
    def test_no_tailored_method_revise(self):
        state = _full_state(tailored_method={})
        out = rg._rule_tailor_gate(state)
        assert out["verdict"] == "revise"

    def test_no_go_verdict_unresolved(self):
        state = _full_state(tailored_method={
            "verdict": "NO-GO",
            "ablation_matrix": [{"experiment_id": "baseline"}, {"experiment_id": "a"},
                                {"experiment_id": "b"}, {"experiment_id": "a+b"}],
        })
        out = rg._rule_tailor_gate(state)
        assert out["verdict"] == "unresolved"

    def test_short_ablation_revise(self):
        state = _full_state(tailored_method={
            "verdict": "GO",
            "ablation_matrix": [{"experiment_id": "baseline"}],
        })
        out = rg._rule_tailor_gate(state)
        assert out["verdict"] == "revise"
        assert "search_method_family" in out["re_search_requests"]

    def test_full_ablation_pass(self):
        state = _full_state(tailored_method={
            "verdict": "GO",
            "ablation_matrix": [
                {"experiment_id": "baseline"},
                {"experiment_id": "a"},
                {"experiment_id": "b"},
                {"experiment_id": "a+b"},
            ],
        })
        out = rg._rule_tailor_gate(state)
        assert out["verdict"] == "pass"


class TestTailorGateCoreMethodTolerance:
    """Step 4: _TAILOR_PROMPT must tolerate empty core_method when
    assembly_plan.description is non-empty.

    Previously the prompt gave no guidance on incomplete upstream, so the
    LLM would reject any tailored_method with core_method="" even when a
    valid assembly_plan.description was present. This caused the Tailor
    gate to emit "unresolved" on cap reached → fused_verdict=BLOCKED.
    """

    def test_prompt_includes_core_method_tolerance_clause(self):
        """_TAILOR_PROMPT must mention core_method + assembly_plan fallback."""
        prompt = rg._TAILOR_PROMPT
        assert "core_method" in prompt
        assert "assembly_plan.description" in prompt
        assert "Do NOT reject solely on missing core_method" in prompt

    def test_prompt_instructs_revise_when_both_empty(self):
        """_TAILOR_PROMPT must call for revise when both fields are empty."""
        prompt = rg._TAILOR_PROMPT
        assert "BOTH core_method AND assembly_plan.description are empty" in prompt
        assert "revise" in prompt

    def test_build_tailor_prompt_renders_tolerance_clause(self):
        """_build_tailor_prompt output must contain the tolerance clause
        when rendered with a real state (not just the template)."""
        state = _full_state(tailored_method={
            "verdict": "GO",
            "core_method": "",
            "assembly_plan": {"description": "Use transformer encoder"},
            "ablation_matrix": [
                {"experiment_id": "baseline"},
                {"experiment_id": "a"},
                {"experiment_id": "b"},
                {"experiment_id": "a+b"},
            ],
        })
        rendered = rg._build_tailor_prompt(state)
        assert "core_method" in rendered
        assert "assembly_plan.description" in rendered
        assert "Do NOT reject solely on missing core_method" in rendered


class TestRuleFallbackFinalReview:
    def test_accepted_with_hypothesis_pass(self):
        state = _full_state(
            novelty_review_verdict="accepted",
            falsifiable_hypothesis="X causes Y",
        )
        out = rg._rule_final_review_gate(state)
        assert out["verdict"] == "pass"

    def test_weak_reject_revise(self):
        state = _full_state(
            novelty_review_verdict="weak_reject",
            falsifiable_hypothesis="X",
        )
        out = rg._rule_final_review_gate(state)
        assert out["verdict"] == "revise"

    def test_reject_unresolved(self):
        state = _full_state(
            novelty_review_verdict="reject",
            falsifiable_hypothesis="X",
        )
        out = rg._rule_final_review_gate(state)
        assert out["verdict"] == "unresolved"

    def test_missing_hypothesis_revise(self):
        state = _full_state(
            novelty_review_verdict="accepted",
            falsifiable_hypothesis="",
        )
        out = rg._rule_final_review_gate(state)
        assert out["verdict"] == "revise"


# ────────────────────────────────────────────────────────────────────────────
# 6. Ledger entry construction
# ────────────────────────────────────────────────────────────────────────────


class TestMakeGateLedger:
    def test_pass_ledger_shape(self):
        result = make_reflection_gate_result(
            gate_name="seed_audit_gate", verdict="pass", round_idx=0,
        )
        ledger = rg._make_gate_ledger(
            gate_name="seed_audit_gate",
            decision_id="seed_audit_gate-r0",
            result=result,
        )
        assert ledger["stage"] == "seed_audit_gate"
        assert ledger["decision"] == "gate_verdict=pass"
        assert ledger["status"] == "verified"
        assert ledger["confidence"] == 1.0
        assert ledger["next_action"] == "continue"
        assert validate_ledger_entry(ledger) == []

    def test_revise_ledger_shape(self):
        result = make_reflection_gate_result(
            gate_name="tailor_gate", verdict="revise", round_idx=1,
            re_search_requests=["search_method_family"],
            rationale="ablation short",
        )
        ledger = rg._make_gate_ledger(
            gate_name="tailor_gate",
            decision_id="tailor_gate-r1",
            result=result,
        )
        assert ledger["status"] == "proposed"
        assert ledger["confidence"] == 0.5
        assert ledger["next_action"] == "re_search"
        assert "search_method_family" in ledger["alternatives_considered"]
        assert "ablation short" in ledger["rejection_reasons"]

    def test_unresolved_ledger_shape(self):
        result = make_reflection_gate_result(
            gate_name="final_review_gate", verdict="unresolved", round_idx=2,
        )
        ledger = rg._make_gate_ledger(
            gate_name="final_review_gate",
            decision_id="final_review_gate-r2",
            result=result,
        )
        assert ledger["status"] == "unresolved"
        assert ledger["confidence"] == 0.0
        assert ledger["next_action"] == "stop"

    def test_ledger_stage_in_canonical_list(self):
        """All 3 gate stages must be in LEDGER_STAGES."""
        for gate_name in (rg.GATE_SEED_AUDIT, rg.GATE_TAILOR, rg.GATE_FINAL_REVIEW):
            assert gate_name in LEDGER_STAGES


# ────────────────────────────────────────────────────────────────────────────
# 7. Seed Audit Gate node — all paths
# ────────────────────────────────────────────────────────────────────────────


class TestSeedAuditGateNode:
    def test_lite_chain_short_circuits_to_pass(self):
        """A-10 acceptance: Lite Chain must not invoke ReAct/Reflection."""
        state = _lite_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = rg.seed_audit_gate_node(state)
        mock_llm.assert_not_called()  # critical: no LLM call in Lite mode
        assert out["reflection_gate_results"]["seed_audit_gate"][0]["verdict"] == "pass"
        assert out["reflection_gate_results"]["seed_audit_gate"][0]["generated_by"] == "skip"

    def test_offline_replay_short_circuits_to_pass(self):
        """A-11 acceptance: Offline Replay must not invoke ReAct/Reflection."""
        state = _offline_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = rg.seed_audit_gate_node(state)
        mock_llm.assert_not_called()
        assert out["reflection_gate_results"]["seed_audit_gate"][0]["verdict"] == "pass"

    def test_full_agent_calls_llm(self):
        state = _full_state(seed_cards=[_verified_seed_card()])
        with patch(PATCH_CALL_JSON, return_value={"verdict": "pass"}) as mock_llm:
            out = rg.seed_audit_gate_node(state)
        mock_llm.assert_called_once()
        result = out["reflection_gate_results"]["seed_audit_gate"][0]
        assert result["verdict"] == "pass"
        assert result["generated_by"] == "llm"
        assert result["round_idx"] == 0

    def test_full_agent_llm_failure_uses_rule_fallback(self):
        state = _full_state(seed_cards=[_verified_seed_card()])
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            out = rg.seed_audit_gate_node(state)
        result = out["reflection_gate_results"]["seed_audit_gate"][0]
        assert result["verdict"] == "pass"  # rule fallback says pass for verified seed
        assert result["generated_by"] == "fallback"

    def test_full_agent_llm_returns_non_dict_uses_rule_fallback(self):
        state = _full_state(seed_cards=[])  # rule will say revise
        with patch(PATCH_CALL_JSON, return_value=None):
            out = rg.seed_audit_gate_node(state)
        result = out["reflection_gate_results"]["seed_audit_gate"][0]
        assert result["verdict"] == "revise"
        assert result["generated_by"] == "fallback"

    def test_trace_events_emitted(self):
        """All paths must emit trace_events (parity with WP5)."""
        state = _lite_state()
        out = rg.seed_audit_gate_node(state)
        assert "trace_events" in out
        assert len(out["trace_events"]) == 1
        trace = out["trace_events"][0]
        assert trace["node"] == "reflection_gate::seed_audit_gate"
        assert "verdict" in trace["output_summary"]
        assert "generated_by" in trace["output_summary"]

    def test_ledger_entry_emitted(self):
        state = _lite_state()
        out = rg.seed_audit_gate_node(state)
        assert "reasoning_ledger" in out
        assert len(out["reasoning_ledger"]) == 1
        ledger = out["reasoning_ledger"][0]
        assert ledger["stage"] == "seed_audit_gate"
        assert validate_ledger_entry(ledger) == []


# ────────────────────────────────────────────────────────────────────────────
# 8. Tailor Gate node
# ────────────────────────────────────────────────────────────────────────────


class TestTailorGateNode:
    def test_lite_chain_short_circuits(self):
        state = _lite_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = rg.tailor_gate_node(state)
        mock_llm.assert_not_called()
        assert out["reflection_gate_results"]["tailor_gate"][0]["verdict"] == "pass"

    def test_full_agent_calls_llm(self):
        state = _full_state(tailored_method={
            "verdict": "GO",
            "ablation_matrix": [{"id": i} for i in range(4)],
        })
        with patch(PATCH_CALL_JSON, return_value={"verdict": "pass"}):
            out = rg.tailor_gate_node(state)
        result = out["reflection_gate_results"]["tailor_gate"][0]
        assert result["generated_by"] == "llm"

    def test_full_agent_llm_failure_uses_rule_fallback(self):
        state = _full_state(tailored_method={
            "verdict": "GO",
            "ablation_matrix": [{"id": i} for i in range(4)],
        })
        with patch(PATCH_CALL_JSON, side_effect=Exception("fail")):
            out = rg.tailor_gate_node(state)
        result = out["reflection_gate_results"]["tailor_gate"][0]
        assert result["generated_by"] == "fallback"
        assert result["verdict"] == "pass"  # rule says pass for GO + 4 ablation


# ────────────────────────────────────────────────────────────────────────────
# 9. Final Review Gate node
# ────────────────────────────────────────────────────────────────────────────


class TestFinalReviewGateNode:
    def test_lite_chain_short_circuits(self):
        state = _lite_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = rg.final_review_gate_node(state)
        mock_llm.assert_not_called()
        assert out["reflection_gate_results"]["final_review_gate"][0]["verdict"] == "pass"

    def test_full_agent_calls_llm(self):
        state = _full_state(
            novelty_review_verdict="accepted",
            falsifiable_hypothesis="X causes Y",
        )
        with patch(PATCH_CALL_JSON, return_value={"verdict": "pass"}):
            out = rg.final_review_gate_node(state)
        result = out["reflection_gate_results"]["final_review_gate"][0]
        assert result["generated_by"] == "llm"

    def test_full_agent_reject_unresolved_via_rule(self):
        state = _full_state(
            novelty_review_verdict="reject",
            falsifiable_hypothesis="X",
        )
        with patch(PATCH_CALL_JSON, side_effect=Exception("fail")):
            out = rg.final_review_gate_node(state)
        result = out["reflection_gate_results"]["final_review_gate"][0]
        assert result["verdict"] == "unresolved"


# ────────────────────────────────────────────────────────────────────────────
# 10. Round cap enforcement (§8.7: max 2 rounds, then unresolved)
# ────────────────────────────────────────────────────────────────────────────


class TestRoundCapEnforcement:
    def test_at_cap_emits_unresolved(self):
        """When round_idx == MAX_ROUNDS, gate must emit unresolved, not self-loop."""
        state = _full_state(reflection_gate_results={
            "seed_audit_gate": [
                make_reflection_gate_result(gate_name="seed_audit_gate", verdict="revise", round_idx=0),
                make_reflection_gate_result(gate_name="seed_audit_gate", verdict="revise", round_idx=1),
            ],
        })
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = rg.seed_audit_gate_node(state)
        mock_llm.assert_not_called()  # no LLM call when cap reached
        result = out["reflection_gate_results"]["seed_audit_gate"][-1]
        assert result["verdict"] == "unresolved"
        assert result["round_idx"] == REFLECTION_GATE_MAX_ROUNDS
        assert "cap reached" in result["rationale"]

    def test_below_cap_still_uses_llm(self):
        state = _full_state(reflection_gate_results={
            "tailor_gate": [
                make_reflection_gate_result(gate_name="tailor_gate", verdict="revise", round_idx=0),
            ],
        })
        with patch(PATCH_CALL_JSON, return_value={"verdict": "pass"}):
            out = rg.tailor_gate_node(state)
        result = out["reflection_gate_results"]["tailor_gate"][-1]
        assert result["round_idx"] == 1
        assert result["verdict"] == "pass"

    def test_lite_chain_at_cap_still_passes(self):
        """Lite Chain short-circuit takes precedence over cap check."""
        state = _lite_state(reflection_gate_results={
            "final_review_gate": [
                make_reflection_gate_result(gate_name="final_review_gate", verdict="pass", round_idx=0),
                make_reflection_gate_result(gate_name="final_review_gate", verdict="pass", round_idx=1),
            ],
        })
        out = rg.final_review_gate_node(state)
        result = out["reflection_gate_results"]["final_review_gate"][-1]
        assert result["verdict"] == "pass"
        assert result["generated_by"] == "skip"


# ────────────────────────────────────────────────────────────────────────────
# 11. WP6 acceptance criteria (Plan §11 A-09 / A-10 / A-11)
# ────────────────────────────────────────────────────────────────────────────


class TestWP6Acceptance:
    """A-09: Full Agent ReAct/Reflection 在预算内完成或有界退出.
    A-10: Lite Chain 无 ReAct/Reflection, Schema 完整.
    A-11: Offline Replay 网络调用为 0, fixture 可复现.
    """

    ALL_GATE_NODES = [
        ("seed_audit_gate", rg.seed_audit_gate_node),
        ("tailor_gate", rg.tailor_gate_node),
        ("final_review_gate", rg.final_review_gate_node),
    ]

    @pytest.mark.parametrize("gate_name,node", ALL_GATE_NODES)
    def test_a10_lite_chain_never_invokes_llm(self, gate_name, node):
        """A-10: Lite Chain must not invoke ReAct/Reflection LLM calls."""
        state = _lite_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = node(state)
        mock_llm.assert_not_called()
        # Schema完整性: every gate result has all 7 keys
        result = out["reflection_gate_results"][gate_name][0]
        required_keys = {
            "gate_name", "verdict", "round_idx", "re_search_requests",
            "unresolved_gaps", "rationale", "generated_by",
        }
        assert required_keys.issubset(result.keys())

    @pytest.mark.parametrize("gate_name,node", ALL_GATE_NODES)
    def test_a11_offline_replay_never_invokes_llm(self, gate_name, node):
        """A-11: Offline Replay must not invoke any LLM call."""
        state = _offline_state()
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = node(state)
        mock_llm.assert_not_called()

    @pytest.mark.parametrize("gate_name,node", ALL_GATE_NODES)
    def test_a09_full_agent_bounded_by_round_cap(self, gate_name, node):
        """A-09: Full Agent must terminate after REFLECTION_GATE_MAX_ROUNDS+1 calls."""
        # Pre-fill state with MAX_ROUNDS entries — next call must short-circuit
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(gate_name=gate_name, verdict="revise", round_idx=i)
                for i in range(REFLECTION_GATE_MAX_ROUNDS)
            ],
        })
        with patch(PATCH_CALL_JSON) as mock_llm:
            out = node(state)
        mock_llm.assert_not_called()
        result = out["reflection_gate_results"][gate_name][-1]
        assert result["verdict"] == "unresolved"

    @pytest.mark.parametrize("gate_name,node", ALL_GATE_NODES)
    def test_trace_events_have_consistent_schema(self, gate_name, node):
        """All gate traces carry provider/verdict/generated_by (parity with WP5)."""
        for state in (_lite_state(), _full_state(), _offline_state()):
            if state["run_mode"] == "full_agent":
                patcher = patch(PATCH_CALL_JSON, return_value={"verdict": "pass"})
            else:
                patcher = patch(PATCH_CALL_JSON)  # should not be called
            with patcher:
                out = node(state)
            trace = out["trace_events"][0]
            assert "verdict" in trace["output_summary"]
            assert "generated_by" in trace["output_summary"]
            assert trace["node"] == f"reflection_gate::{gate_name}"


# ────────────────────────────────────────────────────────────────────────────
# 12. Gate prompt builders
# ────────────────────────────────────────────────────────────────────────────


class TestGatePromptBuilders:
    def test_seed_audit_prompt_contains_seed_cards(self):
        state = _full_state(seed_cards=[_verified_seed_card()])
        prompt = rg._build_seed_audit_prompt(state)
        assert "Seed cards:" in prompt
        assert "Paper S1" in prompt
        assert "[OUTPUT CONTRACT]" in prompt

    def test_tailor_prompt_contains_tailored_method(self):
        state = _full_state(tailored_method={"verdict": "GO", "primary_baseline": {}})
        prompt = rg._build_tailor_prompt(state)
        assert "Tailored method:" in prompt
        assert "GO" in prompt

    def test_final_review_prompt_contains_verdict(self):
        state = _full_state(
            novelty_review_verdict="accepted",
            falsifiable_hypothesis="X causes Y",
        )
        prompt = rg._build_final_review_prompt(state)
        assert "accepted" in prompt
        assert "X causes Y" in prompt

    def test_seed_audit_prompt_handles_empty_state(self):
        state = _full_state()
        prompt = rg._build_seed_audit_prompt(state)
        assert "Seed cards:" in prompt  # template renders even with empty input

    def test_tailor_prompt_handles_empty_state(self):
        state = _full_state()
        prompt = rg._build_tailor_prompt(state)
        assert "Tailored method:" in prompt


# ────────────────────────────────────────────────────────────────────────────
# 13. Reflection gate result schema
# ────────────────────────────────────────────────────────────────────────────


class TestReflectionGateResult:
    def test_make_result_defaults(self):
        result = make_reflection_gate_result(gate_name="x")
        assert result["verdict"] == "unresolved"  # conservative default
        assert result["round_idx"] == 0
        assert result["re_search_requests"] == []
        assert result["unresolved_gaps"] == []
        assert result["rationale"] == ""
        assert result["generated_by"] == "llm"

    def test_make_result_invalid_verdict_clamped(self):
        result = make_reflection_gate_result(gate_name="x", verdict="garbage")
        assert result["verdict"] == "unresolved"

    def test_validate_result_passes_good(self):
        result = make_reflection_gate_result(gate_name="x", verdict="pass")
        assert validate_reflection_gate_result(result) == []

    def test_validate_result_catches_bad_verdict(self):
        bad = {"gate_name": "x", "verdict": "nope", "round_idx": 0,
               "re_search_requests": [], "unresolved_gaps": []}
        errs = validate_reflection_gate_result(bad)
        assert any("verdict" in e for e in errs)


# ────────────────────────────────────────────────────────────────────────────
# 14. Integration: gate → ledger → trace consistency
# ────────────────────────────────────────────────────────────────────────────


class TestGateLedgerTraceConsistency:
    def test_state_patch_keys_match_node_fields(self):
        """NODE_FIELDS declaration must match what the node actually returns."""
        from apps.api.app.services.agents.graph.nodes import NODE_FIELDS
        state = _lite_state()
        out = rg.seed_audit_gate_node(state)
        declared = set(NODE_FIELDS["seed_audit_gate"])
        actual = set(out.keys())
        # trace_events is in declared; reflection_gate_results and reasoning_ledger too
        assert actual.issubset(declared | {"trace_events"})  # trace_events always present

    def test_three_gates_produce_independent_logs(self):
        """Running all 3 gates in sequence produces 3 separate log entries."""
        state = _lite_state()
        out1 = rg.seed_audit_gate_node(state)
        # Update state with patch
        state2 = {**state, **out1}
        out2 = rg.tailor_gate_node(state2)
        state3 = {**state2, **out2}
        out3 = rg.final_review_gate_node(state3)

        # Each gate has exactly 1 entry in its own log
        final_results = out3["reflection_gate_results"]
        assert len(final_results["seed_audit_gate"]) == 1
        assert len(final_results["tailor_gate"]) == 1
        assert len(final_results["final_review_gate"]) == 1

    def test_ledger_stage_matches_gate_name(self):
        state = _lite_state()
        for gate_name, node in self.ALL_GATE_NODES:
            out = node(state)
            ledger = out["reasoning_ledger"][0]
            assert ledger["stage"] == gate_name
            assert validate_ledger_entry(ledger) == []

    ALL_GATE_NODES = [
        ("seed_audit_gate", rg.seed_audit_gate_node),
        ("tailor_gate", rg.tailor_gate_node),
        ("final_review_gate", rg.final_review_gate_node),
    ]


# ── P2 fixup: search_agent.py integration (WP6 follow-up) ──────────────────


class TestSearchAgentModeShortCircuit:
    """P2-2: search_agent.py must short-circuit LLM in Lite/Offline mode.

    Plan §8.5 capability matrix: Lite Chain and Offline Replay must NOT
    invoke the LLM-driven ReAct loop. They fall back to deterministic
    plan-query iteration. Legacy topic_only (run_mode unset) preserves
    old LLM-driven behavior for backward compatibility.
    """

    def test_lite_chain_uses_fallback_not_llm(self, monkeypatch):
        """Lite Chain mode → search_agent uses _fallback_decide, not _llm_decide."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_llm_decide", side_effect=AssertionError("LLM must not be called in lite_chain")) as mock_llm, \
             patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        assert not mock_llm.called
        assert result["provider_profile"] == "local"

    def test_offline_replay_uses_fallback_not_llm(self, monkeypatch):
        """Offline Replay mode → search_agent uses _fallback_decide."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "offline_replay",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_llm_decide", side_effect=AssertionError("LLM must not be called in offline_replay")) as mock_llm, \
             patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        assert not mock_llm.called
        assert result["provider_profile"] == "local"

    def test_legacy_no_run_mode_uses_llm(self, monkeypatch):
        """Legacy topic_only (run_mode unset) → LLM-driven (backward compat)."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        decisions = [
            {"action": "search", "tool": "arxiv", "query": "rag", "reason": "go"},
            {"action": "stop", "reason": "enough"},
        ]
        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": []},
            "trace_events": [],
        }
        with patch.object(sa, "_llm_decide") as mock_llm, \
             patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            decision_iter = iter(decisions)
            mock_llm.side_effect = lambda *a, **k: (next(decision_iter), "fast_json")
            result = sa.search_agent_node(state)
        assert mock_llm.called
        assert result["provider_profile"] == "fast_json"

    def test_full_agent_uses_llm(self, monkeypatch):
        """Full Agent + react_reflection → LLM-driven ReAct."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        decisions = [
            {"action": "search", "tool": "arxiv", "query": "rag", "reason": "go"},
            {"action": "stop", "reason": "enough"},
        ]
        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": []},
            "trace_events": [],
            "run_mode": "full_agent",
            "reasoning_policy": "react_reflection",
        }
        decision_iter = iter(decisions)
        with patch.object(sa, "_llm_decide", side_effect=lambda *a, **k: (next(decision_iter), "fast_json")) as mock_llm, \
             patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        assert mock_llm.called
        assert result["provider_profile"] == "fast_json"


class TestSearchAgentReactActions:
    """P2-3: search_agent.py must write react_actions audit trail.

    Plan §8.6: "每次动作必须记录：目标 Gap → 工具 → 预期成功条件 →
    实际结果 → 下一动作."
    """

    def test_react_actions_in_return_patch(self, monkeypatch):
        """search_agent_node return must include react_actions key."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        assert "react_actions" in result
        assert isinstance(result["react_actions"], list)
        assert len(result["react_actions"]) > 0

    def test_react_actions_has_whitelist_field(self, monkeypatch):
        """P2-1: each react_actions entry must have whitelist_allowed field."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        for entry in result["react_actions"]:
            assert "whitelist_allowed" in entry
            assert isinstance(entry["whitelist_allowed"], bool)

    def test_react_actions_records_gap_id_when_gap_bound(self, monkeypatch):
        """react_actions entries must carry gap_id for gap-bound queries."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {
                "queries": [{
                    "tool": "arxiv", "query": "rag qa",
                    "gap_id": "G1", "success_condition": "find 1+ paper",
                    "lane_id": "competing",
                }],
                "gap_bound": True,
            },
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        gap_entries = [e for e in result["react_actions"] if e.get("gap_id")]
        assert len(gap_entries) > 0
        assert gap_entries[0]["gap_id"] == "G1"

    def test_trace_records_react_enabled_flag(self, monkeypatch):
        """Trace output_summary must record react_enabled for auditability."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "full_agent",
            "reasoning_policy": "react_reflection",
        }
        decision_iter = iter([
            {"action": "search", "tool": "arxiv", "query": "rag qa", "reason": "go"},
            {"action": "stop", "reason": "enough"},
        ])
        with patch.object(sa, "_llm_decide", side_effect=lambda *a, **k: (next(decision_iter), "fast_json")), \
             patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        trace = result["trace_events"][0]
        assert "react_enabled" in trace["output_summary"]
        assert trace["output_summary"]["react_enabled"] is True
        assert "n_react_actions" in trace["output_summary"]

    def test_react_actions_records_failed_dispatch(self, monkeypatch):
        """react_actions must record entry when _run_tool_sync raises exception."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_run_tool_sync", side_effect=RuntimeError("network error")), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        failed_entries = [e for e in result["react_actions"] if e.get("failed")]
        assert len(failed_entries) > 0
        assert failed_entries[0]["n_results"] == 0
        assert failed_entries[0]["gap_resolved"] is False
        assert "next_action" in failed_entries[0]

    def test_react_actions_schema_consistent_across_paths(self, monkeypatch):
        """All react_actions entries must have the same set of keys (Plan §8.6)."""
        from apps.api.app.services.agents.graph.nodes import search_agent as sa

        state = {
            "topic": "test topic",
            "topic_atoms": {"method": ["rag"], "object": ["qa"], "domain": "nlp"},
            "search_plan": {"queries": [{"tool": "arxiv", "query": "rag qa"}]},
            "trace_events": [],
            "run_mode": "lite_chain",
            "reasoning_policy": "chain_only",
        }
        with patch.object(sa, "_run_tool_sync", return_value=[{"title": "paper", "abstract": "abs"}]), \
             patch.object(sa, "_get_domain_tools", return_value=set()), \
             patch("apps.api.app.services.search_catalog.get_source_catalog") as mock_cat:
            mock_cat.return_value.allowed_source_names.return_value = ["arxiv"]
            mock_cat.return_value.source_list_for_prompt.return_value = []
            result = sa.search_agent_node(state)
        # All entries must have the same key set
        key_sets = [set(e.keys()) for e in result["react_actions"]]
        assert len(key_sets) > 0
        first_keys = key_sets[0]
        for ks in key_sets[1:]:
            assert ks == first_keys, f"Schema inconsistency: {first_keys} vs {ks}"
        # Verify required Plan §8.6 fields are present
        required = {"step", "tool", "gap_id", "success_condition",
                    "whitelist_allowed", "n_results", "gap_resolved",
                    "failed", "next_action", "reason"}
        assert required.issubset(first_keys)


# ────────────────────────────────────────────────────────────────────────────
# 15. Conditional repair routing — route_after_gate (Re8.0 P0-2)
# ────────────────────────────────────────────────────────────────────────────


# Forward / repair targets per gate — single source of truth for the
# parametrized tests below. Mirrors _GATE_FORWARD_TARGETS /
# _GATE_REPAIR_TARGETS in reflection_gates.py.
# Re8.0 post-audit: seed_audit_gate forward target changed from
# paper_understanding to fulltext_acquisition (node order swapped so
# PDFs are downloaded before parsing).
_GATE_ROUTING_TARGETS = [
    (rg.GATE_SEED_AUDIT,   "fulltext_acquisition",  "seed_resolver"),
    (rg.GATE_TAILOR,       "innovation_extractor", "search_planner"),
    (rg.GATE_FINAL_REVIEW, "falsifiability",       "evidence_context"),
]


class TestRouteAfterGate:
    """Re8.0 P0-2: route_after_gate drives the conditional repair edges.

    Each gate has a forward target (linear spine) and a repair target
    (upstream node that can fix the gap). The router reads the gate's
    last result from state["reflection_gate_results"][gate_name][-1]
    and routes based on verdict + round_idx.

    Covers SubTasks 2.5 (pass / revise / unresolved routing for all 3
    gates) and 2.6 (round_idx at cap → forward).
    """

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_verdict_pass_routes_forward(self, gate_name, forward, repair):
        """verdict=pass → forward target (gate satisfied)."""
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="pass", round_idx=0,
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_verdict_revise_round_0_routes_repair(self, gate_name, forward, repair):
        """verdict=revise + round_idx=0 → repair target (loop back)."""
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="revise", round_idx=0,
                    re_search_requests=["G1"],
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == repair

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_verdict_revise_at_cap_routes_forward(self, gate_name, forward, repair):
        """SubTask 2.6: verdict=revise + round_idx=2 (cap) → forward.

        The gate normally emits ``unresolved`` once the cap is reached
        (see TestRoundCapEnforcement), but the router must also defend
        against a revise leaking past the cap. This guarantees the
        repair loop terminates even if a future change to the gate
        forgets the cap check.
        """
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="revise",
                    round_idx=REFLECTION_GATE_MAX_ROUNDS,
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_verdict_unresolved_routes_forward(self, gate_name, forward, repair):
        """verdict=unresolved → forward target (cap reached / hard failure)."""
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="unresolved", round_idx=1,
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_verdict_revise_round_1_still_routes_repair(self, gate_name, forward, repair):
        """verdict=revise + round_idx=1 (one round left) → repair target.

        MAX_ROUNDS=2 means round_idx 0 and 1 are both eligible for
        repair; only round_idx >= 2 forces forward.
        """
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="revise", round_idx=0,
                ),
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="revise", round_idx=1,
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == repair

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_lite_chain_pass_routes_forward(self, gate_name, forward, repair):
        """Backward compat: Lite Chain emits pass (generated_by=skip) → forward.

        This is the critical backward-compat guarantee — topic_only /
        lite_chain / offline_replay callers see no behavior change
        because their gates always emit pass via the mode short-circuit.
        """
        state = _lite_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="pass", round_idx=0,
                    generated_by="skip",
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_empty_log_routes_forward(self, gate_name, forward, repair):
        """Defensive: empty gate log (no result yet) → forward.

        Shouldn't normally happen (the gate node runs before this
        router), but the router must not crash — it routes forward
        when there's no signal to act on.
        """
        state = _full_state(reflection_gate_results={})
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_missing_reflection_gate_results_key_routes_forward(self, gate_name, forward, repair):
        """Defensive: state missing reflection_gate_results entirely → forward."""
        state = _full_state()
        del state["reflection_gate_results"]
        assert rg.route_after_gate(state, gate_name) == forward

    @pytest.mark.parametrize("gate_name,forward,repair", _GATE_ROUTING_TARGETS)
    def test_revise_with_round_idx_over_cap_routes_forward(self, gate_name, forward, repair):
        """round_idx well over MAX_ROUNDS (e.g. 99) → forward regardless of revise."""
        state = _full_state(reflection_gate_results={
            gate_name: [
                make_reflection_gate_result(
                    gate_name=gate_name, verdict="revise", round_idx=99,
                ),
            ],
        })
        assert rg.route_after_gate(state, gate_name) == forward

    def test_unknown_gate_raises_value_error(self):
        """Unknown gate_name is a programming error — fail fast, do not silently misroute."""
        state = _full_state()
        with pytest.raises(ValueError, match="unknown gate_name"):
            rg.route_after_gate(state, "totally_fake_gate")

    def test_all_three_gates_have_distinct_targets(self):
        """Sanity: no two gates share the same forward or repair target."""
        forwards = [f for _, f, _ in _GATE_ROUTING_TARGETS]
        repairs = [r for _, _, r in _GATE_ROUTING_TARGETS]
        assert len(set(forwards)) == 3, "forward targets must be distinct"
        assert len(set(repairs)) == 3, "repair targets must be distinct"


# ────────────────────────────────────────────────────────────────────────────
# 16. P1-1: _is_gate_capped + _GATE_REPAIR_PATH_DOWNSTREAM_GATES
# ────────────────────────────────────────────────────────────────────────────


class TestP11IsGateCapped:
    """Re8.0 P1-1: _is_gate_capped + repair-path downstream gate dependencies.

    When a gate emits verdict=revise and routes to its repair target, the
    repair path may re-trigger a DIFFERENT gate that has already hit its
    round cap. route_after_gate must forward instead of repair when the
    downstream gate is capped, because the downstream gate will immediately
    re-emit unresolved and we would loop back with inflated round_idx.

    Covers reflection_gates.py lines 672-708 (_is_gate_capped +
    _GATE_REPAIR_PATH_DOWNSTREAM_GATES) and lines 778-795 (route_after_gate
    P1-1 downstream-cap check).

    _GATE_REPAIR_PATH_DOWNSTREAM_GATES = {
        GATE_FINAL_REVIEW: [GATE_TAILOR],
    }

    _is_gate_capped(state, gate_name) returns True when:
      - last verdict == "unresolved", OR
      - round_idx >= REFLECTION_GATE_MAX_ROUNDS
    Returns False when the gate has no logged entries.
    """

    def test_final_review_revise_when_tailor_capped_routes_forward(self):
        """final_review_gate verdict=revise 且 tailor_gate 已 capped → forward.

        _GATE_REPAIR_PATH_DOWNSTREAM_GATES[GATE_FINAL_REVIEW] = [GATE_TAILOR].
        When tailor_gate's last verdict is unresolved, the repair path
        (evidence_context → tailor_skill_adapter → tailor_gate) cannot
        produce new signal, so route_after_gate must forward to
        "falsifiability" instead of repairing to "evidence_context".
        """
        state = _full_state(reflection_gate_results={
            "tailor_gate": [
                make_reflection_gate_result(
                    gate_name="tailor_gate", verdict="unresolved", round_idx=2,
                ),
            ],
            "final_review_gate": [
                make_reflection_gate_result(
                    gate_name="final_review_gate", verdict="revise", round_idx=0,
                ),
            ],
        })
        # forward target for final_review_gate is "falsifiability"
        assert rg.route_after_gate(state, rg.GATE_FINAL_REVIEW) == "falsifiability"

    def test_final_review_revise_when_tailor_not_capped_routes_repair(self):
        """final_review_gate verdict=revise 且 tailor_gate 未 capped → repair.

        When tailor_gate is NOT capped (verdict=pass), the repair path is
        still viable, so route_after_gate returns the repair target
        "evidence_context".
        """
        state = _full_state(reflection_gate_results={
            "tailor_gate": [
                make_reflection_gate_result(
                    gate_name="tailor_gate", verdict="pass", round_idx=0,
                ),
            ],
            "final_review_gate": [
                make_reflection_gate_result(
                    gate_name="final_review_gate", verdict="revise", round_idx=0,
                ),
            ],
        })
        # repair target for final_review_gate is "evidence_context"
        assert rg.route_after_gate(state, rg.GATE_FINAL_REVIEW) == "evidence_context"

    def test_is_gate_capped_unresolved_verdict(self):
        """_is_gate_capped 对 verdict=unresolved 返回 True.

        Even with round_idx=0 (below cap), an unresolved verdict means the
        gate has hard-failed and cannot produce new signal on re-entry.
        """
        state = _full_state(reflection_gate_results={
            "tailor_gate": [
                make_reflection_gate_result(
                    gate_name="tailor_gate", verdict="unresolved", round_idx=0,
                ),
            ],
        })
        assert rg._is_gate_capped(state, rg.GATE_TAILOR) is True

    def test_is_gate_capped_round_idx_at_cap(self):
        """_is_gate_capped 对 round_idx >= REFLECTION_GATE_MAX_ROUNDS 返回 True.

        A revise verdict at the round cap means the gate has exhausted its
        repair budget — re-entering the repair path is futile.
        """
        state = _full_state(reflection_gate_results={
            "tailor_gate": [
                make_reflection_gate_result(
                    gate_name="tailor_gate", verdict="revise",
                    round_idx=REFLECTION_GATE_MAX_ROUNDS,
                ),
            ],
        })
        assert rg._is_gate_capped(state, rg.GATE_TAILOR) is True

    def test_is_gate_capped_no_entries(self):
        """_is_gate_capped 对空 entries 返回 False.

        Defensive: a gate with no logged results is not capped (it simply
        hasn't run yet). This avoids spurious forwarding on the first
        invocation.
        """
        state = _full_state(reflection_gate_results={})
        assert rg._is_gate_capped(state, rg.GATE_TAILOR) is False

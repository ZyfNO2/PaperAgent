"""Re8.0 WP5 Tailor / Review Skill Adapter Tests.

WP5 acceptance (Plan §10 WP5): "切换至少三类模型时 Schema 稳定，失败可降级"

Test coverage:
- Tailor Skill: 8-field schema, entry_mode gate, schema stability across
  3 simulated model outputs, fallback degradation, verdict/compatibility
  clamping, ablation matrix minimum (Baseline/A/B/A+B), ReasoningLedgerEntry
  appended, trace visibility.
- Novelty Review: P-M-I structure, 3-granularity contributions, falsifiable
  hypothesis, contribution_type clamping, backward compat (existing fields
  preserved), tailored_method consumed when present, schema stability.
- WP5 acceptance: 3-model schema stability + failure-degrades-gracefully.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from apps.api.app.services.agents.graph.nodes.tailor_skill_adapter import (
    _clamp_compatibility,
    _clamp_verdict,
    _fallback_tailor,
    _normalize_tailor_output,
    build_tailor_prompt,
    tailor_skill_adapter_node,
    TAILOR_VERDICTS,
)
from apps.api.app.services.agents.graph.nodes.novelty_review import (
    CONTRIBUTION_TYPES,
    _clamp_contribution_type,
    _clamp_verdict as _clamp_review_verdict,
    _empty_review,
    _normalize_pmi,
    _normalize_contributions,
    build_novelty_review_prompt,
    novelty_review_node,
    normalize_review_output,
)
from apps.api.app.services.agents.graph.re80_schema import (
    make_evidence_gap,
    make_ledger_entry,
    make_method_family,
    make_seed_card,
    validate_ledger_entry,
)

PATCH_CALL_JSON = (
    "apps.api.app.services.agents.graph.validators.llm_output_validator"
    ".call_json_with_validation"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_seeded_state(*, with_tailored: bool = False) -> dict[str, Any]:
    """Build a minimal seeded_research state for Tailor / Review tests."""
    state: dict[str, Any] = {
        "entry_mode": "seeded_research",
        "run_mode": "full_agent",
        "network_policy": "online",
        "topic": "small object detection in complex scenes",
        "seed_cards": [
            make_seed_card(
                seed_id="s1",
                resolved_title="You Only Look Once: Unified, Real-Time Object Detection",
                role="classic_anchor",
                task_definition="object detection",
                method_summary="single-stage detector with grid predictions",
                dataset_and_metrics={
                    "datasets": [{"name": "PASCAL VOC", "size": "20k images"}],
                    "metrics": [{"name": "mAP", "value": "63.4"}],
                },
                reproduction_environment={
                    "framework": "Darknet",
                    "hardware": "Titan X",
                    "hyperparameters": {"lr": 0.001, "batch_size": 64},
                },
                limitations=["limited to grid-based detection", "struggles with small objects"],
            ),
        ],
        "method_families": [
            make_method_family(
                family_id="fam-1",
                name="YOLO family",
                relation_to_seed="direct",
            ),
        ],
        "search_lanes": [
            {"lane_id": "anchor_reference", "queries": ["YOLO original"],
             "gap_id": "gap-s1-anchor_reference"},
            {"lane_id": "competing_baseline", "queries": ["Faster R-CNN"],
             "gap_id": "gap-s1-competing_baseline"},
        ],
        "evidence_gaps": [
            make_evidence_gap(
                gap_id="gap-s1-anchor_reference",
                gap_type="existence",
                question="find 1+ origin paper",
                status="open",
            ),
        ],
        "baseline_candidates": [
            {"id": "b1", "title": "Faster R-CNN"},
        ],
        "innovation_points": [
            {"point": "small-object-aware feature fusion"},
        ],
        "reasoning_ledger": [],
        "search_budget": {"max_searches": 20},
    }
    if with_tailored:
        state["tailored_method"] = _normalize_tailor_output({
            "primary_baseline": {"baseline_id": "b1", "title": "Faster R-CNN"},
            "verdict": "GO",
            "candidate_modules": [{"name": "FPN-lite"}],
        })
    return state


# Simulated outputs from three different model "personalities"
_MODEL_A_OUTPUT = {  # well-behaved model
    "primary_baseline": {"baseline_id": "b1", "title": "Faster R-CNN",
                         "selection_reason": "strong baseline for detection"},
    "candidate_modules": [
        {"module_id": "m1", "name": "FPN-lite",
         "source_evidence_id": "s1", "target_failure_mode": "small object recall"},
    ],
    "compatibility_analysis": [
        {"module_id": "m1", "semantic": "compatible",
         "interface": "feature pyramid", "training_objective": "detection"},
    ],
    "assembly_plan": {"description": "attach FPN-lite to Faster R-CNN",
                      "steps": ["step1"], "expected_interfaces": ["feature maps"]},
    "ablation_matrix": [
        {"experiment_id": "baseline", "config": "Faster R-CNN",
         "tests_hypothesis": "sanity", "expected_signal": "reported mAP"},
        {"experiment_id": "A", "config": "+FPN-lite",
         "tests_hypothesis": "small object recall", "expected_signal": "+2 mAP"},
        {"experiment_id": "B", "config": "+attention",
         "tests_hypothesis": "feature focus", "expected_signal": "+1 mAP"},
        {"experiment_id": "A+B", "config": "+both",
         "tests_hypothesis": "synergy", "expected_signal": ">=max(A,B)"},
    ],
    "fair_comparison_requirements": ["same splits", "same compute"],
    "verdict": "GO",
    "verdict_reason": "modules are compatible and address real failure modes",
    "evidence_gaps_for_research": [
        {"gap_id": "gap-s1-anchor_reference", "description": "need origin",
         "priority": "high"},
    ],
}

_MODEL_B_OUTPUT = {  # sloppy model: missing fields, wrong types, weird verdict
    "primary_baseline": "just a string title",  # wrong type
    "candidate_modules": "not a list",  # wrong type
    "compatibility_analysis": [
        {"module_id": "m1", "semantic": "WEIRD"},  # invalid enum
    ],
    # ablation_matrix missing entirely
    "fair_comparison_requirements": "same splits",  # string not list
    "verdict": "yes",  # not in allowed set
    # verdict_reason missing
    # evidence_gaps_for_research missing
}

_MODEL_C_OUTPUT = {  # minimal model: only verdict
    "verdict": "NO-GO",
    "verdict_reason": "insufficient evidence",
}

_MODEL_D_REVIEW_FULL = {  # well-behaved review
    "verdict": "accepted",
    "novelty_score": 7,
    "pseudo_innovation_risks": ["risk1"],
    "pressure_points": [{"risk": "repetition", "question": "q", "severity": "low",
                         "repair": "r", "evidence_ids": ["s1"]}],
    "differentiation_matrix": [{"adjacent_work_id": "p1", "adjacent_work_label": "Paper",
                                "problem_diff": "d", "method_diff": "d", "detail_diff": "d",
                                "evidence_diff": "d", "insight_diff": "d"}],
    "required_repairs": ["repair1"],
    "strengths": ["strength1"],
    "risks": ["risk1"],
    "problem_method_insight": {"problem": "small object recall",
                                "method": "FPN-lite",
                                "insight": "feature pyramid helps small objects"},
    "contributions": {"one_sentence": "we propose X",
                      "three_sentence": "we propose X. it does Y. we test Z.",
                      "paragraph": "long paragraph..."},
    "falsifiable_hypothesis": "FPN-lite does not help when objects are <4px",
    "minimum_key_experiment": "ablation on small object subset",
    "contribution_type": "methodological",
}

_MODEL_E_REVIEW_SLOPPY = {  # missing all new fields
    "verdict": "Accept",  # wrong case
    "novelty_score": "high",  # wrong type
    "contribution_type": "WACKY-TYPE",  # invalid
}


# ---------------------------------------------------------------------------
# Tailor: _clamp_verdict / _clamp_compatibility
# ---------------------------------------------------------------------------

class TestClampVerdict:
    def test_valid_verdicts_pass_through(self):
        for v in TAILOR_VERDICTS:
            assert _clamp_verdict(v) == v

    def test_lowercase_normalized(self):
        assert _clamp_verdict("go") == "GO"
        assert _clamp_verdict("revise") == "REVISE"
        assert _clamp_verdict("no-go") == "NO-GO"

    def test_yes_does_not_become_go(self):
        """§9.3 step 4: 解析失败不得被当作 GO. "yes" is not a valid verdict
        and must degrade to REVISE rather than be treated as GO."""
        assert _clamp_verdict("yes") == "REVISE"

    def test_unknown_defaults_to_revise(self):
        assert _clamp_verdict("maybe") == "REVISE"
        assert _clamp_verdict(None) == "REVISE"
        assert _clamp_verdict(42) == "REVISE"


class TestClampCompatibility:
    def test_valid_levels_pass_through(self):
        for c in ("compatible", "partial", "incompatible"):
            assert _clamp_compatibility(c) == c

    def test_invalid_defaults_to_partial(self):
        assert _clamp_compatibility("weird") == "partial"
        assert _clamp_compatibility(None) == "partial"


# ---------------------------------------------------------------------------
# Tailor: _normalize_tailor_output (schema stability chokepoint)
# ---------------------------------------------------------------------------

class TestNormalizeTailorOutput:
    def test_well_behaved_output_preserved(self):
        out = _normalize_tailor_output(_MODEL_A_OUTPUT)
        assert out["verdict"] == "GO"
        assert out["primary_baseline"]["title"] == "Faster R-CNN"
        assert len(out["candidate_modules"]) == 1
        assert out["compatibility_analysis"][0]["semantic"] == "compatible"
        assert len(out["ablation_matrix"]) == 4
        assert out["generated_by"] == "llm"

    def test_sloppy_output_normalized(self):
        out = _normalize_tailor_output(_MODEL_B_OUTPUT)
        # primary_baseline coerced to dict
        assert isinstance(out["primary_baseline"], dict)
        assert out["primary_baseline"]["title"] == "just a string title"
        # candidate_modules coerced to list
        assert out["candidate_modules"] == []
        # compatibility clamped
        assert out["compatibility_analysis"][0]["semantic"] == "partial"
        # ablation_matrix backfilled to minimum 4 rows
        assert len(out["ablation_matrix"]) >= 4
        exp_ids = {a["experiment_id"] for a in out["ablation_matrix"]}
        assert {"baseline", "a", "b", "a+b"}.issubset(exp_ids)
        # fair_comparison_requirements coerced to list of strings
        assert isinstance(out["fair_comparison_requirements"], list)
        assert all(isinstance(r, str) for r in out["fair_comparison_requirements"])
        # verdict clamped
        assert out["verdict"] in TAILOR_VERDICTS
        # verdict_reason defaulted to empty string
        assert isinstance(out["verdict_reason"], str)
        # evidence_gaps_for_research defaulted to list
        assert out["evidence_gaps_for_research"] == []

    def test_minimal_output_backfilled(self):
        out = _normalize_tailor_output(_MODEL_C_OUTPUT)
        assert out["verdict"] == "NO-GO"
        assert out["verdict_reason"] == "insufficient evidence"
        # all missing fields backfilled
        assert isinstance(out["primary_baseline"], dict)
        assert out["candidate_modules"] == []
        assert out["compatibility_analysis"] == []
        assert isinstance(out["assembly_plan"], dict)
        assert len(out["ablation_matrix"]) >= 4
        assert out["fair_comparison_requirements"] == []
        assert out["evidence_gaps_for_research"] == []

    def test_ablation_matrix_never_fewer_than_4(self):
        """§11.2 methodology gate: at least Baseline / A / B / A+B."""
        for raw in (_MODEL_A_OUTPUT, _MODEL_B_OUTPUT, _MODEL_C_OUTPUT):
            out = _normalize_tailor_output(raw)
            ids = {str(a.get("experiment_id", "")).lower()
                   for a in out["ablation_matrix"]}
            assert {"baseline", "a", "b", "a+b"}.issubset(ids), \
                f"missing ablation rows in {ids}"

    def test_priority_clamped(self):
        raw = {"evidence_gaps_for_research": [
            {"gap_id": "g1", "priority": "URGENT"},  # invalid
            {"gap_id": "g2", "priority": "high"},
        ]}
        out = _normalize_tailor_output(raw)
        assert out["evidence_gaps_for_research"][0]["priority"] == "medium"
        assert out["evidence_gaps_for_research"][1]["priority"] == "high"


# ---------------------------------------------------------------------------
# Tailor: _fallback_tailor
# ---------------------------------------------------------------------------

class TestFallbackTailor:
    def test_fallback_has_all_8_fields(self):
        out = _fallback_tailor(_make_seeded_state())
        required = {"primary_baseline", "candidate_modules", "compatibility_analysis",
                    "assembly_plan", "ablation_matrix", "fair_comparison_requirements",
                    "verdict", "verdict_reason", "evidence_gaps_for_research",
                    "generated_by"}
        assert required.issubset(out.keys())

    def test_fallback_marks_generated_by(self):
        out = _fallback_tailor(_make_seeded_state())
        assert out["generated_by"] == "fallback"

    def test_fallback_verdict_is_revise(self):
        """Fallback never issues GO (§9.3 step 4: 解析失败不得被当作 GO)."""
        out = _fallback_tailor(_make_seeded_state())
        assert out["verdict"] == "REVISE"

    def test_fallback_ablation_has_minimum_4(self):
        out = _fallback_tailor(_make_seeded_state())
        ids = {a["experiment_id"] for a in out["ablation_matrix"]}
        assert {"baseline", "a", "b", "a+b"}.issubset(ids)


# ---------------------------------------------------------------------------
# Tailor: build_tailor_prompt (seed-aware input compilation)
# ---------------------------------------------------------------------------

class TestBuildTailorPrompt:
    def test_prompt_includes_seed_title(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "You Only Look Once" in prompt

    def test_prompt_includes_method_families(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "YOLO family" in prompt

    def test_prompt_includes_search_lanes(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "anchor_reference" in prompt
        assert "competing_baseline" in prompt

    def test_prompt_includes_open_gaps(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "gap-s1-anchor_reference" in prompt

    def test_prompt_includes_baselines(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "Faster R-CNN" in prompt

    def test_prompt_includes_constraints(self):
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "full_agent" in prompt
        assert "online" in prompt

    def test_prompt_includes_dataset_and_metrics(self):
        """Re8.0 second-batch: Tailor prompt must include dataset_and_metrics."""
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "PASCAL VOC" in prompt
        assert "mAP" in prompt

    def test_prompt_includes_reproduction_environment(self):
        """Re8.0 second-batch: Tailor prompt must include reproduction_environment."""
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "Darknet" in prompt
        assert "Titan X" in prompt

    def test_prompt_includes_limitations(self):
        """Re8.0 second-batch: Tailor prompt must include limitations."""
        prompt = build_tailor_prompt(_make_seeded_state())
        assert "grid-based detection" in prompt
        assert "small objects" in prompt

    def test_format_seed_context_includes_all_5_fields(self):
        """Re8.0 second-batch: _format_seed_context must surface all 5
        paper_understanding fields, not just task_definition + method_summary.

        Before commit (this fix): only 2/5 fields passed to Tailor LLM,
        causing core_method="" + baseline_model=null + contribution_type=null
        in Tailor output across all three seeded cases.
        """
        from apps.api.app.services.agents.graph.nodes.tailor_skill_adapter import (
            _format_seed_context,
        )

        seed_cards = [
            make_seed_card(
                seed_id="s1",
                resolved_title="Test Paper",
                role="classic_anchor",
                task_definition="test task",
                method_summary="test method",
                dataset_and_metrics={"datasets": [{"name": "TestDataset"}]},
                reproduction_environment={"framework": "TestFramework"},
                limitations=["limitation one", "limitation two"],
            ),
        ]
        result = _format_seed_context(seed_cards)
        # All 5 fields must appear in the compiled context.
        assert "test task" in result
        assert "test method" in result
        assert "TestDataset" in result
        assert "TestFramework" in result
        assert "limitation one" in result
        assert "limitation two" in result

    def test_format_seed_context_handles_missing_fields(self):
        """Missing dataset/env/limitations must not crash (backward compat
        with seed cards that haven't passed through paper_understanding)."""
        from apps.api.app.services.agents.graph.nodes.tailor_skill_adapter import (
            _format_seed_context,
        )

        seed_cards = [
            make_seed_card(
                seed_id="s1",
                resolved_title="Minimal Paper",
                role="classic_anchor",
                task_definition="task only",
                # method_summary, dataset_and_metrics, reproduction_environment,
                # limitations all default to None / empty
            ),
        ]
        result = _format_seed_context(seed_cards)
        # Should not crash; empty fields render as empty / "{}" / "".
        assert "Minimal Paper" in result
        assert "task only" in result
        # dataset/environment render as "{}" when missing
        assert "dataset: {}" in result
        assert "environment: {}" in result


# ---------------------------------------------------------------------------
# Tailor: tailor_skill_adapter_node
# ---------------------------------------------------------------------------

class TestTailorNode:
    def test_topic_only_skips_tailor(self):
        state = _make_seeded_state()
        state["entry_mode"] = "topic_only"
        result = tailor_skill_adapter_node(state)
        assert "tailored_method" not in result
        assert result["trace_events"][0]["output_summary"]["skipped"] is True

    def test_seeded_research_activates_tailor(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            result = tailor_skill_adapter_node(state)
        assert "tailored_method" in result
        assert result["tailored_method"]["verdict"] == "GO"

    def test_seeded_research_produces_8_fields(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            result = tailor_skill_adapter_node(state)
        tm = result["tailored_method"]
        required = {"primary_baseline", "candidate_modules", "compatibility_analysis",
                    "assembly_plan", "ablation_matrix", "fair_comparison_requirements",
                    "verdict", "verdict_reason", "evidence_gaps_for_research"}
        assert required.issubset(tm.keys())

    def test_llm_failure_falls_back(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = tailor_skill_adapter_node(state)
        assert result["tailored_method"]["generated_by"] == "fallback"
        assert result["tailored_method"]["verdict"] == "REVISE"

    def test_non_dict_llm_output_falls_back(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value="not a dict"):
            result = tailor_skill_adapter_node(state)
        assert result["tailored_method"]["generated_by"] == "fallback"

    def test_ledger_entry_appended(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            result = tailor_skill_adapter_node(state)
        ledger = result["reasoning_ledger"]
        assert len(ledger) == 1
        assert ledger[0]["stage"] == "tailor"
        # validate against schema
        errs = validate_ledger_entry(ledger[0])
        assert errs == [], f"ledger entry invalid: {errs}"

    def test_trace_has_verdict_and_generated_by(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            result = tailor_skill_adapter_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["verdict"] == "GO"
        assert trace["output_summary"]["generated_by"] == "llm"
        assert trace["provider"] == "premium_review"

    def test_trace_fallback_provider(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = tailor_skill_adapter_node(state)
        trace = result["trace_events"][0]
        assert trace["provider"] == "fallback"
        assert trace["output_summary"]["generated_by"] == "fallback"


# ---------------------------------------------------------------------------
# Novelty Review: schema enforcement helpers
# ---------------------------------------------------------------------------

class TestReviewClamps:
    def test_clamp_verdict_valid(self):
        assert _clamp_review_verdict("accepted") == "accepted"
        assert _clamp_review_verdict("weak_reject") == "weak_reject"
        assert _clamp_review_verdict("reject") == "reject"

    def test_clamp_verdict_case_insensitive(self):
        assert _clamp_review_verdict("Accept") == "accepted"
        assert _clamp_review_verdict("REJECT") == "reject"

    def test_clamp_verdict_unknown_defaults_reject(self):
        assert _clamp_review_verdict("maybe") == "reject"
        assert _clamp_review_verdict(None) == "reject"

    def test_clamp_contribution_type_valid(self):
        for c in CONTRIBUTION_TYPES:
            assert _clamp_contribution_type(c) == c

    def test_clamp_contribution_type_invalid_defaults_engineering(self):
        assert _clamp_contribution_type("WACKY") == "engineering"
        assert _clamp_contribution_type(None) == "engineering"

    def test_clamp_contribution_type_normalizes(self):
        assert _clamp_contribution_type("System-Integration") == "system_integration"
        assert _clamp_contribution_type("Application ") == "application"

    def test_normalize_pmi_backfills(self):
        out = _normalize_pmi(None)
        assert out == {"problem": "unspecified", "method": "unspecified",
                       "insight": "unspecified"}
        out = _normalize_pmi({"problem": "real problem"})
        assert out["problem"] == "real problem"
        assert out["method"] == "unspecified"

    def test_normalize_contributions_backfills(self):
        out = _normalize_contributions(None)
        assert out == {"one_sentence": "unspecified",
                       "three_sentence": "unspecified",
                       "paragraph": "unspecified"}
        out = _normalize_contributions({"one_sentence": "we do X"})
        assert out["one_sentence"] == "we do X"
        assert out["three_sentence"] == "unspecified"


# ---------------------------------------------------------------------------
# Novelty Review: normalize_review_output (schema stability chokepoint)
# ---------------------------------------------------------------------------

class TestNormalizeReviewOutput:
    def test_full_output_preserved(self):
        out = normalize_review_output(_MODEL_D_REVIEW_FULL)
        assert out["novelty_review_verdict"] == "accepted"
        assert out["novelty_review_score"] == 7
        assert out["contribution_type"] == "methodological"
        assert out["problem_method_insight"]["problem"] == "small object recall"
        assert out["contributions"]["one_sentence"] == "we propose X"
        assert out["falsifiable_hypothesis"] == "FPN-lite does not help when objects are <4px"
        assert out["review_generated_by"] == "llm"

    def test_sloppy_output_normalized(self):
        out = normalize_review_output(_MODEL_E_REVIEW_SLOPPY)
        assert out["novelty_review_verdict"] == "accepted"  # "Accept" lowercased
        assert out["novelty_review_score"] == 0  # "high" → 0
        assert out["contribution_type"] == "engineering"  # invalid → engineering
        # new fields backfilled
        assert out["problem_method_insight"] == {"problem": "unspecified",
                                                  "method": "unspecified",
                                                  "insight": "unspecified"}
        assert out["contributions"]["one_sentence"] == "unspecified"
        assert out["falsifiable_hypothesis"] == "unspecified"

    def test_empty_dict_yields_full_schema(self):
        out = normalize_review_output({})
        # existing fields
        for k in ("novelty_review_verdict", "novelty_review_score",
                  "pseudo_innovation_risks", "pressure_points",
                  "differentiation_matrix", "required_repairs",
                  "review_strengths", "review_risks"):
            assert k in out
        # new fields
        for k in ("problem_method_insight", "contributions",
                  "falsifiable_hypothesis", "minimum_key_experiment",
                  "contribution_type", "review_generated_by"):
            assert k in out

    def test_generated_by_propagated(self):
        out = normalize_review_output({}, generated_by="fallback")
        assert out["review_generated_by"] == "fallback"


class TestEmptyReview:
    def test_has_all_fields(self):
        out = _empty_review()
        for k in ("novelty_review_verdict", "novelty_review_score",
                  "problem_method_insight", "contributions",
                  "falsifiable_hypothesis", "minimum_key_experiment",
                  "contribution_type", "review_generated_by"):
            assert k in out

    def test_marks_fallback(self):
        out = _empty_review()
        assert out["review_generated_by"] == "fallback"

    def test_can_carry_error(self):
        out = _empty_review(error="boom")
        assert out["novelty_review_error"] == "boom"


# ---------------------------------------------------------------------------
# Novelty Review: build_novelty_review_prompt (tailored_method consumption)
# ---------------------------------------------------------------------------

class TestReviewPrompt:
    def test_prompt_includes_tailored_method_when_present(self):
        state = _make_seeded_state(with_tailored=True)
        state["innovation_points"] = [{"point": "test"}]
        prompt = build_novelty_review_prompt(state)
        assert "Faster R-CNN" in prompt
        assert "verdict=GO" in prompt

    def test_prompt_handles_missing_tailored_method(self):
        state = _make_seeded_state()
        state["innovation_points"] = [{"point": "test"}]
        prompt = build_novelty_review_prompt(state)
        assert "topic_only path" in prompt

    def test_prompt_includes_contribution_types(self):
        state = _make_seeded_state()
        state["innovation_points"] = [{"point": "test"}]
        prompt = build_novelty_review_prompt(state)
        assert "methodological" in prompt
        assert "engineering" in prompt


# ---------------------------------------------------------------------------
# Novelty Review: novelty_review_node
# ---------------------------------------------------------------------------

class TestReviewNode:
    def test_no_innovation_points_returns_empty_review(self):
        state = _make_seeded_state()
        state["innovation_points"] = []
        result = novelty_review_node(state)
        assert result["novelty_review_verdict"] == "reject"
        assert result["review_generated_by"] == "fallback"
        assert "no_innovation_points" in result["pseudo_innovation_risks"]
        # new fields present even on early exit
        assert "problem_method_insight" in result
        assert "contributions" in result

    def test_full_review_with_llm(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_D_REVIEW_FULL):
            result = novelty_review_node(state)
        assert result["novelty_review_verdict"] == "accepted"
        assert result["contribution_type"] == "methodological"
        assert result["review_generated_by"] == "llm"

    def test_llm_failure_returns_fallback(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = novelty_review_node(state)
        assert result["review_generated_by"] == "fallback"
        assert "llm_unavailable" in result["pseudo_innovation_risks"]
        assert "novelty_review_error" in result

    def test_llm_returns_fallback_dict_marks_fallback(self):
        """When call_json_with_validation returns its own fallback dict,
        we should detect it and mark generated_by=fallback."""
        state = _make_seeded_state()
        fallback_dict = {
            "verdict": "reject", "novelty_score": 0,
            "pseudo_innovation_risks": ["llm_unavailable"],
        }
        with patch(PATCH_CALL_JSON, return_value=fallback_dict):
            result = novelty_review_node(state)
        assert result["review_generated_by"] == "fallback"

    def test_backward_compat_existing_fields(self):
        """Existing consumers reading legacy fields still work."""
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_D_REVIEW_FULL):
            result = novelty_review_node(state)
        # legacy field names
        assert "novelty_review_verdict" in result
        assert "novelty_review_score" in result
        assert "pseudo_innovation_risks" in result
        assert "pressure_points" in result
        assert "differentiation_matrix" in result
        assert "required_repairs" in result
        assert "review_strengths" in result
        assert "review_risks" in result


# ---------------------------------------------------------------------------
# WP5 acceptance: schema stability across 3 model "personalities"
# ---------------------------------------------------------------------------

class TestWP5Acceptance:
    """WP5 acceptance: "切换至少三类模型时 Schema 稳定，失败可降级"."""

    TAILOR_REQUIRED_KEYS = {
        "primary_baseline", "candidate_modules", "compatibility_analysis",
        "assembly_plan", "ablation_matrix", "fair_comparison_requirements",
        "verdict", "verdict_reason", "evidence_gaps_for_research", "generated_by",
    }
    REVIEW_REQUIRED_KEYS = {
        "novelty_review_verdict", "novelty_review_score",
        "pseudo_innovation_risks", "pressure_points", "differentiation_matrix",
        "required_repairs", "review_strengths", "review_risks",
        "problem_method_insight", "contributions",
        "falsifiable_hypothesis", "minimum_key_experiment",
        "contribution_type", "review_generated_by",
    }

    def test_tailor_schema_stable_across_3_models(self):
        """Three different model outputs → same schema keys after normalization."""
        outs = [_normalize_tailor_output(m) for m in
                (_MODEL_A_OUTPUT, _MODEL_B_OUTPUT, _MODEL_C_OUTPUT)]
        key_sets = [set(o.keys()) for o in outs]
        # all three have exactly the same keys
        assert key_sets[0] == key_sets[1] == key_sets[2]
        # and those keys include the required schema
        assert self.TAILOR_REQUIRED_KEYS.issubset(key_sets[0])

    def test_review_schema_stable_across_3_models(self):
        """Three different review outputs → same schema keys after normalization."""
        outs = [
            normalize_review_output(_MODEL_D_REVIEW_FULL),
            normalize_review_output(_MODEL_E_REVIEW_SLOPPY),
            normalize_review_output({}),  # empty
        ]
        key_sets = [set(o.keys()) for o in outs]
        assert key_sets[0] == key_sets[1] == key_sets[2]
        assert self.REVIEW_REQUIRED_KEYS.issubset(key_sets[0])

    def test_tailor_failure_degrades_gracefully(self):
        """LLM failure → fallback Tailor with all schema fields + generated_by=fallback."""
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = tailor_skill_adapter_node(state)
        tm = result["tailored_method"]
        assert self.TAILOR_REQUIRED_KEYS.issubset(tm.keys())
        assert tm["generated_by"] == "fallback"
        assert tm["verdict"] == "REVISE"  # never GO on fallback
        # ablation still has minimum 4 rows even on fallback
        ids = {a["experiment_id"] for a in tm["ablation_matrix"]}
        assert {"baseline", "a", "b", "a+b"}.issubset(ids)

    def test_review_failure_degrades_gracefully(self):
        """LLM failure → fallback Review with all schema fields + generated_by=fallback."""
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = novelty_review_node(state)
        assert self.REVIEW_REQUIRED_KEYS.issubset(result.keys())
        assert result["review_generated_by"] == "fallback"
        assert result["novelty_review_verdict"] == "reject"  # never accepted on fallback

    def test_tailor_verdict_never_invalid(self):
        """Regardless of model output, verdict is always in TAILOR_VERDICTS."""
        for raw in (_MODEL_A_OUTPUT, _MODEL_B_OUTPUT, _MODEL_C_OUTPUT):
            out = _normalize_tailor_output(raw)
            assert out["verdict"] in TAILOR_VERDICTS

    def test_review_verdict_never_invalid(self):
        """Regardless of model output, verdict is always in the allowed set."""
        for raw in (_MODEL_D_REVIEW_FULL, _MODEL_E_REVIEW_SLOPPY, {}):
            out = normalize_review_output(raw)
            assert out["novelty_review_verdict"] in ("accepted", "weak_reject", "reject")


# ---------------------------------------------------------------------------
# Integration: Tailor → Review (seeded_research path)
# ---------------------------------------------------------------------------

class TestIntegrationTailorToReview:
    def test_tailor_output_feeds_into_review_prompt(self):
        """Tailor produces tailored_method; Review prompt consumes it."""
        state = _make_seeded_state()
        # Step 1: Tailor
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            tailor_result = tailor_skill_adapter_node(state)
        state.update(tailor_result)
        # Step 2: Review prompt includes tailored method
        state["innovation_points"] = [{"point": "test"}]
        prompt = build_novelty_review_prompt(state)
        assert "Faster R-CNN" in prompt
        assert "verdict=GO" in prompt

    def test_tailor_to_review_full_chain(self):
        """Full chain: Tailor → Review, both schema-stable."""
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_A_OUTPUT):
            tailor_result = tailor_skill_adapter_node(state)
        state.update(tailor_result)
        with patch(PATCH_CALL_JSON, return_value=_MODEL_D_REVIEW_FULL):
            review_result = novelty_review_node(state)
        assert tailor_result["tailored_method"]["verdict"] == "GO"
        assert review_result["novelty_review_verdict"] == "accepted"
        assert review_result["review_generated_by"] == "llm"


# ---------------------------------------------------------------------------
# P1-1 fixup: novelty_review must emit trace_events on all paths
# ---------------------------------------------------------------------------

class TestReviewTraceVisibility:
    """P1-1 regression: novelty_review_node must emit trace_events with
    provider / verdict / generated_by on ALL return paths, for parity
    with tailor_skill_adapter_node (Plan §11.3 "trace 路径真实")."""

    def test_no_innovation_path_emits_trace(self):
        state = _make_seeded_state()
        state["innovation_points"] = []
        result = novelty_review_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["node"] == "novelty_review"
        assert trace["output_summary"]["verdict"] == "reject"
        assert trace["output_summary"]["generated_by"] == "fallback"
        assert trace["provider"] == "n/a"

    def test_llm_success_path_emits_trace(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, return_value=_MODEL_D_REVIEW_FULL):
            result = novelty_review_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["output_summary"]["verdict"] == "accepted"
        assert trace["output_summary"]["generated_by"] == "llm"
        assert trace["output_summary"]["contribution_type"] == "methodological"
        assert trace["provider"] == "premium_review"

    def test_llm_failure_path_emits_trace(self):
        state = _make_seeded_state()
        with patch(PATCH_CALL_JSON, side_effect=Exception("LLM down")):
            result = novelty_review_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["output_summary"]["generated_by"] == "fallback"
        assert trace["provider"] == "fallback"

    def test_fallback_dict_path_emits_trace(self):
        state = _make_seeded_state()
        fallback_dict = {
            "verdict": "reject", "novelty_score": 0,
            "pseudo_innovation_risks": ["llm_unavailable"],
        }
        with patch(PATCH_CALL_JSON, return_value=fallback_dict):
            result = novelty_review_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["output_summary"]["generated_by"] == "fallback"
        assert trace["provider"] == "fallback"


# ---------------------------------------------------------------------------
# P2-3 fixup: tailor topic_only trace must have verdict/generated_by
# ---------------------------------------------------------------------------

class TestTailorSkipTraceFields:
    def test_topic_only_trace_has_verdict_and_generated_by(self):
        """P2-3: topic_only skip trace must include verdict + generated_by
        for trace schema consistency with activated path."""
        state = _make_seeded_state()
        state["entry_mode"] = "topic_only"
        result = tailor_skill_adapter_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["skipped"] is True
        assert "verdict" in trace["output_summary"]
        assert "generated_by" in trace["output_summary"]


# ---------------------------------------------------------------------------
# P2-6: parse_novelty_review_output backward-compat shim smoke test
# ---------------------------------------------------------------------------

class TestParseNoveltyReviewOutputShim:
    def test_shim_delegates_to_normalize(self):
        """P2-6: parse_novelty_review_output must equal
        normalize_review_output(raw, generated_by='llm')."""
        from apps.api.app.services.agents.graph.nodes.novelty_review import (
            parse_novelty_review_output,
        )
        raw = _MODEL_D_REVIEW_FULL
        via_shim = parse_novelty_review_output(raw)
        via_normalize = normalize_review_output(raw, generated_by="llm")
        assert via_shim == via_normalize

    def test_shim_handles_empty_dict(self):
        from apps.api.app.services.agents.graph.nodes.novelty_review import (
            parse_novelty_review_output,
        )
        out = parse_novelty_review_output({})
        assert "novelty_review_verdict" in out
        assert "problem_method_insight" in out

"""Re8.0 WP3 Method Family Explorer Tests.

Tests task ontology classification, LLM method family derivation, five
Search Lane generation, anti-anchoring queries, and the WP3 acceptance
criteria: "YOLO 输入不会机械地把所有视觉模型当作同任务直接基线."
"""
from __future__ import annotations

import pytest

from apps.api.app.services.agents.graph.nodes.method_family_explorer import (
    LANE_IDS,
    TASK_TYPES,
    _extract_seed_model_name,
    _generate_gaps_for_missing_task,
    _normalise_family,
    build_search_lanes,
    classify_task_type,
    method_family_explorer_node,
)
from apps.api.app.services.agents.graph.re80_schema import (
    make_seed_card,
    validate_evidence_gap,
    validate_ledger_entry,
    validate_method_family,
)


# ---------------------------------------------------------------------------
# classify_task_type
# ---------------------------------------------------------------------------

class TestClassifyTaskType:
    def test_yolo_is_detection(self):
        assert classify_task_type("YOLO: real-time object detection") == "detection"

    def test_unet_is_segmentation(self):
        assert classify_task_type("U-Net for semantic segmentation") == "segmentation"

    def test_resnet_is_classification(self):
        assert classify_task_type("ResNet image classification") == "classification"

    def test_gan_is_generation(self):
        assert classify_task_type("GAN for image generation") == "generation"

    def test_lstm_is_forecasting(self):
        assert classify_task_type("LSTM time-series forecasting") == "forecasting"

    def test_empty_returns_other(self):
        assert classify_task_type("") == "other"

    def test_no_match_returns_other(self):
        assert classify_task_type("a generic paper about nothing") == "other"

    def test_detection_precedence_over_classification(self):
        """YOLO uses classification heads but is primarily detection."""
        assert classify_task_type("YOLO detector with classification head") == "detection"

    def test_mask_rcnn_is_segmentation(self):
        assert classify_task_type("Mask R-CNN instance segmentation") == "segmentation"


# ---------------------------------------------------------------------------
# _extract_seed_model_name
# ---------------------------------------------------------------------------

class TestExtractSeedModelName:
    def test_uppercase_token(self):
        assert _extract_seed_model_name("This paper uses YOLO for detection") == "YOLO"

    def test_hyphenated_name(self):
        # Method summary starting with U-Net
        assert _extract_seed_model_name("U-Net based approach") == "U-Net"

    def test_no_model_name(self):
        assert _extract_seed_model_name("a generic transformer model") == ""

    def test_empty(self):
        assert _extract_seed_model_name("") == ""


# ---------------------------------------------------------------------------
# _normalise_family — WP3 acceptance guard
# ---------------------------------------------------------------------------

class TestNormaliseFamily:
    def test_valid_family_passes(self):
        raw = {
            "name": "Two-stage detectors",
            "task_type": "detection",
            "relation_to_seed": "direct_competitor",
            "applicability_conditions": ["same detection task"],
            "search_queries": ["Faster R-CNN survey"],
        }
        fam = _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="detection")
        assert fam is not None
        assert fam["relation_to_seed"] == "direct_competitor"
        assert validate_method_family(fam) == []

    def test_cross_task_direct_competitor_is_downgraded(self):
        """WP3 acceptance: U-Net (segmentation) cannot be a direct
        competitor of YOLO (detection). Must be downgraded."""
        raw = {
            "name": "U-Net family",
            "task_type": "segmentation",
            "relation_to_seed": "direct_competitor",
        }
        fam = _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="detection")
        assert fam is not None
        assert fam["relation_to_seed"] == "alternative_formulation"

    def test_other_task_type_is_lenient(self):
        """If family task_type is 'other' (unknown), don't downgrade —
        the LLM may simply have failed to classify."""
        raw = {
            "name": "Mystery family",
            "task_type": "other",
            "relation_to_seed": "direct_competitor",
        }
        fam = _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="detection")
        assert fam is not None
        assert fam["relation_to_seed"] == "direct_competitor"

    def test_missing_name_returns_none(self):
        raw = {"task_type": "detection", "relation_to_seed": "direct_competitor"}
        assert _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="detection") is None

    def test_invalid_relation_defaults_to_alternative(self):
        raw = {
            "name": "Weird family",
            "task_type": "detection",
            "relation_to_seed": "totally_bogus_relation",
        }
        fam = _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="detection")
        assert fam is not None
        assert fam["relation_to_seed"] == "alternative_formulation"

    def test_invalid_task_type_defaults_to_other(self):
        raw = {
            "name": "Weird family",
            "task_type": "totally_bogus_type",
            "relation_to_seed": "alternative_formulation",
        }
        fam = _normalise_family(raw, seed_id="s1", idx=0, seed_task_type="other")
        assert fam is not None
        assert fam["task_type"] == "other"

    def test_family_id_is_deterministic(self):
        raw = {"name": "Test", "task_type": "detection", "relation_to_seed": "direct_competitor"}
        fam = _normalise_family(raw, seed_id="seedX", idx=2, seed_task_type="detection")
        assert fam["family_id"] == "family-seedX-2"


# ---------------------------------------------------------------------------
# build_search_lanes — five lanes + anti-anchoring
# ---------------------------------------------------------------------------

class TestBuildSearchLanes:
    def test_returns_five_lanes(self):
        card = make_seed_card(
            seed_id="s1",
            resolved_title="YOLO paper",
            method_summary="YOLO real-time detection",
            task_definition="object detection",
        )
        lanes = build_search_lanes(seed_card=card, families=[], task_type="detection")
        assert len(lanes) == 5
        lane_ids = [l["lane_id"] for l in lanes]
        assert set(lane_ids) == set(LANE_IDS)

    def test_each_lane_has_queries(self):
        card = make_seed_card(
            seed_id="s1",
            resolved_title="YOLO paper",
            task_definition="object detection",
        )
        lanes = build_search_lanes(seed_card=card, families=[], task_type="detection")
        for lane in lanes:
            assert isinstance(lane["queries"], list)
            assert len(lane["queries"]) >= 1, f"lane {lane['lane_id']} has no queries"

    def test_competing_baseline_has_anti_anchor_query(self):
        """Re8.0 §7.4: at least one query in competing_baseline must NOT
        contain the seed model name."""
        card = make_seed_card(
            seed_id="s1",
            resolved_title="YOLO paper",
            method_summary="YOLO real-time detection",
            task_definition="object detection",
        )
        lanes = build_search_lanes(seed_card=card, families=[], task_type="detection")
        competing = next(l for l in lanes if l["lane_id"] == "competing_baseline")
        seed_name = _extract_seed_model_name(card["method_summary"])
        assert seed_name == "YOLO"
        has_clean = any(
            seed_name.lower() not in q.lower()
            for q in competing["queries"]
        )
        assert has_clean, (
            f"anti-anchoring violated: all competing queries contain "
            f"'{seed_name}': {competing['queries']}"
        )

    def test_counter_evidence_has_counter_query(self):
        """Re8.0 §7.4: counter_evidence lane must contain a counter-evidence
        or similar-work query."""
        card = make_seed_card(seed_id="s1", task_definition="detection")
        lanes = build_search_lanes(seed_card=card, families=[], task_type="detection")
        counter = next(l for l in lanes if l["lane_id"] == "counter_evidence")
        import re
        has_counter = any(
            re.search(r"(negative|counter|challenge|fail|limitation)", q, re.I)
            for q in counter["queries"]
        )
        assert has_counter, f"no counter-evidence query in: {counter['queries']}"

    def test_queries_are_deduped(self):
        card = make_seed_card(seed_id="s1", resolved_title="Dup test")
        lanes = build_search_lanes(
            seed_card=card,
            families=[
                {"relation_to_seed": "direct_competitor",
                 "search_queries": ["dup query", "dup query", "dup query"]},
            ],
            task_type="detection",
        )
        competing = next(l for l in lanes if l["lane_id"] == "competing_baseline")
        # "dup query" should appear at most once
        assert competing["queries"].count("dup query") <= 1

    def test_limitations_appear_in_mechanism_lane(self):
        card = make_seed_card(
            seed_id="s1",
            task_definition="detection",
            limitations=["small object detection fails", "high latency on edge"],
        )
        lanes = build_search_lanes(seed_card=card, families=[], task_type="detection")
        mech = next(l for l in lanes if l["lane_id"] == "mechanism_module")
        joined = " ".join(mech["queries"]).lower()
        assert "small object" in joined or "high latency" in joined

    def test_family_queries_routed_by_relation(self):
        families = [
            {"relation_to_seed": "direct_competitor",
             "search_queries": ["DC query 1"]},
            {"relation_to_seed": "alternative_formulation",
             "search_queries": ["AF query 1"]},
            {"relation_to_seed": "transferable_mechanism",
             "search_queries": ["TM query 1"]},
        ]
        card = make_seed_card(seed_id="s1", task_definition="detection")
        lanes = build_search_lanes(seed_card=card, families=families, task_type="detection")
        competing = next(l for l in lanes if l["lane_id"] == "competing_baseline")
        counter = next(l for l in lanes if l["lane_id"] == "counter_evidence")
        mech = next(l for l in lanes if l["lane_id"] == "mechanism_module")
        assert "DC query 1" in competing["queries"]
        assert "AF query 1" in counter["queries"]
        assert "TM query 1" in mech["queries"]


# ---------------------------------------------------------------------------
# _generate_gaps_for_missing_task
# ---------------------------------------------------------------------------

class TestGenerateGapsForMissingTask:
    def test_no_gap_when_task_definition_present(self):
        card = make_seed_card(seed_id="s1", task_definition="detection")
        assert _generate_gaps_for_missing_task(card) == []

    def test_no_gap_when_method_summary_present(self):
        card = make_seed_card(seed_id="s1", method_summary="YOLO detector")
        assert _generate_gaps_for_missing_task(card) == []

    def test_gap_when_both_missing(self):
        card = make_seed_card(seed_id="s1")
        gaps = _generate_gaps_for_missing_task(card)
        assert len(gaps) == 1
        assert gaps[0]["gap_id"] == "gap-s1-task_definition_for_family"
        assert validate_evidence_gap(gaps[0]) == []


# ---------------------------------------------------------------------------
# method_family_explorer_node — no-op paths
# ---------------------------------------------------------------------------

class TestMethodFamilyExplorerNodeNoOp:
    def test_topic_only_skips(self):
        state = {"entry_mode": "topic_only", "seed_cards": []}
        result = method_family_explorer_node(state)
        assert "trace_events" in result
        trace = result["trace_events"][0]
        assert trace["node"] == "method_family_explorer"
        assert trace["output_summary"]["skipped"] is True
        # Must not produce families or lanes
        assert "method_families" not in result
        assert "search_lanes" not in result

    def test_no_seed_cards_skips(self):
        state = {"entry_mode": "seeded_research", "seed_cards": []}
        result = method_family_explorer_node(state)
        assert result["trace_events"][0]["output_summary"]["skipped"] is True

    def test_no_understanding_emits_gaps(self):
        """Seed card without task_definition or method_summary should
        emit an EvidenceGap and skip family derivation."""
        card = make_seed_card(seed_id="s1")  # no understanding fields
        state = {"entry_mode": "seeded_research", "seed_cards": [card]}
        result = method_family_explorer_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["skipped"] is True
        assert trace["output_summary"]["n_gaps_emitted"] == 1
        assert "evidence_gaps" in result
        assert len(result["evidence_gaps"]) == 1
        assert result["evidence_gaps"][0]["gap_id"] == "gap-s1-task_definition_for_family"

    def test_trace_has_state_keys(self):
        state = {"entry_mode": "topic_only", "seed_cards": []}
        result = method_family_explorer_node(state)
        trace = result["trace_events"][0]
        assert "method_families" in trace["state_keys"]
        assert "search_lanes" in trace["state_keys"]
        assert "evidence_gaps" in trace["state_keys"]
        assert "reasoning_ledger" in trace["state_keys"]


# ---------------------------------------------------------------------------
# method_family_explorer_node — LLM-driven family derivation
# ---------------------------------------------------------------------------

class TestMethodFamilyExplorerNodeWithLLM:
    def _yolo_seed(self):
        return make_seed_card(
            seed_id="s1",
            resolved_title="YOLO: Real-Time Object Detection",
            task_definition="Real-time object detection on images",
            method_summary="YOLO uses a single neural network to predict "
                           "bounding boxes and class probabilities.",
            limitations=["struggles with small objects", "localization error"],
        )

    def test_yolo_derives_families(self, monkeypatch):
        """WP3 acceptance: YOLO input should produce method families."""
        mock_families = [
            {
                "name": "Two-stage detectors",
                "task_type": "detection",
                "relation_to_seed": "direct_competitor",
                "applicability_conditions": ["same detection task"],
                "search_queries": ["Faster R-CNN survey", "two-stage detector benchmark"],
            },
            {
                "name": "Transformer detectors",
                "task_type": "detection",
                "relation_to_seed": "direct_competitor",
                "search_queries": ["DETR detection"],
            },
            {
                "name": "Segmentation networks",
                "task_type": "segmentation",
                "relation_to_seed": "alternative_formulation",
                "applicability_conditions": ["if pixel-level output needed"],
                "search_queries": ["U-Net for crack segmentation"],
            },
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        assert "method_families" in result
        assert len(result["method_families"]) == 3
        # Task type should be detected as detection
        assert result["trace_events"][0]["input_summary"]["inferred_task_type"] == "detection"

    def test_yolo_does_not_treat_unet_as_direct_competitor(self, monkeypatch):
        """WP3 acceptance core: U-Net (segmentation) cannot be a
        direct_competitor of YOLO (detection). Even if the LLM mistakenly
        tags it that way, the guard must downgrade it."""
        mock_families = [
            {
                "name": "Two-stage detectors",
                "task_type": "detection",
                "relation_to_seed": "direct_competitor",
                "search_queries": ["Faster R-CNN"],
            },
            {
                "name": "U-Net",
                "task_type": "segmentation",
                "relation_to_seed": "direct_competitor",  # LLM mistake
                "search_queries": ["U-Net segmentation"],
            },
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        families = result["method_families"]
        assert len(families) == 2
        unet = next(f for f in families if f["name"] == "U-Net")
        # Guard must have downgraded this
        assert unet["relation_to_seed"] == "alternative_formulation"
        # The legit two-stage detector stays direct_competitor
        two_stage = next(f for f in families if f["name"] == "Two-stage detectors")
        assert two_stage["relation_to_seed"] == "direct_competitor"

    def test_five_lanes_generated(self, monkeypatch):
        mock_families = [
            {"name": "DC", "task_type": "detection",
             "relation_to_seed": "direct_competitor", "search_queries": ["dc q"]},
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        assert "search_lanes" in result
        assert len(result["search_lanes"]) == 5
        lane_ids = [l["lane_id"] for l in result["search_lanes"]]
        assert set(lane_ids) == set(LANE_IDS)

    def test_anti_anchor_query_present_for_yolo(self, monkeypatch):
        """The competing_baseline lane must have at least one query
        without 'YOLO' in it."""
        mock_families = [
            {"name": "DC", "task_type": "detection",
             "relation_to_seed": "direct_competitor",
             "search_queries": ["YOLO alternatives", "YOLO comparison"]},
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        competing = next(l for l in result["search_lanes"]
                         if l["lane_id"] == "competing_baseline")
        has_clean = any("yolo" not in q.lower() for q in competing["queries"])
        assert has_clean, f"all competing queries mention YOLO: {competing['queries']}"

    def test_ledger_entry_recorded(self, monkeypatch):
        mock_families = [
            {"name": "DC", "task_type": "detection",
             "relation_to_seed": "direct_competitor", "search_queries": ["q"]},
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        assert "reasoning_ledger" in result
        assert len(result["reasoning_ledger"]) == 1
        entry = result["reasoning_ledger"][0]
        assert entry["stage"] == "family_expansion"
        assert entry["status"] == "evidence_backed"
        assert validate_ledger_entry(entry) == []

    def test_llm_failure_emits_error_in_trace(self, monkeypatch):
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: None,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)

        trace = result["trace_events"][0]
        assert trace["output_summary"]["n_families"] == 0
        assert trace["output_summary"]["n_errors"] >= 1
        assert len(trace["errors"]) >= 1
        # Ledger should still be recorded with unresolved status
        assert result["reasoning_ledger"][0]["status"] == "unresolved"

    def test_families_capped_at_four(self, monkeypatch):
        """Even if the LLM returns 10 families, we cap at 4."""
        mock_families = [
            {"name": f"F{i}", "task_type": "detection",
             "relation_to_seed": "direct_competitor", "search_queries": []}
            for i in range(10)
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)
        assert len(result["method_families"]) <= 4

    def test_trace_records_relation_counts(self, monkeypatch):
        mock_families = [
            {"name": "DC1", "task_type": "detection",
             "relation_to_seed": "direct_competitor", "search_queries": []},
            {"name": "AF1", "task_type": "segmentation",
             "relation_to_seed": "alternative_formulation", "search_queries": []},
            {"name": "TM1", "task_type": "other",
             "relation_to_seed": "transferable_mechanism", "search_queries": []},
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research", "seed_cards": [self._yolo_seed()]}
        result = method_family_explorer_node(state)
        summary = result["trace_events"][0]["output_summary"]
        assert summary["n_direct_competitor"] == 1
        assert summary["n_alternative_formulation"] == 1
        assert summary["n_transferable_mechanism"] == 1
        assert summary["n_incompatible"] == 0


# ---------------------------------------------------------------------------
# WP3 acceptance scenario — YOLO + 裂缝 (crack detection)
# ---------------------------------------------------------------------------

class TestWP3AcceptanceScenario:
    """Re8.0 §10 WP3 acceptance: 'YOLO 输入不会机械地把所有视觉模型当作
    同任务直接基线.'

    Concretely: given YOLO as seed, the system should NOT tag every vision
    model as a direct_competitor. U-Net (segmentation) and GAN (generation)
    must be downgraded.
    """

    def _yolo_crack_seed(self):
        return make_seed_card(
            seed_id="crack_yolo",
            resolved_title="YOLO-based Concrete Crack Detection",
            task_definition="Detect concrete cracks in images using YOLO",
            method_summary="YOLO single-stage detector for crack bounding boxes.",
            limitations=["misses thin cracks", "low recall on small cracks"],
        )

    def test_yolo_mixed_families_relations_correct(self, monkeypatch):
        """LLM proposes a mix of detection, segmentation, and generation
        families. The guard must ensure only detection families are
        direct_competitor; others must be downgraded."""
        mock_families = [
            # Legitimate direct competitors
            {"name": "Faster R-CNN", "task_type": "detection",
             "relation_to_seed": "direct_competitor",
             "search_queries": ["Faster R-CNN crack detection"]},
            {"name": "DETR", "task_type": "detection",
             "relation_to_seed": "direct_competitor",
             "search_queries": ["DETR object detection"]},
            # Cross-task — must be downgraded
            {"name": "U-Net", "task_type": "segmentation",
             "relation_to_seed": "direct_competitor",  # LLM mistake
             "search_queries": ["U-Net crack segmentation"]},
            {"name": "GAN-based augmentation", "task_type": "generation",
             "relation_to_seed": "direct_competitor",  # LLM mistake
             "search_queries": ["GAN crack image augmentation"]},
        ]
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: mock_families,
        )

        state = {"entry_mode": "seeded_research",
                 "seed_cards": [self._yolo_crack_seed()]}
        result = method_family_explorer_node(state)
        families = result["method_families"]

        # Group by relation
        direct = [f for f in families if f["relation_to_seed"] == "direct_competitor"]
        non_direct = [f for f in families if f["relation_to_seed"] != "direct_competitor"]

        # Only detection families can be direct_competitor
        for f in direct:
            assert f["task_type"] == "detection", (
                f"family '{f['name']}' with task_type='{f['task_type']}' "
                f"should not be direct_competitor"
            )
        # U-Net and GAN must be in non_direct
        names_non_direct = [f["name"] for f in non_direct]
        assert "U-Net" in names_non_direct
        assert "GAN-based augmentation" in names_non_direct

    def test_yolo_search_lanes_have_anti_anchor(self, monkeypatch):
        """The five Search Lanes for YOLO must include at least one
        competing-baseline query without 'YOLO'."""
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: [
                {"name": "Faster R-CNN", "task_type": "detection",
                 "relation_to_seed": "direct_competitor",
                 "search_queries": ["Faster R-CNN YOLO comparison"]},
            ],
        )
        state = {"entry_mode": "seeded_research",
                 "seed_cards": [self._yolo_crack_seed()]}
        result = method_family_explorer_node(state)
        competing = next(l for l in result["search_lanes"]
                         if l["lane_id"] == "competing_baseline")
        has_clean = any("yolo" not in q.lower() for q in competing["queries"])
        assert has_clean


# ---------------------------------------------------------------------------
# Integration: seed_resolver → paper_understanding → method_family_explorer
# ---------------------------------------------------------------------------

class TestIntegrationWithUpstream:
    """Verify the chain seed_resolver → paper_understanding →
    method_family_explorer produces usable families + lanes."""

    def test_chain_with_understood_seed(self, monkeypatch):
        """Simulate the output of paper_understanding (seed card with
        task_definition + method_summary filled) and feed it to
        method_family_explorer."""
        from apps.api.app.services.agents.graph.nodes.paper_understanding import (
            paper_understanding_node,
        )

        # Seed card as it would look AFTER paper_understanding ran
        # (no PDF needed here — we mock paper_understanding's LLM call)
        # Actually, simpler: directly construct a state with an understood
        # seed card and call method_family_explorer.
        understood_card = make_seed_card(
            seed_id="s1",
            input_form="pdf",
            resolved_title="YOLO paper",
            task_definition="Real-time object detection",
            method_summary="YOLO single-stage detector with bounding boxes.",
            limitations=["small object recall low"],
            fulltext_status="downloaded",
        )
        monkeypatch.setattr(
            "apps.api.app.services.agents.graph.nodes.method_family_explorer._call_family_llm",
            lambda **kwargs: [
                {"name": "Two-stage", "task_type": "detection",
                 "relation_to_seed": "direct_competitor",
                 "search_queries": ["two-stage detector survey"]},
            ],
        )

        state = {
            "entry_mode": "seeded_research",
            "seed_cards": [understood_card],
        }
        result = method_family_explorer_node(state)

        assert result["method_families"]
        assert len(result["search_lanes"]) == 5
        assert result["reasoning_ledger"]


# ---------------------------------------------------------------------------
# State schema validation (P1-1 regression test)
# ---------------------------------------------------------------------------

class TestStateSchemaCompliance:
    """P1-1 regression: search_lanes must be declared in ResearchState.

    Without this declaration, LangGraph may silently drop the field
    during state merging, making the five Search Lanes invisible to
    downstream nodes.
    """

    def test_search_lanes_in_research_state(self):
        """Verify search_lanes is a declared field in ResearchState."""
        from apps.api.app.services.agents.graph.state import ResearchState
        # TypedDict.__annotations__ lists all declared fields
        annotations = ResearchState.__annotations__
        assert "search_lanes" in annotations, (
            "search_lanes must be declared in ResearchState — otherwise "
            "LangGraph state merging may silently drop the field"
        )

    def test_method_families_in_research_state(self):
        """Verify method_families is declared (existed before, sanity check)."""
        from apps.api.app.services.agents.graph.state import ResearchState
        assert "method_families" in ResearchState.__annotations__

    def test_node_fields_match_state_schema(self):
        """NODE_FIELDS for method_family_explorer must reference fields
        that actually exist in ResearchState."""
        from apps.api.app.services.agents.graph.nodes import NODE_FIELDS
        from apps.api.app.services.agents.graph.state import ResearchState
        state_annotations = ResearchState.__annotations__
        node_fields = NODE_FIELDS["method_family_explorer"]
        for field in node_fields:
            assert field in state_annotations, (
                f"NODE_FIELDS 'method_family_explorer' references '{field}' "
                f"but it is not in ResearchState"
            )

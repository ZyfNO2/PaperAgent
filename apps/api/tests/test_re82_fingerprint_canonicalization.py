"""Re8.2 fingerprint v2 canonicalization tests."""
from __future__ import annotations

import copy

from apps.api.app.services.agents.graph.nodes.reflection_gate_reuse import (
    tailor_gate_input_fingerprint,
    tailor_gate_input_projection,
)


def _state():
    return {
        "tailored_method": {
            "primary_baseline": {"baseline_id": "b1", "title": "Baseline"},
            "candidate_modules": [
                {"module_id": "m2", "name": "B", "source_evidence_id": "e2"},
                {"module_id": "m1", "name": "A", "source_evidence_id": "e1"},
            ],
            "compatibility_analysis": [
                {"module_id": "m2", "semantic": "partial", "interface": "late"},
                {"module_id": "m1", "semantic": "compatible", "interface": "mid"},
            ],
            "assembly_plan": {
                "description": "A plus B",
                "steps": ["prepare", "train", "evaluate"],
                "expected_interfaces": ["late", "mid"],
                "connections": ["late", "mid"],
            },
            "ablation_matrix": [
                {"experiment_id": "a+b"},
                {"experiment_id": "baseline"},
                {"experiment_id": "b"},
                {"experiment_id": "a"},
            ],
            "fair_comparison_requirements": ["same split", "same budget"],
            "limitations": ["limited compute", "single dataset"],
            "validation_warnings": [
                {"code": "W2", "message": "second"},
                {"code": "W1", "message": "first"},
            ],
            "evidence_gaps_for_research": [
                {"gap_id": "g2", "priority": "low", "description": "B evidence"},
                {"gap_id": "g1", "priority": "high", "description": "A evidence"},
            ],
            "generated_by": "llm",
            "verdict": "GO",
        },
        "evidence_gaps": [],
        "seed_cards": [],
    }


def test_all_set_like_tailor_collections_are_order_insensitive():
    state = _state()
    before = tailor_gate_input_fingerprint(state)
    changed = copy.deepcopy(state)
    tailored = changed["tailored_method"]
    tailored["candidate_modules"].reverse()
    tailored["compatibility_analysis"].reverse()
    tailored["assembly_plan"]["expected_interfaces"].reverse()
    tailored["assembly_plan"]["connections"].reverse()
    tailored["ablation_matrix"].reverse()
    tailored["fair_comparison_requirements"].reverse()
    tailored["limitations"].reverse()
    tailored["validation_warnings"].reverse()
    tailored["evidence_gaps_for_research"].reverse()
    assert before == tailor_gate_input_fingerprint(changed)


def test_ordered_assembly_steps_remain_semantic():
    state = _state()
    changed = copy.deepcopy(state)
    changed["tailored_method"]["assembly_plan"]["steps"].reverse()
    assert tailor_gate_input_fingerprint(state) != tailor_gate_input_fingerprint(changed)


def test_provider_generation_mode_is_operational_not_semantic():
    state = _state()
    changed = copy.deepcopy(state)
    changed["tailored_method"]["generated_by"] = "fallback"
    assert tailor_gate_input_fingerprint(state) == tailor_gate_input_fingerprint(changed)


def test_compatibility_content_change_still_changes_fingerprint():
    state = _state()
    changed = copy.deepcopy(state)
    changed["tailored_method"]["compatibility_analysis"][0]["semantic"] = "incompatible"
    assert tailor_gate_input_fingerprint(state) != tailor_gate_input_fingerprint(changed)


def test_projection_version_is_v2():
    projection = tailor_gate_input_projection(_state())
    assert projection["schema"] == "re8.2-tailor-gate-fingerprint/v2"

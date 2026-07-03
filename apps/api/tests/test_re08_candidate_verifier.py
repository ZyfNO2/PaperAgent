"""Re08 — smoke tests for CandidateVerifier + GapRepairPlanner.

These tests run offline (no LLM, no network).  They verify the rule
layer produces stable verdicts on tiny hand-rolled candidates and that
the gap_repair planner produces 1-3 targeted queries per gap reason.
"""
from __future__ import annotations

import pytest


def test_verifier_marks_direct_when_axis_matches():
    from app.services.agents.candidate_verifier import verify_candidate_offline

    cand = {
        "candidate_id": "c1",
        "title": "Concrete Pavement Crack Detection using CNN",
        "abstract": "This paper applies deep learning to crack detection on concrete pavement.",
        "url": "https://arxiv.org/abs/1234.5678",
    }
    atoms = {
        "task": [{"en": "crack detection", "aliases": ["defect detection"]}],
        "object": [{"en": "concrete pavement crack", "aliases": ["road crack"]}],
        "method": [{"en": "deep learning", "aliases": ["CNN"]}],
        "scenario": [],
    }
    r = verify_candidate_offline(cand, atoms, role="baseline")
    assert r.verification_status in {"verified", "weak_metadata"}
    assert r.topic_relation == "direct"
    assert any("crack" in m.lower() for m in r.matched_keywords)


def test_verifier_marks_metadata_mismatch_when_sim_low():
    from app.services.agents.candidate_verifier import verify_candidate_offline

    cand = {
        "candidate_id": "c2",
        "title": "Concrete Pavement Crack Detection",
        "abstract": "We study masonry walls and brick textures in 19th century buildings.",
        "url": "https://doi.org/10.1234/xyz",
    }
    atoms = {
        "task": [{"en": "crack detection"}],
        "object": [{"en": "concrete pavement crack"}],
        "method": [],
        "scenario": [],
    }
    r = verify_candidate_offline(cand, atoms, role="baseline")
    assert r.verification_status == "metadata_mismatch"
    assert "stitched" in r.reason.lower() or "overlap" in r.reason.lower()


def test_verifier_marks_foundation_for_backbone():
    from app.services.agents.candidate_verifier import verify_candidate_offline

    cand = {
        "candidate_id": "c3",
        "title": "YOLOv8: Real-time Object Detection",
        "abstract": "Generic YOLO architecture.",
        "url": "https://github.com/ultralytics/ultralytics",
    }
    atoms = {
        "task": [{"en": "crack detection"}],
        "object": [{"en": "concrete pavement crack"}],
        "method": [],
        "scenario": [],
    }
    r = verify_candidate_offline(cand, atoms, role="baseline")
    assert r.topic_relation == "foundation"


def test_verifier_marks_not_found_when_empty():
    from app.services.agents.candidate_verifier import verify_candidate_offline

    r = verify_candidate_offline({}, {}, role="baseline")
    assert r.verification_status == "not_found"


def test_gap_repair_plan_emits_queries_per_gap():
    from app.services.agents.gap_repair_planner import rule_repair_plan

    atoms = {
        "task": [{"en": "crack detection"}],
        "object": [{"en": "concrete pavement crack"}],
        "method": [{"en": "deep learning"}],
        "scenario": [{"en": "highway"}],
    }
    plan, _unmatched, _dropped = rule_repair_plan(
        ["no_dataset_or_data_gap_note", "core_n=1_but_no_effective_core"],
        atoms,
    )
    assert len(plan) == 2
    for entry in plan:
        assert 1 <= len(entry["queries"]) <= 3
        for q in entry["queries"]:
            assert q["query"]
            assert q["tool"]


def test_gap_repair_plan_handles_unknown_gap():
    from app.services.agents.gap_repair_planner import rule_repair_plan

    plan, _unmatched, _dropped = rule_repair_plan(["this_is_an_unknown_gap_xyz"], {})
    assert plan == []


def test_gap_repair_plan_query_substitution():
    from app.services.agents.gap_repair_planner import (
        _build_query, rule_repair_plan,
    )
    atoms = {
        "task": [{"en": "crack detection"}],
        "object": [{"en": "concrete pavement crack"}],
        "method": [{"en": "deep learning"}],
        "scenario": [{"en": "highway"}],
    }
    out = _build_query("{object} {scenario} dataset", atoms)
    assert "concrete pavement crack" in out
    assert "highway" in out


def test_eval_compute_resource_status_returns_re08_fields():
    """Smoke test the Re08 verification_*_n fields are present."""
    from app.services.agents.eval import compute_resource_status
    raw = {
        "title": "test",
        "raw_topic": "test",
        "candidate_pool": {"paper": [], "dataset": [], "repo": []},
        "synthesis": {"paper_groups": {}, "candidate_pool": {}},
        "evidence_review": [],
    }
    st = compute_resource_status(raw)
    for k in (
        "verification_verified_n",
        "verification_repaired_n",
        "verification_quarantined_n",
        "verification_not_found_n",
        "verification_records",
    ):
        assert k in st, f"missing Re08 field: {k}"
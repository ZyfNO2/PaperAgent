"""Re03 SOP §6.1: query_matrix tests."""

import pytest

from app.services.agents.query_matrix import build_query_matrix


def test_build_query_matrix_core_method_task():
    qm = build_query_matrix("U-Net 钢材裂缝", {
        "method_terms": ["U-Net", "encoder-decoder"],
        "task_terms": ["crack segmentation"],
        "object_terms": ["steel surface"],
        "query_atoms_en": ["U-Net steel crack"],
        "domain_route": "vision_2d",
    })
    assert qm["domain_route"] == "vision_2d"
    assert qm["query_families"]["core"]
    # First core query should have method+task
    core0 = qm["query_families"]["core"][0]
    assert "U-Net" in core0 and "crack segmentation" in core0


def test_query_matrix_falls_back_to_raw_topic_when_empty():
    qm = build_query_matrix("基于Unet的钢材裂缝分割", {})
    assert qm["query_families"]["core"] == ["基于Unet的钢材裂缝分割"]
    # Fallback never silently produces "machine learning"
    for fam_queries in qm["query_families"].values():
        for q in fam_queries:
            assert q != "machine learning"


def test_query_matrix_no_method_no_task_still_produces_families():
    qm = build_query_matrix("some topic", {
        "query_atoms_en": ["term1 term2"],
        "object_terms": ["obj"],
    })
    # dataset / repo / survey / benchmark must still exist
    assert "dataset" in qm["query_families"]
    assert "repo" in qm["query_families"]
    assert "survey" in qm["query_families"]
    assert "benchmark" in qm["query_families"]


def test_query_matrix_dedups_within_family():
    qm = build_query_matrix("t", {
        "method_terms": ["U-Net", "U-Net"],
        "task_terms": ["crack"],
        "object_terms": [],
        "query_atoms_en": [],
        "domain_route": "vision_2d",
    })
    for fam, qs in qm["query_families"].items():
        assert len(qs) == len(set(qs)), f"duplicates in {fam}"


def test_query_matrix_axes_preserve_original_terms():
    qm = build_query_matrix("t", {
        "method_terms": ["A", "B"],
        "task_terms": ["X"],
        "object_terms": ["Y"],
        "domain_route": "d",
    })
    assert qm["axes"]["method_terms"] == ["A", "B"]
    assert qm["axes"]["task_terms"] == ["X"]
    assert qm["axes"]["object_terms"] == ["Y"]
    assert qm["axes"]["domain_route"] == "d"

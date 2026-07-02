"""Re05 task B (SOP §3) — canonical baseline registry feeds baseline queries only.

S66v compliance assertion: registry entries NEVER reach `candidate_pool.py`.
"""

from __future__ import annotations

import os

from app.services.agents.data.canonical_baselines import (
    load_canonical_baselines,
    load_keywords,
)
from app.services.agents.query_matrix import build_query_matrix


def _qm_for(domain: str, **extra):
    atoms = {
        "method_terms": [],
        "task_terms": ["point cloud completion"],
        "object_terms": [],
        "query_atoms_en": ["point cloud completion"],
        "domain_route": domain,
    }
    atoms.update(extra)
    return build_query_matrix("point cloud completion", atoms)


def test_canonical_baselines_feed_query():
    qm = _qm_for("point_cloud_completion")
    baseline = qm["query_families"]["baseline"]
    assert baseline, "baseline family should not be empty"
    assert any(b.startswith(("PCN ", "SnowflakeNet ", "PoinTr ", "GRNet ")) for b in baseline), (
        f"expected canonical baseline prefix, got {baseline!r}"
    )
    # Canonical hit = no fallback degradation.
    assert qm["baseline_fallback_reason"] is None


def test_canonical_baselines_not_in_pool():
    # The registry MUST NOT be reachable from candidate_pool.py — S66v claim.
    cp_path = os.path.join(
        os.path.dirname(__file__),  # g:/PaperAgent/apps/api/tests
        "..", "app", "services", "agents", "candidate_pool.py",
    )
    cp_path = os.path.normpath(cp_path)
    with open(cp_path, "r", encoding="utf-8") as f:
        src = f.read()
    assert "canonical_baselines" not in src, (
        "S66v violation: candidate_pool.py must not reference the canonical baseline registry"
    )
    # The loader itself must return names (sanity).
    names = load_canonical_baselines("point_cloud_completion")
    assert "PCN" in names and "SnowflakeNet" in names


def test_load_canonical_baselines_missing_domain():
    assert load_canonical_baselines("not_a_real_domain_xyz") == []
    assert load_canonical_baselines("") == []
    # keywords also missing-safe
    assert load_keywords("not_a_real_domain_xyz") == []


def test_canonical_keywords_load():
    kws = load_keywords("remote_sensing_detection")
    assert "remote sensing" in kws
    assert load_keywords("") == []


def test_remote_sensing_canonical_query():
    qm = _qm_for(
        "remote_sensing_detection",
        task_terms=["remote sensing object detection"],
        query_atoms_en=["remote sensing object detection"],
    )
    baseline = qm["query_families"]["baseline"]
    assert any(b.startswith(("YOLOv5 ", "YOLOv7 ", "YOLOv8 ")) for b in baseline), baseline
    assert qm["baseline_fallback_reason"] is None


def test_uncatalogued_domain_keeps_four_layer_fallback():
    # Unknown domain → canonical registry returns [] → existing 4-layer
    # fallback should kick in (no regression).
    qm = build_query_matrix(
        "raw topic",
        {
            "method_terms": ["methA", "methB"],
            "task_terms": ["taskA"],
            "object_terms": [],
            "query_atoms_en": ["methA taskA"],
            "domain_route": "totally_unknown_domain_xyz",
        },
    )
    baseline = qm["query_families"]["baseline"]
    assert baseline, "4-layer fallback must still produce baseline queries"
    # method+task layer should fire (no fallback reason)
    assert any("methA" in b and "taskA" in b for b in baseline)
    assert qm["baseline_fallback_reason"] is None

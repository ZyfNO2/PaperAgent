"""Re06 SOP §5 acceptance — evidence consistency + role classification tests.

Covers the regression cases R1-R5 from
``Plan/PaperAgent_Re06_去硬编码噪声与证据一致性审计_SOP.md``.
"""
from __future__ import annotations

import pytest

from app.services.agents.eval import compute_resource_status
from app.services.agents.evidence_consistency import (
    audit_candidate,
    audit_synthesis,
    ConsistencyResult,
)
from app.services.agents.evidence_roles import (
    classify_dataset_role,
    classify_baseline_role,
    classify_parallel_role,
)


# ---- R1: AGN metadata mismatch --------------------------------------------

def test_r1_agn_metadata_mismatch_is_metadata_mismatch_not_noise():
    """AGN 天体物理 title + ORB-SLAM3 abstract → metadata_mismatch, NOT off_topic.

    The old `_is_strong_noise` gate would have flagged this as noise
    because of the substring "AGN" → status="fail".
    Re06 must instead use title-abstract consistency to flag it as
    ``metadata_mismatch`` and never reach ``off_topic`` via a
    substring blacklist.
    """
    cand = {
        "candidate_id": "c-agn-orbslam3",
        "title": "A rich bounty of AGN in the 9 square degree Bootes survey: "
                 "high-z obscured AGN and large-scale structure",
        "abstract": "We propose ORB-LINE-SLAM3, a tightly coupled "
                    "Lidar-Inertial-Visual SLAM system for dynamic "
                    "environments with moving object rejection.",
        "url": "https://doi.org/10.1234/agn-survey",
        "source_type": "crossref",
    }
    topic_atoms = {
        "task": ["SLAM", "visual odometry"],
        "object": ["dynamic environment", "moving object"],
        "method": ["ORB-SLAM3", "tightly coupled"],
        "scenario": ["indoor", "outdoor"],
    }
    res = audit_candidate(cand, role="baseline", topic_atoms=topic_atoms)
    assert res.consistency_status == "metadata_mismatch", res
    assert res.evidence_quality.title_abstract_consistent is False
    assert res.evidence_quality.has_title is True
    assert res.evidence_quality.has_abstract is True


# ---- R2: Agnostic Lane Detection must not be flagged as noise -------------

def test_r2_agnostic_lane_detection_passes_consistency_audit():
    """`Agnostic Lane Detection` must NOT trigger a noise keyword.

    Old `_is_strong_noise("Agnostic Lane Detection")` returned True
    because `"agn"` is a substring of "Agnostic".  Re06 has no
    substring blacklist at all; the candidate is judged purely on
    axis coverage.
    """
    cand = {
        "candidate_id": "c-agnostic-lane",
        "title": "Agnostic Lane Detection",
        "abstract": "Instance-segmentation based lane detection for "
                    "autonomous driving in road scenes.",
        "url": "https://arxiv.org/abs/1905.03704",
        "source_type": "arxiv",
    }
    topic_atoms = {
        "task": ["lane detection"],
        "object": ["lane", "road", "autonomous driving"],
        "method": ["instance segmentation", "deep learning"],
        "scenario": ["road scene"],
    }
    res = audit_candidate(cand, role="parallel", topic_atoms=topic_atoms)
    # Either aligned (object+task both hit) or proxy (at least one).
    # Crucially, it must NOT be off_topic and must NOT be rejected.
    assert res.consistency_status in {"aligned", "proxy"}, res
    assert res.consistency_status != "metadata_mismatch"
    # The whole module must not contain a `_is_strong_noise` reference.
    from app.services.agents.eval import compute_resource_status
    import app.services.agents.eval as eval_mod
    assert not hasattr(eval_mod, "_is_strong_noise"), (
        "Re06 SOP §4 Task A: production code must not retain _is_strong_noise"
    )
    assert not hasattr(eval_mod, "STRONG_NOISE_TOKENS"), (
        "Re06 SOP §4 Task A: production code must not retain STRONG_NOISE_TOKENS"
    )


# ---- R3: core=0 + only generic/proxy baseline must downgrade to weak ------

def test_r3_core_zero_only_generic_baseline_downgrades_to_weak():
    """core=0 + generic/proxy baseline (DAMO-YOLO/NEU-DET) → weak, not pass."""
    pool = [
        *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
        {"evidence_type": "dataset", "title": "COCO"},
        {"evidence_type": "dataset", "title": "DOTA"},
        {"evidence_type": "dataset", "title": "NEU-DET"},
        {"evidence_type": "dataset", "title": "PCB-defect"},
    ]
    synthesis = {
        "paper_groups": {
            "baseline": [
                {"candidate_id": "c-damo", "title": "DAMO-YOLO",
                 "abstract": "DAMO-YOLO is a compact and efficient object "
                             "detection model that achieves state-of-the-art "
                             "performance across detection benchmarks."},
                {"candidate_id": "c-hyperdefect", "title": "HyperDefect-YOLO",
                 "abstract": "HyperDefect-YOLO proposes a hypernetwork-driven "
                             "defect detection framework with adaptive YOLO "
                             "backbones."},
                {"candidate_id": "c-yolopears", "title": "YOLOPears",
                 "abstract": "YOLOPears is a YOLO-based pear detection system "
                             "designed for orchard environments."},
                {"candidate_id": "c-neudet", "title": "NEU-DET baseline paper",
                 "abstract": "NEU-DET is a steel surface defect detection "
                             "benchmark dataset for industrial quality "
                             "control."},
            ],
            "parallel": [],
            "reference": [],
            "long_tail_candidates": [],
        },
        "candidate_pool": {
            "core": [],
            "dataset": [
                {"title": "COCO", "name": "COCO",
                 "url": "https://cocodataset.org/",
                 "source_type": "openalex"},
                {"title": "DOTA", "name": "DOTA",
                 "url": "https://captain-whu.github.io/DOTA/",
                 "source_type": "openalex"},
                {"title": "NEU-DET", "name": "NEU-DET",
                 "url": "http://faculty.neu.edu.cn/songkechen/zh_CN/zdylm/263270/list/index.htm",
                 "source_type": "openalex"},
                {"title": "PCB-defect", "name": "PCB-defect",
                 "url": "https://github.com/Ironbrotherstyle/PCB-defect",
                 "source_type": "openalex"},
            ],
        },
        "topic_atoms": {
            "task": ["defect detection"],
            "object": ["insulator", "catenary"],
            "method": ["deep learning"],
            "scenario": ["railway"],
        },
    }
    status = compute_resource_status({"candidate_pool": pool, "synthesis": synthesis})
    assert status["status"] == "weak", status
    assert status["core_direct_n"] == 0
    assert status["topic_dataset_n"] == 0
    assert "datasets_present_but_no_topic_dataset" in status["evidence_gap_reasons"]


# ---- R4: dataset role tier classification ----------------------------------

def test_r4_pcn_topicshape_pretrain_kitti_proxy():
    """PCN = topic (completion benchmark), ShapeNet = pretrain, KITTI = proxy."""
    atoms = {
        "task": ["point cloud completion", "pcn"],
        "object": ["partial point cloud", "3d shape"],
        "method": ["deep learning"],
        "scenario": ["3d vision"],
    }
    pcn = classify_dataset_role(
        {"title": "PCN: Point Completion Network", "name": "PCN",
         "abstract": "Point cloud completion benchmark", "url": "https://...",
         "source_type": "openalex"},
        topic_atoms=atoms,
    )
    shapenet = classify_dataset_role(
        {"title": "ShapeNet: An Information-Rich 3D Model Repository",
         "name": "ShapeNet", "url": "https://shapenet.org/",
         "source_type": "openalex"},
        topic_atoms=atoms,
    )
    kitti = classify_dataset_role(
        {"title": "KITTI Vision Benchmark Suite",
         "name": "KITTI", "url": "https://www.cvlibs.net/datasets/kitti/",
         "source_type": "openalex"},
        topic_atoms=atoms,
    )
    # PCN is both a canonical benchmark AND a direct axis match
    # for point cloud completion → role = "topic".
    assert pcn.role == "topic", pcn
    # ShapeNet is a canonical pretrain family (modelnet/shapenet
    # family) but its name doesn't share tokens with the atoms →
    # role = "pretrain".
    assert shapenet.role == "pretrain", shapenet
    # KITTI is an autonomous-driving benchmark.  It is NOT in the
    # canonical pretrain roster anymore (deliberately) and its name
    # doesn't share tokens with the topic atoms → role = "proxy".
    assert kitti.role == "proxy", kitti


# ---- R5: attack/defense axis missing → weak, not pass ----------------------

def test_r5_attack_defense_axis_missing_downgrades_to_weak():
    """Topic mentions attack/defense but no candidate hits task axis → weak."""
    pool = [
        *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
        {"evidence_type": "repo", "title": "owner/multimodal-perception"},
    ]
    synthesis = {
        "paper_groups": {
            "baseline": [
                {"candidate_id": "c-mmf-perception",
                 "title": "Multi-Modal Fusion Perception for Autonomous Driving",
                 "abstract": "We propose a multi-modal fusion perception system "
                             "that combines camera and lidar for autonomous "
                             "driving perception tasks."},
                {"candidate_id": "c-bevfusion", "title": "BEVFusion",
                 "abstract": "BEVFusion is a multi-modal fusion framework for "
                             "3D object detection in autonomous driving."},
                {"candidate_id": "c-transfusion", "title": "TransFusion",
                 "abstract": "TransFusion is an end-to-end transformer-based "
                             "model for 3D object detection."},
                {"candidate_id": "c-ptv3", "title": "Point Transformer V3",
                 "abstract": "Point Transformer V3 is a transformer model "
                             "designed for 3D point cloud perception."},
            ],
            "parallel": [
                {"candidate_id": "c-autonomous-perception",
                 "title": "Autonomous Driving Perception Survey",
                 "abstract": "A survey of perception methods for self-driving "
                             "cars covering detection and segmentation."},
                {"candidate_id": "c-image-classification-robustness",
                 "title": "Image Classification Robustness to Noise",
                 "abstract": "How robust are image classification models to "
                             "input noise perturbations in standard benchmarks?"},
            ],
            "reference": [],
            "long_tail_candidates": [],
        },
        "candidate_pool": {
            "core": [],
            "dataset": [
                # MVTec AD / COCO etc. — explicit dataset count for
                # Re07 pass condition (dataset+repo >= 1).
                {"candidate_id": "c-mvtec", "title": "MVTec AD",
                 "name": "MVTec AD", "source_type": "openalex"},
            ],
        },
        "topic_atoms": {
            "task": ["attack", "defense", "adversarial"],
            "object": ["multi-modal perception", "autonomous driving perception"],
            "method": ["deep learning"],
            "scenario": ["autonomous driving"],
        },
    }
    status = compute_resource_status({"candidate_pool": pool, "synthesis": synthesis})
    # Re07 SOP §5.3: Re05 case 066 must NOT be pass — axis missing.
    assert status["status"] == "weak", status
    assert "attack_defense_axis_missing" in status["axis_missing_reasons"]
    # Sanity: scenario/object axes may also be missing, but the
    # attack_defense flag MUST be present (R5 regression).
    assert any(r.startswith("attack_defense") for r in status["axis_missing_reasons"])


# ---- Extra: aggregate metrics exposes Re06 counters ------------------------

def test_aggregate_metrics_re06_counters_present():
    from app.services.agents.eval import aggregate_metrics
    agg = aggregate_metrics([
        {"status": "pass", "core_direct_n": 1, "metadata_mismatch_n": 0,
         "off_topic_core_n": 0, "critical_consistency_error_n": 0},
        {"status": "weak", "core_direct_n": 0, "metadata_mismatch_n": 0,
         "off_topic_core_n": 0, "critical_consistency_error_n": 0},
        {"status": "fail", "core_direct_n": 1, "metadata_mismatch_n": 1,
         "off_topic_core_n": 0, "critical_consistency_error_n": 1},
    ])
    assert agg["critical_consistency_error_cases"] == 1
    assert agg["metadata_mismatch_cases"] == 1
    assert agg["core_zero_pass_cases"] == 0
    assert "critical_consistency_error_cases" in agg


# ---- Extra: pass case with topic dataset + repo ---------------------------

def test_pass_case_with_topic_dataset_and_repo():
    pool = [
        *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
        {"evidence_type": "dataset", "title": "MVTec AD"},
        {"evidence_type": "repo", "title": "owner/R1"},
    ]
    synthesis = {
        "paper_groups": {
            "baseline": [
                {"candidate_id": "c-mt-u2net", "title": "MT-U2Net for magnetic tile",
                 "abstract": "Magnetic tile surface defect detection"},
            ],
            "parallel": [
                {"candidate_id": "c-yolo-tile", "title": "Improved YOLO for tile defects",
                 "abstract": "Real-time tile defect detection"},
                {"candidate_id": "c-rtdetr-tile", "title": "RT-DETR for magnetic tile",
                 "abstract": "Magnetic tile surface defect detection"},
            ],
            "reference": [],
            "long_tail_candidates": [],
        },
        "candidate_pool": {
            "core": [
                {"candidate_id": "c-mt-u2net", "title": "MT-U2Net for magnetic tile",
                 "abstract": "Magnetic tile surface defect detection in an "
                             "industrial inspection line setting"},
            ],
            "dataset": [
                # PCN is the canonical completion/industrial defect
                # benchmark — not on the pretrain roster, name shares
                # "pcn" with topic atoms → topic_dataset.
                {"title": "PCN magnetic-tile defect dataset",
                 "name": "PCN",
                 "url": "https://example.org/pcn",
                 "source_type": "openalex",
                 "abstract": "PCN is an industrial magnetic-tile defect "
                             "detection dataset for surface defect "
                             "research."},
            ],
        },
        "topic_atoms": {
            "task": ["surface defect detection"],
            "object": ["magnetic tile", "pcn"],
            "method": ["deep learning"],
            "scenario": ["industrial inspection"],
        },
    }
    status = compute_resource_status({"candidate_pool": pool, "synthesis": synthesis})
    assert status["status"] == "pass", status
    assert status["core_direct_n"] >= 1
    assert status["topic_dataset_n"] >= 1
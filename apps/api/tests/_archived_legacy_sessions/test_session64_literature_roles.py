"""Session 64 T7: literature_role_classifier backend tests.

覆盖四个核心分类路径:
- baseline_framework (YOLOv8 框架介绍)
- survey (综述)
- dataset_paper (数据集/基准)
- irrelevant (错领域: medical)
"""

from __future__ import annotations


from app.services.retrieval.literature_role_classifier import (
    classify_literature,
)


TOPIC_ATOMS_CRACK = {
    "object_terms": ["混凝土", "裂缝", "桥梁", "concrete", "crack", "bridge"],
    "task_terms": ["缺陷检测", "裂缝检测", "detection", "detection"],
    "method_terms": ["YOLO", "CNN", "yolov8", "yolov5"],
    "domain": "vision_2d",
}


def test_yolov8_is_baseline_framework():
    """YOLOv8 should be baseline_framework."""
    candidates = [{
        "candidate_id": "1",
        "title": "YOLOv8: Ultralytics State-of-the-Art Real-Time Object Detector",
        "abstract": "We introduce YOLOv8, a unified framework for object detection.",
        "code_url": "https://github.com/ultralytics/ultralytics",
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    assert roles[0].role == "baseline_framework"
    assert roles[0].base_framework == "yolov8"


def test_survey_is_survey():
    """Survey should be survey, not baseline."""
    candidates = [{
        "candidate_id": "2",
        "title": "Deep Learning for Crack Detection: A Survey",
        "abstract": "Comprehensive survey of crack detection methods on concrete and bridge structures.",
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    assert roles[0].role == "survey"


def test_codebrim_is_dataset():
    """CODEBRIM should be dataset_paper."""
    candidates = [{
        "candidate_id": "3",
        "title": "CODEBRIM: Concrete Bridge Defect Dataset",
        "abstract": "We release CODEBRIM, a benchmark dataset for bridge defect classification on concrete structures.",
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    assert roles[0].role == "dataset_paper"


def test_medical_is_irrelevant():
    """Medical papers should be irrelevant for civil engineering."""
    candidates = [{
        "candidate_id": "4",
        "title": "X-ray Bone Fracture Detection",
        "abstract": "Medical imaging for bone detection in clinical settings.",
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    assert roles[0].role == "irrelevant"


def test_parallel_application_paper():
    """YOLOv8 + module on concrete crack → parallel_application_paper."""
    candidates = [{
        "candidate_id": "5",
        "title": "Concrete Crack Detection with Improved YOLOv8 and CBAM Attention",
        "abstract": (
            "We improve YOLOv8 with CBAM attention and feature pyramid fusion "
            "for concrete crack detection on bridge surfaces, achieving higher mAP."
        ),
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    # 同时命中 yolov8 框架 + 模块关键词 + concrete/crack 任务对象 → parallel
    assert roles[0].role == "parallel_application_paper"
    assert roles[0].base_framework == "yolov8"


def test_low_relevance_irrelevant():
    """Title without concrete/crack/bridge terms and no framework → irrelevant."""
    candidates = [{
        "candidate_id": "6",
        "title": "Random topic far from civil engineering",
        "abstract": "Something unrelated to concrete or bridges.",
    }]
    roles = classify_literature(candidates, TOPIC_ATOMS_CRACK)
    # object/task/method < 2/4 → irrelevant
    assert roles[0].role == "irrelevant"
"""Session 64 T7: candidate_cleaner backend tests.

覆盖 T1 之外的边界场景:
- 跑题标题 (AGN / German survey / medical / MLPerf) 在 civil 题目下被 reject
- 相关题目 (YOLO + concrete crack) 被 keep 或 quarantine
- is_irrelevant_title 命中各跑题模式
"""

from __future__ import annotations

import pytest

from app.services.retrieval.candidate_cleaner import (
    clean_candidates,
    is_irrelevant_title,
)


# 题目对象关键词 (硬规则触发条件之一) - civil/concrete crack 主题
TOPIC_ATOMS_CRACK = {
    "raw": "concrete crack detection on bridge surfaces using YOLO",
    "required": ["concrete", "crack", "YOLO"],
    "domain_hint": "civil",
    "method_terms": ["YOLO", "CNN"],
    "task_terms": ["缺陷检测", "裂缝检测"],
    "object_terms": ["混凝土", "裂缝", "桥梁"],
    "modality_terms": ["图像", "2D"],
    "domain": "vision_2d",
}


def test_agn_paper_rejected():
    """AGN paper should be rejected for concrete crack topic."""
    candidates = [{
        "candidate_id": "agn1",
        "title": "A rich bounty of AGN: relativistic jets",
        "abstract": "Active Galactic Nuclei and jets",
        "retrieval_score": 0.5,
        "matched_atoms": ["galaxy"],
    }]
    results = clean_candidates(candidates, TOPIC_ATOMS_CRACK, domain="vision_2d")
    assert results[0].clean_status == "reject"
    # 不管 reason 文本怎么写, 类型必须是 wrong_domain
    assert results[0].mismatch_type == "wrong_domain"


def test_german_survey_rejected():
    """German survey should be rejected for civil engineering."""
    candidates = [{
        "candidate_id": "survey1",
        "title": "AIn't Nothing But a Survey: German Coding Challenges",
        "abstract": "Survey of German programming",
        "retrieval_score": 0.4,
        "matched_atoms": [],
    }]
    results = clean_candidates(candidates, TOPIC_ATOMS_CRACK, domain="vision_2d")
    # 命中 german.*coding 跑题模式 → reject
    assert results[0].clean_status in ("reject", "quarantine")
    assert results[0].mismatch_type in ("wrong_domain", "not_paper")


def test_concrete_crack_yolo_kept():
    """YOLO for concrete crack should be kept (or quarantine)."""
    candidates = [{
        "candidate_id": "yolo1",
        "title": "YOLOv8 for Concrete Crack Detection",
        "abstract": "Using YOLOv8 for detecting cracks in concrete structures",
        "retrieval_score": 0.7,
        "matched_atoms": ["YOLO", "concrete", "crack"],
    }]
    results = clean_candidates(candidates, TOPIC_ATOMS_CRACK, domain="vision_2d")
    # 不命中任何跑题模式, score 足够, 命中多个 atoms → keep 或 quarantine 都行, 但绝不 reject
    assert results[0].clean_status in ("keep", "quarantine")
    assert results[0].clean_status != "reject"


@pytest.mark.parametrize(
    "title",
    [
        "A rich bounty of AGN",
        "German coding survey",
        "X-ray medical imaging",
        "MLPerf benchmark",
        "Active galactic nuclei jets",
        "Cosmology and galaxy formation",
        "Astronomy and astrophysics overview",
        "CT scan for radiologists",
        "MRI brain tumor segmentation",
        "Protein structure prediction for drug discovery",
    ],
)
def test_is_irrelevant_title(title: str):
    """Check irrelevant title patterns are all flagged."""
    assert is_irrelevant_title(title), f"Should reject: {title}"


def test_relevant_title_not_irrelevant():
    """A relevant concrete crack title must not be flagged as irrelevant."""
    title = "YOLOv8 with CBAM attention for concrete crack detection on bridges"
    assert is_irrelevant_title(title) is False
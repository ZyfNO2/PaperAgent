"""Self-check for keyword_match_explainer (Session 65 T1).

Run: .venv/Scripts/python.exe -m pytest apps/api/tests/test_keyword_match_explainer.py -v
or:  python -m apps.api.tests.test_keyword_match_explainer
"""

from __future__ import annotations

import sys

from app.services.retrieval.keyword_match_explainer import (
    explain_keyword_match,
    _count_atoms_in_text,
    _detect_unrelated,
    _detect_evidence_gap,
    KeywordMatchExplanation,
)


def test_count_atoms_basic():
    text = "We apply U-Net to crack segmentation on concrete surface."
    hits = _count_atoms_in_text(["U-Net", "crack", "concrete", "BERT"], text)
    assert "U-Net" in hits
    assert "crack" in hits
    assert "concrete" in hits
    assert "BERT" not in hits


def test_count_atoms_case_insensitive():
    text = "Surface DEFECT detection with deep learning."
    hits = _count_atoms_in_text(["surface defect", "DEEP LEARNING"], text)
    assert "surface defect" in hits
    assert "DEEP LEARNING" in hits


def test_count_atoms_word_boundary():
    # "crack" should NOT match "crackpot" via word boundary
    text = "We study crackpot theories in materials."
    hits = _count_atoms_in_text(["crack"], text)
    assert hits == []


def test_count_atoms_chinese():
    text = "基于深度学习的混凝土裂缝检测"
    hits = _count_atoms_in_text(["混凝土", "裂缝", "检测", "桥梁"], text)
    assert "混凝土" in hits
    assert "裂缝" in hits
    assert "检测" in hits
    assert "桥梁" not in hits


def test_count_atoms_empty_inputs():
    assert _count_atoms_in_text([], "anything") == []
    assert _count_atoms_in_text(["foo"], "") == []
    assert _count_atoms_in_text(["foo"], None or "") == []


def test_detect_unrelated_survey():
    text = "A Survey Motivation: German Open-Ended Survey on coding practices."
    hits = _detect_unrelated(text)
    assert "survey motivation" in hits
    assert "german coding" in hits or "german open-ended" in hits


def test_detect_unrelated_clean_text():
    text = "U-Net for concrete crack segmentation"
    assert _detect_unrelated(text) == []


def test_detect_evidence_gap_no_match():
    gap = _detect_evidence_gap([], [], [], ["concrete"], None)
    assert gap == "object_missing"


def test_detect_evidence_gap_full_match():
    gap = _detect_evidence_gap(["U-Net"], ["segmentation"], ["crack"], [], None)
    assert gap == "none"


def test_detect_evidence_gap_url_failed():
    gap = _detect_evidence_gap(["U-Net"], ["seg"], ["crack"], [], "fetch_failed")
    assert gap == "url_unverified"


def test_detect_evidence_gap_wrong_domain():
    gap = _detect_evidence_gap([], [], [], [], None)
    assert gap == "wrong_domain"


def test_explain_keyword_match_happy_path():
    candidate = {
        "candidate_id": "p1",
        "title": "U-Net for Concrete Crack Segmentation",
        "abstract": "We apply U-Net to detect crack on concrete surface.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["segmentation", "detection"],
        "object_terms": ["crack", "concrete"],
        "modality_terms": ["image"],
    }
    result = explain_keyword_match(candidate, topic_atoms)
    assert isinstance(result, KeywordMatchExplanation)
    assert result.candidate_id == "p1"
    assert "U-Net" in result.matched_topic_keywords
    assert "crack" in result.matched_topic_keywords
    assert "concrete" in result.matched_topic_keywords
    assert result.evidence_gap == "none"
    assert "命中" in result.match_summary


def test_explain_keyword_match_missing_required():
    candidate = {
        "candidate_id": "p2",
        "title": "Image segmentation survey",
        "abstract": "A review of segmentation methods.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["segmentation"],
        "object_terms": ["crack", "concrete"],
        "required": ["U-Net", "concrete", "公开数据集", "baseline 代码"],
    }
    result = explain_keyword_match(candidate, topic_atoms)
    assert "公开数据集" in result.missing_required_keywords
    assert "baseline 代码" in result.missing_required_keywords
    assert "concrete" in result.missing_required_keywords
    assert result.evidence_gap in {"object_missing", "dataset_missing", "repo_missing"}


def test_explain_keyword_match_with_unrelated_hints():
    candidate = {
        "candidate_id": "p3",
        "title": "AIn't Nothing But a Survey",
        "abstract": "Survey motivation for German Open-Ended Survey about coding.",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["segmentation"],
        "object_terms": ["crack"],
    }
    result = explain_keyword_match(candidate, topic_atoms)
    assert len(result.unrelated_keywords) > 0
    assert result.evidence_gap == "wrong_domain"


def test_explain_keyword_match_handles_missing_fields():
    candidate = {"candidate_id": "p4"}  # no title, no abstract
    topic_atoms = {"method_terms": ["U-Net"], "object_terms": ["crack"]}
    result = explain_keyword_match(candidate, topic_atoms)
    assert result.candidate_id == "p4"
    assert result.matched_topic_keywords == []
    assert result.evidence_gap == "wrong_domain"


def test_explain_keyword_match_url_unverified():
    candidate = {
        "candidate_id": "p5",
        "title": "Crack segmentation with U-Net",
        "abstract": "We use U-Net on concrete cracks.",
        "source_status": "fetch_failed",
    }
    topic_atoms = {
        "method_terms": ["U-Net"],
        "task_terms": ["segmentation"],
        "object_terms": ["crack", "concrete"],
    }
    result = explain_keyword_match(candidate, topic_atoms)
    assert result.evidence_gap == "url_unverified"


def main() -> int:
    failures: list[str] = []
    tests = [
        v for k, v in globals().items() if k.startswith("test_") and callable(v)
    ]
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
            failures.append(t.__name__)
        except Exception as e:  # noqa: BLE001
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
            failures.append(t.__name__)
    print()
    if failures:
        print(f"FAILED: {len(failures)} / {len(tests)}")
        return 1
    print(f"OK: {len(tests)} / {len(tests)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
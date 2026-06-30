"""T1 candidate_cleaner 基础规则测试."""

from app.services.retrieval.candidate_cleaner import (
    CandidateCleanResult,
    clean_candidates,
    is_irrelevant_title,
)


CIVIL_ATOMS = {
    "raw": "concrete crack detection on bridge surfaces",
    "required": ["concrete", "crack", "bridge"],
    "domain_hint": "civil",
}


def test_is_irrelevant_title_agn():
    assert is_irrelevant_title("A rich bounty of AGN spectroscopy in nearby galaxies") is True


def test_is_irrelevant_title_german_survey():
    assert is_irrelevant_title("A German coding survey motivation for software engineers") is True


def test_is_irrelevant_title_medical():
    assert is_irrelevant_title("Deep learning for medical imaging X-ray CT scan segmentation") is True


def test_is_irrelevant_title_mlperf():
    assert is_irrelevant_title("MLPerf: Benchmarking ML performance across hardware") is True


def test_is_irrelevant_title_clean_concrete():
    assert is_irrelevant_title("DeepCrack: Deep learning for concrete crack detection") is False


def test_reject_low_score_no_atoms():
    candidates = [
        {
            "candidate_id": "c1",
            "title": "Random unrelated work",
            "retrieval_score": 0.05,
            "matched_atoms": [],
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "reject"
    assert out[0].mismatch_type == "low_relevance"


def test_reject_agn_for_civil_topic():
    candidates = [
        {
            "candidate_id": "c2",
            "title": "A rich bounty of AGN in nearby galaxies",
            "retrieval_score": 0.55,
            "matched_atoms": ["galaxy"],
            "abstract": "AGN astronomy study.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "reject"
    assert out[0].mismatch_type == "wrong_domain"


def test_reject_german_survey_for_civil():
    candidates = [
        {
            "candidate_id": "c3",
            "title": "A German coding survey motivation paper",
            "retrieval_score": 0.40,
            "matched_atoms": [],
            "abstract": "German software engineering study.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "reject"


def test_reject_medical_for_civil():
    candidates = [
        {
            "candidate_id": "c4",
            "title": "Deep learning for medical imaging X-ray CT scan segmentation",
            "retrieval_score": 0.45,
            "matched_atoms": ["segmentation"],
            "abstract": "Medical X-ray analysis.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "reject"


def test_reject_mlperf_for_civil():
    candidates = [
        {
            "candidate_id": "c5",
            "title": "MLPerf: Benchmarking ML inference across GPUs",
            "retrieval_score": 0.50,
            "matched_atoms": ["benchmark"],
            "abstract": "Benchmarking ML systems.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "reject"


def test_quarantine_dead_url():
    candidates = [
        {
            "candidate_id": "c6",
            "title": "Some concrete study",
            "url": "https://example.com/404",
            "source_status": "fetch_failed",
            "retrieval_score": 0.6,
            "matched_atoms": ["concrete"],
            "abstract": "Concrete crack analysis.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    assert out[0].clean_status == "quarantine"
    assert out[0].mismatch_type == "wrong_url"


def test_quarantine_survey_only_no_object():
    candidates = [
        {
            "candidate_id": "c7",
            "title": "A survey of computer vision methods",
            "url": "https://arxiv.org/abs/0000.0000",
            "retrieval_score": 0.5,
            "matched_atoms": ["survey"],
            "abstract": "We review deep learning methods in general.",
        }
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    # survey-only + 无 civil object → quarantine
    assert out[0].clean_status == "quarantine"


def test_result_sorting_keep_first():
    candidates = [
        {"candidate_id": "bad", "title": "AGN stuff", "retrieval_score": 0.5, "matched_atoms": ["x"],
         "abstract": "AGN."},
        {"candidate_id": "q", "title": "Some concrete work", "url": "x", "retrieval_score": 0.7,
         "matched_atoms": ["concrete"], "source_status": "fetch_failed", "abstract": "Concrete."},
    ]
    out = clean_candidates(candidates, CIVIL_ATOMS, domain="vision_2d")
    # bad -> reject, q -> quarantine. quarantine 应排在 reject 之前
    statuses = [r.clean_status for r in out]
    assert statuses.index("quarantine") < statuses.index("reject")
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

_SCORER_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "score_academic_tailoring_retrieval_v1.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "academic_tailoring_retrieval_v1_scorer", _SCORER_PATH
)
assert _SPEC is not None and _SPEC.loader is not None
_SCORER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SCORER)

_accepted_verified_items = _SCORER._accepted_verified_items
_baseline_target_titles = _SCORER._baseline_target_titles
_titles_related = _SCORER._titles_related


def test_titles_related_accepts_alias_containment_but_rejects_neighbor_paper() -> None:
    assert _titles_related(
        "USAD", "USAD: UnSupervised Anomaly Detection on Multivariate Time Series"
    )
    assert not _titles_related(
        "TimeMachine: A Time Series is Worth 4 Mambas for Long-Term Forecasting",
        "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers",
    )
    assert not _titles_related(
        "BEiT: BERT Pre-Training of Image Transformers",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    )


def test_declared_baseline_titles_override_gold_alternatives() -> None:
    case = {
        "public_input": {
            "supplied_materials": [
                {"title": "Oriented R-CNN", "declared_role": "reproduced baseline"},
                {"title": "Parallel Paper", "declared_role": "parallel paper"},
            ]
        },
        "gold": {
            "baseline_decision": {"canonical": "Another Baseline"},
            "expected_assets": [],
        },
    }
    assert _baseline_target_titles(case) == ["Oriented R-CNN"]


def test_only_accepted_verified_relevant_evidence_can_score() -> None:
    state = {
        "evidence": {
            "accepted_ids": ["good", "rejected-review"],
            "items": [
                {"evidence_id": "good", "title": "Correct Paper", "source_type": "paper"},
                {
                    "evidence_id": "rejected-review",
                    "title": "Correct Repository",
                    "source_type": "repository",
                },
                {"evidence_id": "not-accepted", "title": "Gold Paper", "source_type": "paper"},
            ],
        }
    }
    reviews = [
        SimpleNamespace(
            evidence_id="good", accepted=True, identity_verified=True, relevance_passed=True
        ),
        SimpleNamespace(
            evidence_id="rejected-review",
            accepted=False,
            identity_verified=True,
            relevance_passed=True,
        ),
        SimpleNamespace(
            evidence_id="not-accepted",
            accepted=True,
            identity_verified=True,
            relevance_passed=True,
        ),
    ]
    trace = SimpleNamespace(evidence_reviews=reviews)

    items = _accepted_verified_items(state, trace)

    assert [item["evidence_id"] for item in items] == ["good"]

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

_accepted_asset_matches = _SCORER._accepted_asset_matches
_accepted_verified_items = _SCORER._accepted_verified_items
_dataset_asset_score = _SCORER._dataset_asset_score
_baseline_target_titles = _SCORER._baseline_target_titles
_titles_related = _SCORER._titles_related
_rejection_outcome = _SCORER._rejection_outcome


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


def test_title_identity_is_symmetric_and_rejects_prefixed_neighbor_paper() -> None:
    assert _titles_related(
        "Oriented R-CNN for Object Detection",
        "Oriented R-CNN for Object Detection",
    )
    assert not _titles_related(
        "Multispectral-oriented R-CNN for object detection in remote sensing images",
        "Oriented R-CNN for Object Detection",
    )


def test_query_text_cannot_impersonate_missing_paper_identity() -> None:
    assets = [
        {
            "kind": "paper",
            "title": "USAD: UnSupervised Anomaly Detection on Multivariate Time Series",
        }
    ]
    items = [
        {
            "source_type": "paper",
            "title": "An Efficient Method for Detecting Abnormal Electricity Behavior",
            "locator": "doi:10.1000/wrong",
            "metadata": {
                "query_text": '"USAD: UnSupervised Anomaly Detection on Multivariate Time Series"'
            },
        }
    ]
    assert _accepted_asset_matches(assets, items) == 0


def test_dataset_mention_scores_partial_not_official_identity_credit() -> None:
    assets = [{"kind": "dataset", "title": "MIMII dataset"}]
    items = [
        {
            "source_type": "dataset",
            "title": "MIMII",
            "locator": "doi:10.1000/paper",
            "metadata": {"relation": "dataset_named_in_verified_paper", "dataset_ref": "MIMII"},
        }
    ]
    assert _accepted_asset_matches(assets, items) == 1
    assert _dataset_asset_score(assets, items) == 4


def test_canonicalization_failure_is_not_safe_rejection() -> None:
    correct, implementation_failure = _rejection_outcome(
        expected_outcome="safe_rejection",
        allowed_rejection_reasons={"semantic_incompatibility"},
        decision="REVISE",
        module_defer_reason="METHOD_CANONICALIZATION_FAILED",
        trace_error_codes=("NOT_EVALUATED",),
        runtime_error=None,
    )
    assert correct is False
    assert implementation_failure is True


def test_safe_rejection_requires_allowed_scientific_reason() -> None:
    correct, implementation_failure = _rejection_outcome(
        expected_outcome="safe_rejection",
        allowed_rejection_reasons={"semantic_incompatibility"},
        decision="NO_GO",
        module_defer_reason="semantic_incompatibility",
        trace_error_codes=(),
        runtime_error=None,
    )
    assert correct is True
    assert implementation_failure is False


def test_runtime_failure_prevents_safe_rejection() -> None:
    correct, _ = _rejection_outcome(
        expected_outcome="safe_rejection",
        allowed_rejection_reasons={"semantic_incompatibility"},
        decision="NO_GO",
        module_defer_reason="semantic_incompatibility",
        trace_error_codes=(),
        runtime_error={"case_id": "case", "error_type": "CaseExecutionIncomplete"},
    )
    assert correct is False

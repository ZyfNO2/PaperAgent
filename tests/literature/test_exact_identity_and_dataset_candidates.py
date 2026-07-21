from __future__ import annotations

from types import SimpleNamespace

from paperagent.literature.adapter import (
    LiteratureSearchAdapter,
    _exact_title_match,
    _quoted_title,
)
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import PaperRecord, RankFeatures, SourceRecord


def _paper(title: str, abstract: str = "") -> PaperRecord:
    return PaperRecord(
        paper_id="paper-test",
        canonical_title=title,
        abstract=abstract,
        doi="10.1000/test",
        urls=[],
        source_records=[SourceRecord(provider="openalex", provider_record_id="x", request_id="r")],
        verification_status="verified",
        rank_features=RankFeatures(
            relevance=1.0,
            gap_coverage=1.0,
            metadata_verification=1.0,
            recency_fit=1.0,
            diversity=1.0,
            citation_tiebreaker=1.0,
            score=1.0,
        ),
    )


def test_quoted_identity_requires_exact_title_before_provider_stop() -> None:
    required = _quoted_title(
        '"PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern Recognition"'
    )
    assert required is not None
    assert _exact_title_match(required, required)
    assert not _exact_title_match(
        "Dynamic Training Strategies for Domain Generalization in Self-Supervised "
        "Anomaly Sound Detection",
        required,
    )


def test_dataset_candidate_is_explicitly_linked_to_verified_paper_mention() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q",
        gap_id="g",
        query="MIMII dataset evaluation protocol low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper("Industrial sound evaluation", "Experiments use the MIMII dataset under noise."),
        False,
    )
    datasets = [item for item in candidates if item.source_type == "dataset"]
    assert len(datasets) == 1
    assert datasets[0].title == "MIMII"
    assert datasets[0].metadata["relation"] == "dataset_named_in_verified_paper"


def test_model_name_is_not_promoted_to_dataset_without_dataset_context() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-model-dataset",
        gap_id="g-model-dataset",
        query="Evaluate PANNs on the MIMII dataset under low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper(
            "PANNs: Large-Scale Pretrained Audio Neural Networks",
            "The PANNs model is evaluated on the MIMII dataset.",
        ),
        False,
    )
    dataset_titles = [item.title for item in candidates if item.source_type == "dataset"]
    assert dataset_titles == ["MIMII"]

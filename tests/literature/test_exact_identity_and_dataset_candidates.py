from __future__ import annotations

from types import SimpleNamespace

from paperagent.literature.adapter import (
    LiteratureSearchAdapter,
    _dataset_names_from_text,
    _dataset_relation_names,
    _exact_title_match,
    _looks_like_dataset_name,
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


def test_dataset_can_be_discovered_from_parallel_paper_text() -> None:
    names = _dataset_relation_names(
        "compare robust anomaly detection methods",
        (
            _paper(
                "A Parallel Industrial Anomaly Method",
                "We evaluate the method on the MIMII dataset and report low-SNR results.",
            ),
        ),
    )
    assert names == ("MIMII",)


def test_dataset_relation_candidate_survives_missing_provider_abstract() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q-linked-dataset",
        gap_id="g-linked-dataset",
        query="Evaluate PANNs on the MIMII dataset under low SNR",
        source_types=["paper", "dataset"],
    )
    candidates = adapter._candidates(
        query,
        _paper("A verified industrial evaluation paper"),
        False,
        relation="parallel_via_dataset",
        linked_dataset_names=("MIMII",),
    )
    datasets = [item for item in candidates if item.source_type == "dataset"]
    assert len(datasets) == 1
    assert datasets[0].title == "MIMII"
    assert datasets[0].metadata["relation"] == "dataset_linked_by_focused_retrieval"
    assert datasets[0].metadata["verification_scope"] == "retrieval_relation"


def test_dataset_entity_precision_rejects_descriptive_words() -> None:
    text = (
        "We use a specific dataset, a large-scale dataset, and this dataset for evaluation. "
        "Results are also reported on the AudioSet dataset and MIMII benchmark."
    )
    assert _dataset_names_from_text(text) == ("AudioSet", "MIMII")
    assert not _looks_like_dataset_name("specific")
    assert not _looks_like_dataset_name("large-scale")
    assert _looks_like_dataset_name("CLINC150")
    assert _looks_like_dataset_name("SWaT")


def test_dataset_relation_query_keeps_dataset_anchor_not_model_title() -> None:
    names = _dataset_relation_names(
        "PANNs pretrained audio baseline performance MIMII dataset",
        (_paper("PANNs: Large-Scale Pretrained Audio Neural Networks"),),
    )
    assert names == ("MIMII",)


def test_dataset_relation_query_rejects_model_only_anchors() -> None:
    names = _dataset_relation_names(
        "BERT LoRA text classification compatibility",
        (
            _paper("BERT: Pre-training of Deep Bidirectional Transformers"),
            _paper("LoRA: Low-Rank Adaptation of Large Language Models"),
        ),
    )
    assert names == ()


def test_dataset_relation_relevance_accepts_verified_dataset_title() -> None:
    paper = _paper("MIMII Dataset: Sound Dataset for Machine Investigation")
    paper = paper.model_copy(
        update={
            "rank_features": paper.rank_features.model_copy(
                update={"relevance": 0.01, "score": 0.01}
            )
        }
    )
    assert LiteratureSearchAdapter._passes_relation_relevance(
        paper,
        dataset_name="MIMII",
    )


def test_relation_providers_defer_rate_limited_source() -> None:
    providers = LiteratureSearchAdapter._relation_providers(
        ("semantic_scholar", "openalex", "arxiv")
    )
    assert providers == ("openalex", "arxiv", "semantic_scholar")


def test_relation_provider_order_respects_configured_availability() -> None:
    providers = LiteratureSearchAdapter._relation_providers(("arxiv", "semantic_scholar"))
    assert providers == ("arxiv", "semantic_scholar")

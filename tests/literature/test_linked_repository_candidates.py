from __future__ import annotations

from types import SimpleNamespace

from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import PaperRecord, RankFeatures, SourceRecord


def _paper(*, verified: bool = True) -> PaperRecord:
    return PaperRecord(
        paper_id="paper-patchtst",
        canonical_title="A Time Series is Worth 64 Words: Long-term Forecasting with Transformers",
        abstract=(
            "PatchTST improves forecasting accuracy. Code is available at: "
            "https://github.com/yuqinie98/PatchTST."
        ),
        doi="10.48550/arxiv.2211.14730",
        urls=["https://arxiv.org/abs/2211.14730"],
        source_records=[
            SourceRecord(provider="openalex", provider_record_id="oa", request_id="req")
        ],
        verification_status="verified" if verified else "pending",
        rank_features=RankFeatures(
            relevance=1.0,
            gap_coverage=1.0,
            metadata_verification=1.0,
            recency_fit=1.0,
            diversity=1.0,
            citation_tiebreaker=1.0,
            score=0.95,
        ),
    )


def test_verified_paper_emits_distinct_author_linked_repository_candidate() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="PatchTST official implementation repository",
        source_types=["paper", "repository", "web"],
    )

    candidates = adapter._candidates(query, _paper(), False)

    assert [candidate.source_type for candidate in candidates] == ["paper", "repository"]
    repository = candidates[1]
    assert repository.title == "yuqinie98/PatchTST"
    assert repository.locator == "https://github.com/yuqinie98/patchtst"
    assert repository.metadata["verification_status"] == "verified"
    assert repository.metadata["relation"] == "author_linked_from_verified_paper"


def test_unverified_paper_does_not_promote_repository_identity() -> None:
    adapter = LiteratureSearchAdapter(service=SimpleNamespace(provider_names=[]))
    query = SearchQuery(
        query_id="q1",
        gap_id="g1",
        query="PatchTST official implementation repository",
        source_types=["paper", "repository", "web"],
    )

    candidates = adapter._candidates(query, _paper(verified=False), False)

    assert [candidate.source_type for candidate in candidates] == ["paper"]

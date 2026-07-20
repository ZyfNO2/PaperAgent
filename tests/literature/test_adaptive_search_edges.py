from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import pytest

from paperagent.errors import ProviderError
from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.source_policy import review_search_query
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import (
    CoverageReport,
    LiteratureBundle,
    PaperRecord,
    ProviderResult,
    RankFeatures,
    RetrievalMetrics,
    SourceRecord,
)

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _query(value: str, *, source_types: list[str] | None = None) -> SearchQuery:
    return SearchQuery(
        query_id="q-edge",
        gap_id="gap-edge",
        query=value,
        source_types=source_types or ["paper", "web"],  # type: ignore[arg-type]
    )


def _paper(
    provider: str,
    *,
    paper_id: str = "paper-edge",
    verified: bool = True,
    relevance: float = 0.8,
    score: float = 0.82,
    abstract: str = "Relevant evidence.",
) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        canonical_title="Lightweight UAV small object detection on VisDrone",
        authors=["Researcher"],
        year=2025,
        abstract=abstract,
        doi="10.1234/edge" if verified else None,
        urls=[f"https://example.org/{provider}/{paper_id}"],
        source_records=[
            SourceRecord(
                provider=provider,
                provider_record_id=f"{provider}-{paper_id}",
                request_id=f"req-{provider}",
            )
        ],
        verification_status="verified" if verified else "pending",
        verification_methods=["crossref_doi_exact"] if verified else [],
        matched_gap_ids=["gap-edge"],
        rank_features=RankFeatures(
            relevance=relevance,
            gap_coverage=1.0,
            metadata_verification=1.0 if verified else 0.5,
            recency_fit=1.0,
            diversity=0.5,
            citation_tiebreaker=0.0,
            score=score,
            explanation=[],
        ),
    )


def _bundle(
    provider: str,
    papers: list[PaperRecord] | None = None,
    *,
    status: str | None = None,
) -> LiteratureBundle:
    selected = papers or []
    resolved_status = status or ("success" if selected else "empty")
    result_kwargs: dict[str, Any] = {}
    if resolved_status in {"failed", "timeout", "rate_limited"}:
        result_kwargs = {
            "error_code": resolved_status.upper(),
            "error_message": resolved_status,
        }
    result = ProviderResult(
        provider=provider,
        request_id=f"req-{provider}",
        status=resolved_status,  # type: ignore[arg-type]
        started_at=_NOW,
        finished_at=_NOW,
        **result_kwargs,
    )
    return LiteratureBundle(
        papers=selected,
        provider_results=[result],
        coverage=CoverageReport(),
        metrics=RetrievalMetrics(rounds=1, provider_calls=1),
    )


class RecordingService:
    def __init__(self, bundles: dict[str, LiteratureBundle]) -> None:
        self.provider_names = tuple(bundles)
        self._bundles = bundles
        self.calls: list[str] = []

    async def retrieve(self, plan: Any) -> LiteratureBundle:
        provider = plan.query_lanes[0].source_preferences[0]
        self.calls.append(provider)
        return self._bundles[provider]


def _adapter(service: RecordingService) -> LiteratureSearchAdapter:
    return LiteratureSearchAdapter(
        service=cast(LiteratureRetrievalService, service),
        source_preferences=["openalex", "semantic_scholar"],
        supplement_source_preferences=["arxiv"],
        fallback_source_preferences=["tavily", "duckduckgo"],
    )


@pytest.mark.asyncio
async def test_no_configured_academic_provider_fails_closed() -> None:
    service = RecordingService({"tavily": _bundle("tavily")})
    adapter = _adapter(service)

    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(
            query=_query("lightweight UAV small object detection VisDrone latency"),
            scenario="live",
            call_index=0,
            fixture_version="v1",
            limit=5,
        )

    assert exc_info.value.code == "NO_ACADEMIC_PROVIDER"
    assert service.calls == []


@pytest.mark.asyncio
async def test_all_attempted_academic_provider_failures_are_reported() -> None:
    service = RecordingService(
        {
            provider: _bundle(provider, status="failed")
            for provider in ("openalex", "semantic_scholar", "arxiv")
        }
    )
    adapter = _adapter(service)

    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(
            query=_query(
                "lightweight UAV small object detection VisDrone latency",
                source_types=["paper"],
            ),
            scenario="live",
            call_index=0,
            fixture_version="v1",
            limit=5,
        )

    assert exc_info.value.code == "ALL_LITERATURE_PROVIDERS_FAILED"
    assert service.calls == ["openalex", "semantic_scholar", "arxiv"]
    diagnostics = adapter.last_query_diagnostics("q-edge")
    assert diagnostics["stop_reason"] == "all_attempted_providers_failed"


@pytest.mark.asyncio
async def test_relevant_web_supplement_is_returned_only_after_academic_insufficiency() -> None:
    web_paper = _paper("tavily", verified=False)
    service = RecordingService(
        {
            "openalex": _bundle("openalex"),
            "semantic_scholar": _bundle("semantic_scholar"),
            "arxiv": _bundle("arxiv"),
            "tavily": _bundle("tavily", [web_paper]),
            "duckduckgo": _bundle("duckduckgo"),
        }
    )
    adapter = _adapter(service)

    candidates = await adapter.search(
        query=_query("lightweight UAV small object detection VisDrone latency"),
        scenario="live",
        call_index=0,
        fixture_version="v1",
        limit=5,
    )

    assert service.calls == ["openalex", "semantic_scholar", "arxiv", "tavily"]
    assert len(candidates) == 1
    assert candidates[0].metadata["source_kind"] == "web"
    assert candidates[0].metadata["fallback_used"] == "true"
    assert candidates[0].metadata["web_supplement"] == "true"
    diagnostics = adapter.last_query_diagnostics("q-edge")
    assert diagnostics["stop_reason"] == "relevant_web_supplement_found"


@pytest.mark.asyncio
async def test_provider_call_ceiling_stops_before_second_web_source() -> None:
    service = RecordingService(
        {
            "openalex": _bundle("openalex"),
            "semantic_scholar": _bundle("semantic_scholar"),
            "arxiv": _bundle("arxiv"),
            "tavily": _bundle("tavily"),
            "duckduckgo": _bundle("duckduckgo", [_paper("duckduckgo", verified=False)]),
        }
    )
    adapter = _adapter(service)

    candidates = await adapter.search(
        query=_query("lightweight UAV small object detection VisDrone latency"),
        scenario="live",
        call_index=0,
        fixture_version="v1",
        limit=5,
    )

    assert candidates == []
    assert service.calls == ["openalex", "semantic_scholar", "arxiv", "tavily"]
    diagnostics = adapter.last_query_diagnostics("q-edge")
    assert diagnostics["stop_reason"] == "provider_call_budget_exhausted"


def test_merge_prefers_verified_richer_and_higher_rank_record() -> None:
    first = _paper(
        "openalex",
        paper_id="same",
        verified=False,
        relevance=0.5,
        score=0.55,
        abstract="short",
    )
    second = _paper(
        "semantic_scholar",
        paper_id="same",
        verified=True,
        relevance=0.9,
        score=0.91,
        abstract="a substantially longer abstract",
    ).model_copy(update={"matched_gap_ids": ["gap-two"]})
    papers = {first.paper_id: first}

    LiteratureSearchAdapter._merge_papers(papers, [second])

    merged = papers["same"]
    assert merged.verification_status == "verified"
    assert merged.abstract == "a substantially longer abstract"
    assert len(merged.source_records) == 2
    assert merged.matched_gap_ids == ["gap-edge", "gap-two"]
    assert merged.rank_features is not None
    assert merged.rank_features.score == 0.91


def test_low_quality_record_is_filtered_and_source_kinds_are_distinct() -> None:
    policy = review_search_query(
        _query("lightweight UAV small object detection VisDrone latency")
    )
    assert not LiteratureSearchAdapter._passes_return_relevance(
        PaperRecord(paper_id="no-rank", canonical_title="No rank"),
        policy,
    )
    assert LiteratureSearchAdapter._source_kind({"tavily"}) == "web"
    assert LiteratureSearchAdapter._source_kind({"openalex", "tavily"}) == "academic+web"
    assert LiteratureSearchAdapter._source_kind({"openalex"}) == "academic"


def test_query_policy_covers_identifier_recent_cjk_and_rejection_paths() -> None:
    exact = review_search_query(_query("arxiv:2401.12345", source_types=["paper"]))
    recent = review_search_query(
        _query("recent UAV detector benchmark 2026", source_types=["paper"])
    )
    cjk = review_search_query(
        _query("无人机小目标检测轻量化方法评估", source_types=["paper"])
    )
    empty = review_search_query(_query(" ", source_types=["paper"]))
    too_long = review_search_query(_query("specific " * 40, source_types=["paper"]))

    assert exact.primary_provider == "arxiv"
    assert exact.minimum_relevant_results == 1
    assert recent.primary_provider == "arxiv"
    assert cjk.approved
    assert cjk.precision_risk == "low"
    assert not empty.approved
    assert not too_long.approved

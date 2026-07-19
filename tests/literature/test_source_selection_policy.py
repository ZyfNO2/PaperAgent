from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

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


def _query(value: str, *, source_types: list[str] | None = None) -> SearchQuery:
    return SearchQuery(
        query_id="q-1",
        gap_id="gap-1",
        query=value,
        source_types=source_types or ["paper", "web"],
    )


def _paper(
    provider: str,
    *,
    paper_id: str,
    relevance: float,
    score: float,
    verified: bool,
) -> PaperRecord:
    return PaperRecord(
        paper_id=paper_id,
        canonical_title="Lightweight UAV small object detection on VisDrone",
        authors=["Researcher"],
        year=2025,
        abstract="Lightweight UAV detector for small objects on VisDrone with latency evaluation.",
        doi=f"10.1234/{paper_id}" if verified else None,
        urls=[f"https://example.org/{paper_id}"],
        source_records=[
            SourceRecord(
                provider=provider,
                provider_record_id=f"{provider}-{paper_id}",
                request_id=f"req-{provider}",
            )
        ],
        verification_status="verified" if verified else "pending",
        matched_gap_ids=["gap-1"],
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


def _bundle(provider: str, papers: list[PaperRecord]) -> LiteratureBundle:
    now = datetime.now(UTC)
    result = ProviderResult(
        provider=provider,
        request_id=f"req-{provider}",
        status="success" if papers else "empty",
        papers=[],
        started_at=now,
        finished_at=now,
    )
    return LiteratureBundle(
        papers=papers,
        provider_results=[result],
        coverage=CoverageReport(),
        metrics=RetrievalMetrics(rounds=1, provider_calls=1),
    )


class RecordingService:
    def __init__(self, bundles: dict[str, LiteratureBundle]) -> None:
        self.provider_names = tuple(bundles)
        self._bundles = bundles
        self.calls: list[str] = []

    async def retrieve(self, plan: object) -> LiteratureBundle:
        lane = plan.query_lanes[0]
        provider = lane.source_preferences[0]
        self.calls.append(provider)
        return self._bundles[provider]


def _adapter(service: RecordingService) -> LiteratureSearchAdapter:
    return LiteratureSearchAdapter(
        service=cast(LiteratureRetrievalService, service),
        source_preferences=["openalex", "semantic_scholar"],
        supplement_source_preferences=["arxiv"],
        fallback_source_preferences=["tavily", "duckduckgo"],
    )


def test_generic_query_is_rejected_before_any_provider_call() -> None:
    service = RecordingService({"openalex": _bundle("openalex", [])})
    adapter = _adapter(service)

    with pytest.raises(ProviderError) as exc_info:
        pytest.run(async_fn=adapter.search)(
            query=_query("deep learning"),
            scenario="live",
            call_index=0,
            fixture_version="v0.1",
            limit=10,
        )

    assert exc_info.value.code == "QUERY_TOO_BROAD"
    assert service.calls == []
    diagnostics = adapter.last_query_diagnostics("q-1")
    assert diagnostics["query_approved"] is False
    assert diagnostics["stop_reason"] == "query_rejected_before_provider_use"


@pytest.mark.asyncio
async def test_specific_query_stops_after_one_successful_academic_source() -> None:
    strong = _paper("openalex", paper_id="oa-1", relevance=0.8, score=0.84, verified=True)
    service = RecordingService(
        {
            "openalex": _bundle("openalex", [strong, strong.model_copy(update={"paper_id": "oa-2"})]),
            "semantic_scholar": _bundle("semantic_scholar", []),
            "arxiv": _bundle("arxiv", []),
            "tavily": _bundle("tavily", []),
        }
    )
    adapter = _adapter(service)

    results = await adapter.search(
        query=_query("lightweight UAV small object detection VisDrone AP_small latency"),
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        limit=10,
    )

    assert len(results) == 2
    assert service.calls == ["openalex"]
    diagnostics = adapter.last_query_diagnostics("q-1")
    assert diagnostics["provider_call_count"] == 1
    assert diagnostics["stop_reason"] == "sufficient_academic_evidence"


@pytest.mark.asyncio
async def test_low_quality_first_source_escalates_only_until_threshold_is_met() -> None:
    weak = _paper("openalex", paper_id="oa-weak", relevance=0.1, score=0.4, verified=False)
    strong = _paper(
        "semantic_scholar",
        paper_id="s2-1",
        relevance=0.8,
        score=0.84,
        verified=True,
    )
    service = RecordingService(
        {
            "openalex": _bundle("openalex", [weak]),
            "semantic_scholar": _bundle(
                "semantic_scholar",
                [strong, strong.model_copy(update={"paper_id": "s2-2"})],
            ),
            "arxiv": _bundle("arxiv", []),
            "tavily": _bundle("tavily", []),
        }
    )
    adapter = _adapter(service)

    results = await adapter.search(
        query=_query("lightweight UAV small object detection VisDrone AP_small latency"),
        scenario="live",
        call_index=0,
        fixture_version="v0.1",
        limit=10,
    )

    assert [item.title for item in results]
    assert service.calls == ["openalex", "semantic_scholar"]
    assert "arxiv" not in service.calls
    assert "tavily" not in service.calls


def test_web_fallback_requires_low_precision_risk_and_explicit_web_scope() -> None:
    medium = review_search_query(
        _query("UAV small object detection", source_types=["paper", "web"])
    )
    paper_only = review_search_query(
        _query(
            "lightweight UAV small object detection VisDrone AP_small latency",
            source_types=["paper"],
        )
    )
    precise = review_search_query(
        _query("lightweight UAV small object detection VisDrone AP_small latency")
    )

    assert medium.allow_web_fallback is False
    assert paper_only.allow_web_fallback is False
    assert precise.allow_web_fallback is True
    assert precise.maximum_provider_calls == 4

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from paperagent.literature.cache import CacheKey, InMemoryProviderCache
from paperagent.literature.service import (
    DeterministicFocusedQueryRewriter,
    LiteratureRetrievalService,
)
from paperagent.literature.verification import VerificationService
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


@dataclass
class FakeProvider:
    provider_name: str
    results: list[ProviderResult]
    contract_version: str = "test-v1"
    delay: float = 0
    calls: int = 0

    async def search(self, *, lane, filters, limit):
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        index = min(self.calls - 1, len(self.results) - 1)
        result = self.results[index]
        papers = [
            paper.model_copy(
                update={
                    "matched_gap_ids": list(lane.gap_ids),
                    "source_lane_ids": [lane.lane_id],
                }
            )
            for paper in result.papers[:limit]
        ]
        return result.model_copy(update={"papers": papers})


def provider_result(provider: str, status: str, papers: list[ProviderPaper] | None = None):
    kwargs = {}
    if status in {"failed", "timeout", "rate_limited"}:
        kwargs = {"error_code": status.upper(), "error_message": status}
    return ProviderResult(
        provider=provider,
        request_id=f"req-{provider}-{status}",
        status=status,
        papers=papers or [],
        started_at=NOW,
        finished_at=NOW,
        **kwargs,
    )


def plan(*, gaps: list[str] | None = None) -> LiteratureQueryPlan:
    gap_ids = gaps or ["g1"]
    return LiteratureQueryPlan(
        question="reliable retrieval methods",
        scope="IR",
        required_gap_ids=gap_ids,
        query_lanes=[
            QueryLane(
                lane_id="l1",
                purpose="method",
                query="reliable retrieval methods",
                gap_ids=[gap_ids[0]],
                source_preferences=["openalex", "arxiv"],
            )
        ],
    )


def paper(identifier: str, title: str = "Reliable Retrieval") -> ProviderPaper:
    return ProviderPaper(
        provider_record_id=identifier,
        title=title,
        authors=["Jane Doe"],
        year=2024,
        arxiv_id=f"2401.{identifier.zfill(5)}" if identifier.isdigit() else None,
    )


def test_cache_failure_does_not_poison_and_empty_uses_short_ttl() -> None:
    now = [0.0]
    cache = InMemoryProviderCache(clock=lambda: now[0], success_ttl=100, empty_ttl=5)
    key = CacheKey(
        normalized_query="q",
        provider="p",
        filters="{}",
        limit=10,
        provider_contract_version="v1",
    )
    failed = provider_result("p", "failed")
    cache.set(key, failed)
    assert cache.get(key) is None

    empty = provider_result("p", "empty")
    cache.set(key, empty)
    assert cache.get(key) is not None
    now[0] = 6
    assert cache.get(key) is None


@pytest.mark.asyncio
async def test_service_partial_failure_still_returns_explainable_papers() -> None:
    openalex = FakeProvider("openalex", [provider_result("openalex", "success", [paper("1")])])
    arxiv = FakeProvider("arxiv", [provider_result("arxiv", "timeout")])
    service = LiteratureRetrievalService(
        providers=[openalex, arxiv],
        verifier=VerificationService([]),
    )
    bundle = await service.retrieve(plan())
    assert len(bundle.papers) == 1
    assert {result.status for result in bundle.provider_results} == {"success", "timeout"}
    assert bundle.coverage.retry_recommendation == "none"


@pytest.mark.asyncio
async def test_all_sources_fail_is_blocked_and_creates_no_paper() -> None:
    service = LiteratureRetrievalService(
        providers=[
            FakeProvider("openalex", [provider_result("openalex", "failed")]),
            FakeProvider("arxiv", [provider_result("arxiv", "timeout")]),
        ],
        verifier=VerificationService([]),
    )
    bundle = await service.retrieve(plan())
    assert bundle.papers == []
    assert bundle.coverage.retry_recommendation == "blocked"


@pytest.mark.asyncio
async def test_success_cache_hit_avoids_second_provider_call() -> None:
    provider = FakeProvider("openalex", [provider_result("openalex", "success", [paper("1")])])
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        cache=InMemoryProviderCache(),
    )
    single_plan = plan()
    await service.retrieve(single_plan)
    second = await service.retrieve(single_plan)
    assert provider.calls == 1
    assert second.metrics.cache_hits == 1
    assert second.provider_results[0].cache_status == "hit"


@pytest.mark.asyncio
async def test_concurrent_identical_requests_are_coalesced() -> None:
    provider = FakeProvider(
        "openalex",
        [provider_result("openalex", "success", [paper("1")])],
        delay=0.02,
    )
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        cache=InMemoryProviderCache(),
    )
    first, second = await asyncio.gather(service.retrieve(plan()), service.retrieve(plan()))
    assert provider.calls == 1
    assert first.papers[0].paper_id == second.papers[0].paper_id
    assert any(
        result.cache_status == "coalesced"
        for bundle in (first, second)
        for result in bundle.provider_results
    )


@pytest.mark.asyncio
async def test_uncovered_gap_triggers_only_one_focused_retry() -> None:
    openalex = FakeProvider(
        "openalex",
        [
            provider_result("openalex", "success", [paper("1")]),
            provider_result("openalex", "empty"),
            provider_result("openalex", "success", [paper("2", "Failure Analysis")]),
        ],
    )
    arxiv = FakeProvider(
        "arxiv",
        [
            provider_result("arxiv", "empty"),
            provider_result("arxiv", "empty"),
            provider_result("arxiv", "empty"),
        ],
    )
    two_gap_plan = LiteratureQueryPlan(
        question="reliable retrieval methods and failures",
        scope="IR",
        required_gap_ids=["method", "failure"],
        query_lanes=[
            QueryLane(
                lane_id="l1",
                purpose="method",
                query="retrieval methods",
                gap_ids=["method"],
                source_preferences=["openalex", "arxiv"],
            ),
            QueryLane(
                lane_id="l2",
                purpose="limitation_failure",
                query="retrieval failure analysis",
                gap_ids=["failure"],
                source_preferences=["openalex", "arxiv"],
            ),
        ],
    )
    service = LiteratureRetrievalService(
        providers=[openalex, arxiv],
        verifier=VerificationService([]),
        rewriter=DeterministicFocusedQueryRewriter(),
    )
    bundle = await service.retrieve(two_gap_plan)
    assert bundle.metrics.rounds == 2
    assert bundle.metrics.query_rewrite_calls == 1
    assert bundle.coverage.retry_recommendation == "none"
    assert bundle.coverage.gap_coverage == {"failure": 1, "method": 1}


@pytest.mark.asyncio
async def test_first_round_enough_does_not_rewrite_query() -> None:
    provider = FakeProvider("openalex", [provider_result("openalex", "success", [paper("1")])])
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        rewriter=DeterministicFocusedQueryRewriter(),
    )
    bundle = await service.retrieve(plan())
    assert bundle.metrics.rounds == 1
    assert bundle.metrics.query_rewrite_calls == 0

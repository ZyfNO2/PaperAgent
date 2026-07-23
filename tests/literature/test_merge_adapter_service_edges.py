from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from literature_fixtures import provider_result
from paperagent.literature.adapter import LiteratureSearchAdapter
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.service import (
    DeterministicFocusedQueryRewriter,
    LiteratureRetrievalService,
)
from paperagent.literature.verification import VerificationService
from paperagent.schemas import SearchQuery
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)


@dataclass
class RecordingProvider:
    provider_name: str
    result: ProviderResult
    contract_version: str = "test-v1"
    delay: float = 0.0
    calls: int = 0
    limits: list[int] | None = None

    async def search(self, *, lane, filters, limit):
        del filters
        self.calls += 1
        if self.limits is not None:
            self.limits.append(limit)
        if self.delay:
            await asyncio.sleep(self.delay)
        papers = [
            paper.model_copy(
                update={
                    "matched_gap_ids": list(lane.gap_ids),
                    "source_lane_ids": [lane.lane_id],
                }
            )
            for paper in self.result.papers[:limit]
        ]
        return self.result.model_copy(update={"papers": papers})


def plan(*, preferences: list[str] | None = None, max_rounds: int = 2) -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question="retrieval method",
        scope="IR",
        required_gap_ids=["g"],
        query_lanes=[
            QueryLane(
                lane_id="l",
                purpose="method",
                query="retrieval method",
                source_preferences=preferences or [],
                gap_ids=["g"],
            )
        ],
        max_rounds=max_rounds,
    )


def raw(identifier: str, **updates: object) -> ProviderPaper:
    values: dict[str, object] = {
        "provider_record_id": identifier,
        "title": f"Paper {identifier}",
        "authors": ["Jane Doe"],
        "year": 2024,
    }
    values.update(updates)
    return ProviderPaper(**values)


def test_merge_respects_candidate_limit() -> None:
    papers = [raw(str(index)) for index in range(5)]
    merged = merge_provider_results(
        [provider_result("openalex", "success", papers)], candidate_limit=2
    )
    assert len(merged) == 2


def test_approximate_title_merge_is_marked_suspicious() -> None:
    first = raw("a", title="Reliable Retrieval Systems", doi=None)
    second = raw("b", title="Reliable Retrieval System", doi=None, year=2025)
    merged = merge_provider_results(
        [
            provider_result("openalex", "success", [first]),
            provider_result("arxiv", "success", [second]),
        ]
    )
    assert len(merged) == 1
    assert merged[0].verification_status == "suspicious"
    assert "APPROXIMATE_TITLE_MATCH" in {warning.code for warning in merged[0].merge_warnings}


def test_author_conflict_is_preserved_as_warning() -> None:
    first = raw("a", doi="10.1/x", authors=["Jane Doe"])
    second = raw("b", doi="10.1/x", authors=["Jane Doe", "John Roe"])
    merged = merge_provider_results(
        [
            provider_result("openalex", "success", [first]),
            provider_result("semantic_scholar", "success", [second]),
        ]
    )
    assert "AUTHOR_CONFLICT" in {warning.code for warning in merged[0].merge_warnings}
    assert merged[0].authors == ["Jane Doe", "John Roe"]


def test_arxiv_versions_merge_to_canonical_identifier() -> None:
    first = raw("a", arxiv_id="2401.12345v1")
    second = raw("b", arxiv_id="https://arxiv.org/abs/2401.12345v3")
    merged = merge_provider_results(
        [
            provider_result("arxiv", "success", [first]),
            provider_result("openalex", "success", [second]),
        ]
    )
    assert len(merged) == 1
    assert merged[0].arxiv_id == "2401.12345"


@pytest.mark.asyncio
async def test_service_with_no_configured_provider_is_blocked() -> None:
    bundle = await LiteratureRetrievalService(
        providers=[], verifier=VerificationService([])
    ).retrieve(plan())
    assert bundle.papers == []
    assert bundle.coverage.retry_recommendation == "blocked"


@pytest.mark.asyncio
async def test_round_deadline_returns_explicit_timeout() -> None:
    provider = RecordingProvider(
        "slow",
        provider_result("slow", "success", [raw("1", arxiv_id="2401.12345")]),
        delay=0.05,
    )
    bundle = await LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        total_deadline_seconds=0.001,
    ).retrieve(plan(preferences=["slow"], max_rounds=1))
    assert bundle.provider_results[0].status == "timeout"
    assert bundle.provider_results[0].error_code == "ROUND_DEADLINE"
    assert bundle.coverage.retry_recommendation == "blocked"


@pytest.mark.asyncio
async def test_router_uses_only_first_two_providers_and_caps_limit() -> None:
    limits: list[int] = []
    providers = [
        RecordingProvider(
            name,
            provider_result(name, "empty"),
            limits=limits,
        )
        for name in ("one", "two", "three")
    ]
    bundle = await LiteratureRetrievalService(
        providers=providers,
        verifier=VerificationService([]),
        results_per_request=100,
        providers_per_lane=10,
    ).retrieve(plan(max_rounds=1))
    assert [result.provider for result in bundle.provider_results] == ["one", "two"]
    assert limits == [100, 100]


@pytest.mark.asyncio
async def test_second_round_insufficient_marks_budget_exhausted() -> None:
    provider = RecordingProvider("openalex", provider_result("openalex", "empty"))
    bundle = await LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        rewriter=DeterministicFocusedQueryRewriter(),
    ).retrieve(plan(preferences=["openalex"]))
    assert bundle.metrics.rounds == 2
    assert bundle.coverage.retry_recommendation == "budget_exhausted"


def test_adapter_locator_precedence_and_pending_fallback() -> None:
    assert LiteratureSearchAdapter._locator("10.1/x", "2401.1", ["https://x"]) == "doi:10.1/x"
    assert (
        LiteratureSearchAdapter._locator(None, "2401.12345", ["https://x"])
        == "https://arxiv.org/abs/2401.12345"
    )
    assert LiteratureSearchAdapter._locator(None, None, ["https://x"]) == "https://x"
    assert LiteratureSearchAdapter._locator(None, None, []) == "literature://pending"


@pytest.mark.asyncio
async def test_adapter_verified_empty_returns_no_candidates_without_error() -> None:
    provider = RecordingProvider("openalex", provider_result("openalex", "empty"))
    adapter = LiteratureSearchAdapter(
        service=LiteratureRetrievalService(providers=[provider], verifier=VerificationService([])),
        source_preferences=["openalex"],
    )
    candidates = await adapter.search(
        query=SearchQuery(query_id="q", gap_id="g", query="retrieval method"),
        scenario="ignored",
        call_index=0,
        fixture_version="v0.2",
        limit=10,
    )
    assert candidates == []
    assert adapter.last_provider_results("q")[0].status == "empty"

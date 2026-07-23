from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from paperagent.literature.cache import (
    CacheKey,
    InMemoryProviderCache,
    JsonFixtureProviderCache,
    SQLiteProviderCache,
)
from paperagent.literature.providers.base import HTTPResponse, http_failure_result, parse_retry_at
from paperagent.literature.resilience import ProviderCircuitBreaker, ProviderCircuitPolicy
from paperagent.literature.service import LiteratureRetrievalService
from paperagent.literature.verification import VerificationService
from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def cache_key() -> CacheKey:
    return CacheKey(
        normalized_query="reliable retrieval",
        provider="openalex",
        filters="{}",
        limit=10,
        provider_contract_version="test-v1",
    )


def paper() -> ProviderPaper:
    return ProviderPaper(
        provider_record_id="W1",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2025,
        arxiv_id="2501.00001",
    )


def result(status: str, *, error_code: str | None = None) -> ProviderResult:
    return ProviderResult(
        provider="openalex",
        request_id=f"req-{status}",
        status=status,
        papers=[paper()] if status == "success" else [],
        started_at=NOW,
        finished_at=NOW,
        error_code=error_code,
        error_message=error_code,
    )


def plan() -> LiteratureQueryPlan:
    return LiteratureQueryPlan(
        question="reliable retrieval methods",
        scope="IR",
        required_gap_ids=["g1"],
        query_lanes=[
            QueryLane(
                lane_id="l1",
                purpose="method",
                query="reliable retrieval methods",
                source_preferences=["openalex"],
                gap_ids=["g1"],
            )
        ],
    )


@dataclass
class SequencedProvider:
    results: list[ProviderResult]
    provider_name: str = "openalex"
    contract_version: str = "test-v1"
    calls: int = 0

    async def search(self, *, lane, filters, limit):
        del filters
        selected = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return selected.model_copy(
            update={
                "papers": [
                    item.model_copy(
                        update={
                            "matched_gap_ids": list(lane.gap_ids),
                            "source_lane_ids": [lane.lane_id],
                        }
                    )
                    for item in selected.papers[:limit]
                ]
            }
        )


def test_sqlite_cache_survives_process_restart(tmp_path) -> None:
    path = tmp_path / "retrieval.sqlite3"
    first = SQLiteProviderCache(path)
    first.set(cache_key(), result("success"))
    first.close()

    second = SQLiteProviderCache(path)
    cached = second.get(cache_key())
    second.close()

    assert cached is not None
    assert cached.status == "success"
    assert cached.cached_at is not None


def test_json_fixture_cache_records_manifest_and_replays(tmp_path) -> None:
    writer = JsonFixtureProviderCache(tmp_path, writable=True)
    writer.set(cache_key(), result("success"))

    reader = JsonFixtureProviderCache(tmp_path)
    cached = reader.get(cache_key())

    assert cached is not None
    assert cached.papers[0].title == "Reliable Retrieval"
    assert (tmp_path / "manifest.json").is_file()


def test_negative_cache_suppresses_repeated_rate_limit_until_expiry() -> None:
    now = [100.0]
    cache = InMemoryProviderCache(
        clock=lambda: now[0],
        rate_limit_ttl=60,
    )
    limited = result("rate_limited", error_code="RATE_LIMITED")
    cache.set(cache_key(), limited)

    assert cache.get(cache_key()) is not None
    now[0] += 61
    assert cache.get(cache_key()) is None


def test_rate_limit_headers_distinguish_retry_and_daily_quota() -> None:
    retry_at = parse_retry_at({"Retry-After": "120"}, now=NOW)
    assert retry_at == NOW + timedelta(seconds=120)

    quota = http_failure_result(
        provider="openalex",
        request_id="r1",
        started_at=NOW,
        response=HTTPResponse(
            429,
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "3600"},
            {},
            "",
        ),
    )
    assert quota is not None
    assert quota.error_code == "DAILY_QUOTA_EXHAUSTED"
    assert quota.rate_limit_remaining == 0
    assert quota.retry_at is not None


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_two_timeouts() -> None:
    now = [NOW]
    breaker = ProviderCircuitBreaker(
        {
            "arxiv": ProviderCircuitPolicy(
                timeout_failures=2,
                failure_cooldown_seconds=600,
            )
        },
        now=lambda: now[0],
    )
    timeout = ProviderResult(
        provider="arxiv",
        request_id="timeout",
        status="timeout",
        started_at=NOW,
        finished_at=NOW,
        error_code="CONNECTION_TIMEOUT",
        error_message="timeout",
    )

    await breaker.record("arxiv", timeout)
    assert await breaker.before_call("arxiv") is None
    await breaker.record("arxiv", timeout)

    blocked_until = await breaker.before_call("arxiv")
    assert blocked_until == NOW + timedelta(seconds=600)


@pytest.mark.asyncio
async def test_stale_success_is_used_when_live_provider_times_out() -> None:
    now = [100.0]
    provider = SequencedProvider(
        [
            result("success"),
            result("timeout", error_code="CONNECTION_TIMEOUT"),
        ]
    )
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([]),
        cache=InMemoryProviderCache(
            clock=lambda: now[0],
            success_ttl=5,
            timeout_ttl=60,
        ),
        stale_cache_max_age_seconds=60,
    )

    first = await service.retrieve(plan())
    now[0] += 6
    second = await service.retrieve(plan())

    assert first.provider_results[0].cache_status == "miss"
    assert provider.calls == 2
    assert second.provider_results[0].cache_status == "stale_hit"
    assert second.provider_results[0].retrieval_mode == "stale_cache"
    assert second.provider_results[0].live_error_code == "CONNECTION_TIMEOUT"
    assert second.papers


@pytest.mark.asyncio
async def test_offline_mode_never_calls_provider_on_cache_miss() -> None:
    provider = SequencedProvider([result("success")])
    service = LiteratureRetrievalService(
        providers=[provider],
        verifier=VerificationService([], mode="offline"),
        cache=InMemoryProviderCache(),
        retrieval_mode="offline",
    )

    bundle = await service.retrieve(plan())

    assert provider.calls == 0
    assert bundle.provider_results[0].error_code == "OFFLINE_CACHE_MISS"
    assert bundle.metrics.provider_calls == 0

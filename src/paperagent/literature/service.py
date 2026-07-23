from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

from paperagent.literature.cache import CacheKey, ProviderCache
from paperagent.literature.coverage import audit_coverage
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.normalize import normalized_text
from paperagent.literature.providers.base import LiteratureProvider, make_request_id, utc_now
from paperagent.literature.ranking import rank_papers
from paperagent.literature.resilience import ProviderCircuitBreaker
from paperagent.literature.verification import VerificationService
from paperagent.providers.request_rate_limit import shared_request_rate_limiter
from paperagent.schemas.literature import (
    CoverageReport,
    LiteratureBundle,
    LiteratureFilters,
    LiteratureQueryPlan,
    PaperRecord,
    ProviderResult,
    QueryLane,
    RetrievalMetrics,
)

RetrievalMode = Literal["offline", "cache_first", "live"]


class FocusedQueryRewriter(Protocol):
    async def rewrite(
        self,
        plan: LiteratureQueryPlan,
        coverage: CoverageReport,
    ) -> list[QueryLane]: ...


class DeterministicFocusedQueryRewriter:
    async def rewrite(
        self,
        plan: LiteratureQueryPlan,
        coverage: CoverageReport,
    ) -> list[QueryLane]:
        output: list[QueryLane] = []
        for gap_id in coverage.uncovered_gap_ids:
            original = next(
                (lane for lane in plan.query_lanes if gap_id in lane.gap_ids),
                plan.query_lanes[0],
            )
            output.append(
                QueryLane(
                    lane_id=f"retry-{gap_id}",
                    purpose=original.purpose,
                    query=f"{original.query} {gap_id} evidence limitations benchmark",
                    source_preferences=list(original.source_preferences),
                    gap_ids=[gap_id],
                    priority=100,
                )
            )
        return output[:4]


@dataclass(frozen=True)
class _ProviderCall:
    provider: LiteratureProvider
    lane: QueryLane


class LiteratureRetrievalService:
    def __init__(
        self,
        *,
        providers: Sequence[LiteratureProvider],
        verifier: VerificationService,
        cache: ProviderCache | None = None,
        rewriter: FocusedQueryRewriter | None = None,
        total_deadline_seconds: float = 25.0,
        providers_per_lane: int = 2,
        results_per_request: int = 10,
        candidate_limit: int = 30,
        final_limit: int = 12,
        provider_concurrency: int | Mapping[str, int] = 2,
        request_rates_per_minute: Mapping[str, int] | None = None,
        circuit_breaker: ProviderCircuitBreaker | None = None,
        retrieval_mode: RetrievalMode = "cache_first",
        stale_cache_max_age_seconds: float = 30 * 24 * 60 * 60,
        max_provider_calls: int | None = 48,
    ) -> None:
        if max_provider_calls is not None and max_provider_calls < 1:
            raise ValueError("max_provider_calls must be positive or None")
        if retrieval_mode not in {"offline", "cache_first", "live"}:
            raise ValueError("retrieval_mode must be offline, cache_first, or live")
        if stale_cache_max_age_seconds < 0:
            raise ValueError("stale_cache_max_age_seconds must be non-negative")
        self._providers = {provider.provider_name: provider for provider in providers}
        self._provider_order = [provider.provider_name for provider in providers]
        self._verifier = verifier
        self._cache = cache
        self._rewriter = rewriter
        self._deadline = total_deadline_seconds
        self._providers_per_lane = min(2, providers_per_lane)
        self._results_per_request = min(100, results_per_request)
        self._candidate_limit = min(30, candidate_limit)
        self._final_limit = min(12, final_limit)
        concurrency_by_provider = (
            dict(provider_concurrency)
            if isinstance(provider_concurrency, Mapping)
            else {name: provider_concurrency for name in self._providers}
        )
        self._semaphores = {
            name: asyncio.Semaphore(max(1, concurrency_by_provider.get(name, 1)))
            for name in self._providers
        }
        self._request_rates_per_minute = dict(request_rates_per_minute or {})
        self._circuit_breaker = circuit_breaker or ProviderCircuitBreaker()
        self._retrieval_mode = retrieval_mode
        self._stale_cache_max_age_seconds = stale_cache_max_age_seconds
        self._inflight: dict[CacheKey, asyncio.Task[ProviderResult]] = {}
        self._inflight_lock = asyncio.Lock()
        self._max_provider_calls = max_provider_calls
        self._provider_calls_started = 0
        self._provider_call_budget_lock = asyncio.Lock()

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(self._provider_order)

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()
        self._verifier.close()

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return self._retrieval_mode

    def provider_call_budget(self) -> dict[str, int | None]:
        maximum = self._max_provider_calls
        return {
            "maximum": maximum,
            "used": self._provider_calls_started,
            "remaining": (
                None if maximum is None else max(0, maximum - self._provider_calls_started)
            ),
        }

    async def retrieve(self, plan: LiteratureQueryPlan) -> LiteratureBundle:
        first_results = await self._execute_lanes(plan.query_lanes, plan.filters)
        papers, coverage = await self._assemble(first_results, plan, round_number=1)
        all_results = list(first_results)
        rounds = 1
        rewrite_calls = 0
        if (
            plan.max_rounds > 1
            and coverage.retry_recommendation == "focused_retry"
            and self._rewriter is not None
        ):
            retry_lanes = await self._rewriter.rewrite(plan, coverage)
            rewrite_calls = 1
            if retry_lanes:
                second_results = await self._execute_lanes(retry_lanes, plan.filters)
                all_results.extend(second_results)
                rounds = 2
                papers, coverage = await self._assemble(all_results, plan, round_number=2)
        if not papers and (
            not all_results
            or all(result.status in {"failed", "timeout", "rate_limited"} for result in all_results)
        ):
            coverage = coverage.model_copy(update={"retry_recommendation": "blocked"})
        no_remote_call_codes = {
            "OFFLINE_CACHE_MISS",
            "PROVIDER_CALL_BUDGET_EXHAUSTED",
            "PROVIDER_CIRCUIT_OPEN",
        }
        metrics = RetrievalMetrics(
            rounds=rounds,
            provider_calls=sum(
                result.cache_status in {"miss", "bypass"}
                and result.error_code not in no_remote_call_codes
                for result in all_results
            ),
            query_rewrite_calls=rewrite_calls,
            cache_hits=sum(
                result.cache_status
                in {"hit", "stale_hit", "negative_hit", "offline_hit", "coalesced"}
                for result in all_results
            ),
        )
        return LiteratureBundle(
            papers=papers,
            provider_results=all_results,
            coverage=coverage,
            metrics=metrics,
        )

    async def _assemble(
        self,
        results: list[ProviderResult],
        plan: LiteratureQueryPlan,
        *,
        round_number: int,
    ) -> tuple[list[PaperRecord], CoverageReport]:
        merged = merge_provider_results(results, candidate_limit=self._candidate_limit)
        verified = await self._verifier.verify_all(merged)
        ranked = rank_papers(
            verified,
            plan,
            now_year=datetime.now(UTC).year,
            final_limit=self._final_limit,
        )
        return ranked, audit_coverage(ranked, plan, round_number=round_number)

    def _route(self, lane: QueryLane) -> list[LiteratureProvider]:
        preferred = [name for name in lane.source_preferences if name in self._providers]
        names = preferred or self._provider_order
        return [self._providers[name] for name in names[: self._providers_per_lane]]

    async def _execute_lanes(
        self,
        lanes: list[QueryLane],
        filters: LiteratureFilters,
    ) -> list[ProviderResult]:
        calls = [
            _ProviderCall(provider=provider, lane=lane)
            for lane in sorted(lanes, key=lambda item: (-item.priority, item.lane_id))
            for provider in self._route(lane)
        ]
        tasks = [asyncio.create_task(self._call_provider(call, filters)) for call in calls]
        if not tasks:
            return []
        done, pending = await asyncio.wait(tasks, timeout=self._deadline)
        results_by_task: dict[asyncio.Task[ProviderResult], ProviderResult] = {}
        for task in done:
            results_by_task[task] = task.result()
        for task in pending:
            task.cancel()
        results: list[ProviderResult] = []
        for call, task in zip(calls, tasks, strict=True):
            if task in results_by_task:
                results.append(results_by_task[task])
            else:
                now = utc_now()
                results.append(
                    ProviderResult(
                        provider=call.provider.provider_name,
                        request_id=make_request_id(
                            call.provider.provider_name,
                            call.lane,
                            filters,
                            self._results_per_request,
                        ),
                        status="timeout",
                        started_at=now,
                        finished_at=now,
                        error_code="ROUND_DEADLINE",
                        error_message="retrieval round deadline exceeded",
                    )
                )
        return results

    def _cache_key(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
    ) -> CacheKey:
        return CacheKey(
            normalized_query=normalized_text(lane.query),
            provider=provider.provider_name,
            filters=json.dumps(filters.model_dump(mode="json"), sort_keys=True),
            limit=self._results_per_request,
            provider_contract_version=provider.contract_version,
        )

    async def _reserve_provider_call(self) -> bool:
        async with self._provider_call_budget_lock:
            maximum = self._max_provider_calls
            if maximum is not None and self._provider_calls_started >= maximum:
                return False
            self._provider_calls_started += 1
            return True

    def _budget_exhausted_result(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        now = utc_now()
        return ProviderResult(
            provider=provider.provider_name,
            request_id=make_request_id(
                provider.provider_name,
                lane,
                filters,
                self._results_per_request,
            ),
            status="failed",
            started_at=now,
            finished_at=now,
            cache_status="bypass",
            error_code="PROVIDER_CALL_BUDGET_EXHAUSTED",
            error_message="task-level external provider call budget exhausted",
        )

    def _offline_miss_result(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        now = utc_now()
        return ProviderResult(
            provider=provider.provider_name,
            request_id=make_request_id(
                provider.provider_name,
                lane,
                filters,
                self._results_per_request,
            ),
            status="failed",
            started_at=now,
            finished_at=now,
            cache_status="bypass",
            retrieval_mode="offline_fixture",
            error_code="OFFLINE_CACHE_MISS",
            error_message="offline retrieval mode forbids a live provider request",
        )

    def _circuit_open_result(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
        retry_at: datetime,
    ) -> ProviderResult:
        now = utc_now()
        return ProviderResult(
            provider=provider.provider_name,
            request_id=make_request_id(
                provider.provider_name,
                lane,
                filters,
                self._results_per_request,
            ),
            status="rate_limited",
            started_at=now,
            finished_at=now,
            cache_status="bypass",
            retry_at=retry_at,
            error_code="PROVIDER_CIRCUIT_OPEN",
            error_message="provider circuit is open; live request skipped",
        )

    @staticmethod
    def _cached_copy(result: ProviderResult, *, offline: bool) -> ProviderResult:
        cache_status = (
            "negative_hit"
            if result.status in {"failed", "timeout", "rate_limited"}
            else ("offline_hit" if offline else "hit")
        )
        retrieval_mode = "offline_fixture" if offline else "cache"
        return result.model_copy(
            update={"cache_status": cache_status, "retrieval_mode": retrieval_mode}
        )

    def _stale_fallback(
        self,
        key: CacheKey,
        live_result: ProviderResult,
    ) -> ProviderResult | None:
        if self._cache is None or self._stale_cache_max_age_seconds <= 0:
            return None
        stale = self._cache.get_stale(key, max_stale_seconds=self._stale_cache_max_age_seconds)
        if stale is None or stale.status not in {"success", "empty"}:
            return None
        return stale.model_copy(
            update={
                "cache_status": "stale_hit",
                "retrieval_mode": "stale_cache",
                "live_error_code": live_result.error_code,
            }
        )

    async def _call_provider(
        self,
        call: _ProviderCall,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        provider = call.provider
        key = self._cache_key(provider, call.lane, filters)
        use_cache = self._cache is not None and self._retrieval_mode != "live"
        if use_cache:
            cached = self._cache.get(key)
            if cached is not None:
                return self._cached_copy(cached, offline=self._retrieval_mode == "offline")
        if self._retrieval_mode == "offline":
            return self._offline_miss_result(provider, call.lane, filters)
        cache = self._cache
        if cache is None:
            return await self._execute_live(provider, call.lane, filters, key)

        async with self._inflight_lock:
            cached = cache.get(key) if self._retrieval_mode != "live" else None
            if cached is not None:
                return self._cached_copy(cached, offline=False)
            task = self._inflight.get(key)
            owner = task is None
            if task is None:
                task = asyncio.create_task(self._execute_live(provider, call.lane, filters, key))
                self._inflight[key] = task
        try:
            result = await task
        finally:
            if owner:
                async with self._inflight_lock:
                    self._inflight.pop(key, None)
        if owner:
            return result
        return result.model_copy(update={"cache_status": "coalesced"})

    async def _execute_live(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
        key: CacheKey,
    ) -> ProviderResult:
        retry_at = await self._circuit_breaker.before_call(provider.provider_name)
        if retry_at is not None:
            blocked = self._circuit_open_result(provider, lane, filters, retry_at)
            return self._stale_fallback(key, blocked) or blocked
        if not await self._reserve_provider_call():
            return self._budget_exhausted_result(provider, lane, filters)
        result = await self._run_provider(provider, lane, filters)
        await self._circuit_breaker.record(provider.provider_name, result)
        stale = (
            self._stale_fallback(key, result)
            if result.status in {"failed", "timeout", "rate_limited"}
            else None
        )
        if stale is not None:
            return stale
        if self._cache is not None:
            self._cache.set(key, result)
        cache_status = "bypass" if self._retrieval_mode == "live" else "miss"
        return result.model_copy(update={"cache_status": cache_status, "retrieval_mode": "live"})

    async def _run_provider(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        async with self._semaphores[provider.provider_name]:
            requests_per_minute = self._request_rates_per_minute.get(provider.provider_name)
            if requests_per_minute is not None:
                limiter = shared_request_rate_limiter(
                    namespace=f"literature:{provider.provider_name}",
                    requests_per_minute=requests_per_minute,
                )
                await limiter.acquire()
            return await provider.search(
                lane=lane,
                filters=filters,
                limit=self._results_per_request,
            )

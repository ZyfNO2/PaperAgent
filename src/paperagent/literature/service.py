from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from paperagent.literature.cache import CacheKey, InMemoryProviderCache
from paperagent.literature.coverage import audit_coverage
from paperagent.literature.merge import merge_provider_results
from paperagent.literature.normalize import normalized_text
from paperagent.literature.providers.base import LiteratureProvider, make_request_id, utc_now
from paperagent.literature.ranking import rank_papers
from paperagent.literature.verification import VerificationService
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
        cache: InMemoryProviderCache | None = None,
        rewriter: FocusedQueryRewriter | None = None,
        total_deadline_seconds: float = 25.0,
        providers_per_lane: int = 2,
        results_per_request: int = 10,
        candidate_limit: int = 30,
        final_limit: int = 12,
        provider_concurrency: int = 2,
    ) -> None:
        self._providers = {provider.provider_name: provider for provider in providers}
        self._provider_order = [provider.provider_name for provider in providers]
        self._verifier = verifier
        self._cache = cache
        self._rewriter = rewriter
        self._deadline = total_deadline_seconds
        self._providers_per_lane = min(2, providers_per_lane)
        self._results_per_request = min(10, results_per_request)
        self._candidate_limit = min(30, candidate_limit)
        self._final_limit = min(12, final_limit)
        self._semaphores = {
            name: asyncio.Semaphore(provider_concurrency) for name in self._providers
        }
        self._inflight: dict[CacheKey, asyncio.Task[ProviderResult]] = {}
        self._inflight_lock = asyncio.Lock()

    @property
    def provider_names(self) -> tuple[str, ...]:
        return tuple(self._provider_order)

    async def retrieve(self, plan: LiteratureQueryPlan) -> LiteratureBundle:
        first_results = await self._execute_lanes(plan.query_lanes, plan.filters)
        papers, coverage = await self._assemble(first_results, plan, round_number=1)
        all_results = list(first_results)
        rounds = 1
        rewrite_calls = 0
        if coverage.retry_recommendation == "focused_retry" and self._rewriter is not None:
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
        metrics = RetrievalMetrics(
            rounds=rounds,
            provider_calls=sum(result.cache_status in {"miss", "bypass"} for result in all_results),
            query_rewrite_calls=rewrite_calls,
            cache_hits=sum(result.cache_status == "hit" for result in all_results),
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

    async def _call_provider(
        self,
        call: _ProviderCall,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        provider = call.provider
        key = self._cache_key(provider, call.lane, filters)
        if self._cache is None:
            async with self._semaphores[provider.provider_name]:
                result = await provider.search(
                    lane=call.lane,
                    filters=filters,
                    limit=self._results_per_request,
                )
            return result.model_copy(update={"cache_status": "bypass"})
        cached = self._cache.get(key)
        if cached is not None:
            return cached.model_copy(update={"cache_status": "hit"})
        async with self._inflight_lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached.model_copy(update={"cache_status": "hit"})
            task = self._inflight.get(key)
            owner = task is None
            if task is None:
                task = asyncio.create_task(self._run_provider(provider, call.lane, filters))
                self._inflight[key] = task
        try:
            result = await task
        finally:
            if owner:
                async with self._inflight_lock:
                    self._inflight.pop(key, None)
        if owner:
            self._cache.set(key, result)
            return result.model_copy(update={"cache_status": "miss"})
        return result.model_copy(update={"cache_status": "coalesced"})

    async def _run_provider(
        self,
        provider: LiteratureProvider,
        lane: QueryLane,
        filters: LiteratureFilters,
    ) -> ProviderResult:
        async with self._semaphores[provider.provider_name]:
            return await provider.search(
                lane=lane,
                filters=filters,
                limit=self._results_per_request,
            )

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from paperagent.errors import ProviderError
from paperagent.providers.base import LLMProvider
from paperagent.providers.endpoint import (
    EndpointHealthState,
    ProviderPool,
    RoutedEndpoint,
)
from paperagent.schemas import Message, TokenUsage

T = TypeVar("T", bound=BaseModel)

_ENDPOINT_FATAL_CODES = {
    "LLM_AUTHENTICATION",
    "LLM_CONFIGURATION",
    "LLM_PERMISSION",
}
_ROUTER_STOP_CODES = {
    "LLM_BUDGET_EXHAUSTED",
    "LLM_CANCELLED",
}


@dataclass(frozen=True, slots=True)
class RouteAttempt:
    pool_id: str
    endpoint_id: str
    outcome: str
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class EndpointSnapshot:
    pool_id: str
    endpoint_id: str
    state: EndpointHealthState
    in_flight: int
    consecutive_failures: int
    latency_ewma_ms: float
    open_until: float | None
    last_error_code: str | None


@dataclass(slots=True)
class _EndpointRuntime:
    pool_id: str
    endpoint: RoutedEndpoint
    in_flight: int = 0
    consecutive_failures: int = 0
    latency_ewma_ms: float = 0.0
    open_until: float = 0.0
    half_open_in_flight: bool = False
    last_error_code: str | None = None

    def health_state(self, now: float) -> EndpointHealthState:
        if self.open_until == float("inf") or now < self.open_until:
            return EndpointHealthState.OPEN
        if self.open_until > 0:
            return EndpointHealthState.HALF_OPEN
        return EndpointHealthState.CLOSED


class RoutingLLMProvider:
    """Route structured LLM calls across ordered pools and healthy endpoints.

    Pool order defines cross-provider fallback. Within one pool, selection uses a
    least-in-flight score with EWMA latency and recent-failure penalties. The router owns
    no retry loop inside an endpoint; every delegate call is one router attempt.
    """

    provider_name = "router"

    def __init__(
        self,
        pools: Sequence[ProviderPool],
        *,
        max_total_attempts: int | None = None,
        ewma_alpha: float = 0.2,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not pools:
            raise ValueError("at least one provider pool is required")
        if max_total_attempts is not None and max_total_attempts <= 0:
            raise ValueError("max_total_attempts must be positive")
        if not 0 < ewma_alpha <= 1:
            raise ValueError("ewma_alpha must be in (0, 1]")

        pool_ids = [pool.pool_id for pool in pools]
        if len(pool_ids) != len(set(pool_ids)):
            raise ValueError("pool IDs must be globally unique")

        endpoint_ids = [
            endpoint.config.endpoint_id for pool in pools for endpoint in pool.endpoints
        ]
        if len(endpoint_ids) != len(set(endpoint_ids)):
            raise ValueError("endpoint IDs must be globally unique")

        self._pools = tuple(pools)
        self._max_total_attempts = max_total_attempts or len(endpoint_ids)
        self._ewma_alpha = ewma_alpha
        self._clock = clock
        self._condition = asyncio.Condition()
        self._runtimes = {
            endpoint.config.endpoint_id: _EndpointRuntime(
                pool_id=pool.pool_id,
                endpoint=endpoint,
            )
            for pool in self._pools
            for endpoint in pool.endpoints
        }
        self.last_usage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms = 0
        self.last_endpoint_id: str | None = None
        self.last_pool_id: str | None = None
        self.last_attempt_count = 0
        self.last_attempts: tuple[RouteAttempt, ...] = ()

    @property
    def model_name(self) -> str:
        if self.last_endpoint_id is not None:
            return self._runtimes[self.last_endpoint_id].endpoint.config.model
        return self._pools[0].endpoints[0].config.model

    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T:
        attempts: list[RouteAttempt] = []
        excluded: set[str] = set()
        last_failure: ProviderError | None = None
        self.last_usage = TokenUsage(input_tokens=0, output_tokens=0)
        self.last_latency_ms = 0
        self.last_endpoint_id = None
        self.last_pool_id = None
        self.last_attempt_count = 0
        self.last_attempts = ()

        for pool in self._pools:
            while len(attempts) < self._max_total_attempts:
                runtime = await self._acquire_endpoint(pool, excluded)
                if runtime is None:
                    break
                endpoint_id = runtime.endpoint.config.endpoint_id
                excluded.add(endpoint_id)
                started = time.perf_counter()
                try:
                    result = await runtime.endpoint.provider.generate_structured(
                        task=task,
                        scenario=scenario,
                        call_index=call_index,
                        fixture_version=fixture_version,
                        schema=schema,
                        messages=messages,
                    )
                except asyncio.CancelledError:
                    await self._release_cancelled(runtime)
                    raise
                except ProviderError as exc:
                    latency_ms = (time.perf_counter() - started) * 1000
                    await self._release_failure(runtime, exc, latency_ms)
                    attempts.append(
                        RouteAttempt(
                            pool_id=runtime.pool_id,
                            endpoint_id=endpoint_id,
                            outcome="failed",
                            error_code=exc.code,
                        )
                    )
                    last_failure = exc
                    if exc.code in _ROUTER_STOP_CODES:
                        self._record_terminal_attempts(attempts)
                        raise
                    continue
                else:
                    latency_ms = (time.perf_counter() - started) * 1000
                    await self._release_success(runtime, latency_ms)
                    attempts.append(
                        RouteAttempt(
                            pool_id=runtime.pool_id,
                            endpoint_id=endpoint_id,
                            outcome="succeeded",
                        )
                    )
                    self._copy_winner_metrics(runtime)
                    self.last_endpoint_id = endpoint_id
                    self.last_pool_id = runtime.pool_id
                    self._record_terminal_attempts(attempts)
                    return result

        self._record_terminal_attempts(attempts)
        if last_failure is not None:
            raise last_failure
        raise ProviderError(
            "no healthy LLM endpoint is currently routable",
            provider=self.provider_name,
            task=task,
            retryable=True,
            code="LLM_ROUTER_UNAVAILABLE",
        )

    async def snapshots(self) -> tuple[EndpointSnapshot, ...]:
        async with self._condition:
            now = self._clock()
            return tuple(
                EndpointSnapshot(
                    pool_id=runtime.pool_id,
                    endpoint_id=runtime.endpoint.config.endpoint_id,
                    state=runtime.health_state(now),
                    in_flight=runtime.in_flight,
                    consecutive_failures=runtime.consecutive_failures,
                    latency_ewma_ms=runtime.latency_ewma_ms,
                    open_until=(runtime.open_until if runtime.open_until > 0 else None),
                    last_error_code=runtime.last_error_code,
                )
                for runtime in self._runtimes.values()
            )

    async def aclose(self) -> None:
        seen: set[int] = set()
        for runtime in self._runtimes.values():
            provider = runtime.endpoint.provider
            provider_identity = id(provider)
            if provider_identity in seen:
                continue
            seen.add(provider_identity)
            closer = getattr(provider, "aclose", None)
            if closer is None:
                continue
            result = closer()
            if inspect.isawaitable(result):
                await result

    async def _acquire_endpoint(
        self,
        pool: ProviderPool,
        excluded: set[str],
    ) -> _EndpointRuntime | None:
        async with self._condition:
            while True:
                now = self._clock()
                candidates: list[_EndpointRuntime] = []
                capacity_blocked = False
                for endpoint in pool.endpoints:
                    config = endpoint.config
                    if config.endpoint_id in excluded or config.disabled:
                        continue
                    runtime = self._runtimes[config.endpoint_id]
                    state = runtime.health_state(now)
                    if state is EndpointHealthState.OPEN:
                        continue
                    if state is EndpointHealthState.HALF_OPEN and runtime.half_open_in_flight:
                        continue
                    if runtime.in_flight >= config.limits.max_concurrency:
                        capacity_blocked = True
                        continue
                    candidates.append(runtime)

                if candidates:
                    selected = min(candidates, key=self._endpoint_score)
                    selected.in_flight += 1
                    if selected.health_state(now) is EndpointHealthState.HALF_OPEN:
                        selected.half_open_in_flight = True
                    return selected
                if capacity_blocked:
                    await self._condition.wait()
                    continue
                return None

    def _endpoint_score(self, runtime: _EndpointRuntime) -> tuple[float, str]:
        limits = runtime.endpoint.config.limits
        load_penalty = runtime.in_flight / limits.max_concurrency
        latency_penalty = runtime.latency_ewma_ms / 1000
        failure_penalty = runtime.consecutive_failures * 5.0
        return (
            load_penalty + latency_penalty + failure_penalty,
            runtime.endpoint.config.endpoint_id,
        )

    async def _release_success(self, runtime: _EndpointRuntime, latency_ms: float) -> None:
        async with self._condition:
            runtime.in_flight -= 1
            runtime.consecutive_failures = 0
            runtime.open_until = 0.0
            runtime.half_open_in_flight = False
            runtime.last_error_code = None
            runtime.latency_ewma_ms = self._updated_ewma(
                runtime.latency_ewma_ms,
                latency_ms,
            )
            self._condition.notify_all()

    async def _release_failure(
        self,
        runtime: _EndpointRuntime,
        error: ProviderError,
        latency_ms: float,
    ) -> None:
        async with self._condition:
            now = self._clock()
            previous_state = runtime.health_state(now)
            runtime.in_flight -= 1
            runtime.half_open_in_flight = False
            runtime.last_error_code = error.code
            runtime.latency_ewma_ms = self._updated_ewma(
                runtime.latency_ewma_ms,
                latency_ms,
            )
            if error.code in _ENDPOINT_FATAL_CODES:
                runtime.consecutive_failures += 1
                runtime.open_until = float("inf")
            elif error.retryable:
                runtime.consecutive_failures += 1
                threshold = runtime.endpoint.config.failure_threshold
                if (
                    previous_state is EndpointHealthState.HALF_OPEN
                    or runtime.consecutive_failures >= threshold
                ):
                    runtime.open_until = now + runtime.endpoint.config.cooldown_seconds
            self._condition.notify_all()

    async def _release_cancelled(self, runtime: _EndpointRuntime) -> None:
        async with self._condition:
            runtime.in_flight -= 1
            runtime.half_open_in_flight = False
            self._condition.notify_all()

    def _updated_ewma(self, previous: float, observed: float) -> float:
        if previous <= 0:
            return observed
        return self._ewma_alpha * observed + (1 - self._ewma_alpha) * previous

    def _copy_winner_metrics(self, runtime: _EndpointRuntime) -> None:
        provider = runtime.endpoint.provider
        usage = getattr(provider, "last_usage", None)
        if isinstance(usage, TokenUsage):
            self.last_usage = usage
        latency = getattr(provider, "last_latency_ms", None)
        if isinstance(latency, int):
            self.last_latency_ms = latency
        else:
            self.last_latency_ms = int(runtime.latency_ewma_ms)

    def _record_terminal_attempts(self, attempts: list[RouteAttempt]) -> None:
        self.last_attempts = tuple(attempts)
        self.last_attempt_count = len(attempts)


__all__ = ["EndpointSnapshot", "RouteAttempt", "RoutingLLMProvider"]

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from paperagent.schemas.literature import ProviderResult

CircuitState = Literal["closed", "open", "half_open"]


@dataclass(frozen=True)
class ProviderCircuitPolicy:
    timeout_failures: int = 2
    rate_limit_failures: int = 2
    failure_cooldown_seconds: float = 600.0
    rate_limit_cooldown_seconds: float = 900.0

    def __post_init__(self) -> None:
        if self.timeout_failures < 1 or self.rate_limit_failures < 1:
            raise ValueError("circuit failure thresholds must be positive")
        if self.failure_cooldown_seconds <= 0 or self.rate_limit_cooldown_seconds <= 0:
            raise ValueError("circuit cooldowns must be positive")


@dataclass
class ProviderHealth:
    state: CircuitState = "closed"
    consecutive_timeouts: int = 0
    consecutive_rate_limits: int = 0
    opened_until: datetime | None = None
    probe_in_flight: bool = False


class ProviderCircuitBreaker:
    def __init__(
        self,
        policies: dict[str, ProviderCircuitPolicy] | None = None,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._policies = policies or {}
        self._health: dict[str, ProviderHealth] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._now = now

    def _policy(self, provider: str) -> ProviderCircuitPolicy:
        return self._policies.get(provider, ProviderCircuitPolicy())

    def _state(self, provider: str) -> ProviderHealth:
        return self._health.setdefault(provider, ProviderHealth())

    def _lock(self, provider: str) -> asyncio.Lock:
        return self._locks.setdefault(provider, asyncio.Lock())

    async def before_call(self, provider: str) -> datetime | None:
        async with self._lock(provider):
            health = self._state(provider)
            now = self._now()
            if health.state == "closed":
                return None
            if health.state == "open":
                if health.opened_until is not None and health.opened_until > now:
                    return health.opened_until
                health.state = "half_open"
                health.probe_in_flight = False
            if health.probe_in_flight:
                return health.opened_until or now + timedelta(seconds=1)
            health.probe_in_flight = True
            return None

    async def record(self, provider: str, result: ProviderResult) -> None:
        async with self._lock(provider):
            health = self._state(provider)
            policy = self._policy(provider)
            now = self._now()
            if result.status in {"success", "empty"}:
                health.state = "closed"
                health.consecutive_timeouts = 0
                health.consecutive_rate_limits = 0
                health.opened_until = None
                health.probe_in_flight = False
                return

            health.probe_in_flight = False
            if result.error_code == "DAILY_QUOTA_EXHAUSTED":
                health.state = "open"
                health.opened_until = result.retry_at or now + timedelta(days=1)
                return
            if result.status == "timeout":
                health.consecutive_timeouts += 1
                health.consecutive_rate_limits = 0
                if health.consecutive_timeouts >= policy.timeout_failures:
                    health.state = "open"
                    health.opened_until = now + timedelta(seconds=policy.failure_cooldown_seconds)
                return
            if result.status == "rate_limited":
                health.consecutive_rate_limits += 1
                health.consecutive_timeouts = 0
                if result.retry_at is not None:
                    health.state = "open"
                    health.opened_until = result.retry_at
                elif health.consecutive_rate_limits >= policy.rate_limit_failures:
                    health.state = "open"
                    health.opened_until = now + timedelta(
                        seconds=policy.rate_limit_cooldown_seconds
                    )
                return

            health.consecutive_timeouts = 0
            health.consecutive_rate_limits = 0
            if health.state == "half_open":
                health.state = "open"
                health.opened_until = now + timedelta(seconds=policy.failure_cooldown_seconds)

    def snapshot(self, provider: str) -> ProviderHealth:
        health = self._state(provider)
        return ProviderHealth(
            state=health.state,
            consecutive_timeouts=health.consecutive_timeouts,
            consecutive_rate_limits=health.consecutive_rate_limits,
            opened_until=health.opened_until,
            probe_in_flight=health.probe_in_flight,
        )

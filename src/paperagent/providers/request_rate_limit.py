from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import monotonic
from weakref import WeakKeyDictionary

Clock = Callable[[], float]
Sleeper = Callable[[float], Awaitable[None]]


class AsyncRequestRateLimiter:
    """Smooth requests to a fixed maximum rate within one event loop."""

    def __init__(
        self,
        requests_per_minute: int,
        *,
        clock: Clock = monotonic,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        if requests_per_minute <= 0:
            raise ValueError("requests_per_minute must be positive")
        self._minimum_interval_seconds = 60.0 / requests_per_minute
        self._clock = clock
        self._sleep = sleep
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = self._clock()
            delay = max(0.0, self._next_allowed_at - now)
            if delay:
                await self._sleep(delay)
                now = self._clock()
            self._next_allowed_at = max(now, self._next_allowed_at) + self._minimum_interval_seconds


_LIMITERS: WeakKeyDictionary[
    asyncio.AbstractEventLoop,
    dict[tuple[str, int], AsyncRequestRateLimiter],
] = WeakKeyDictionary()


def shared_request_rate_limiter(
    *,
    namespace: str,
    requests_per_minute: int,
) -> AsyncRequestRateLimiter:
    """Return an event-loop-local limiter shared across provider instances."""

    loop = asyncio.get_running_loop()
    limiters = _LIMITERS.setdefault(loop, {})
    key = (namespace, requests_per_minute)
    limiter = limiters.get(key)
    if limiter is None:
        limiter = AsyncRequestRateLimiter(requests_per_minute)
        limiters[key] = limiter
    return limiter

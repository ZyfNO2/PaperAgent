"""Re7.6 SourcePolicy — per-source rate limiting + circuit breaker state.

SOP §7.2: Semantic Scholar 429 must be handled with SourcePolicy:
concurrency cap, exponential backoff, circuit breaker, cache TTL,
and {disabled|rate_limited|empty|failed} explicit states.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Literal

SourceState = Literal["enabled", "disabled", "rate_limited", "empty", "failed"]


@dataclass
class SourcePolicy:
    """Rate-limiting and circuit-breaker policy for one retrieval source."""
    source_id: str
    max_concurrency: int = 3
    backoff_base_s: float = 1.0
    backoff_max_s: float = 60.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_s: float = 300.0
    cache_ttl_s: float = 3600.0
    state: SourceState = "enabled"

    _semaphore: threading.Semaphore = field(init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _last_failure_at: float = field(default=0.0, init=False, repr=False)
    _current_backoff_s: float = field(default=0.0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = threading.Semaphore(self.max_concurrency)

    def acquire(self, timeout_s: float = 30.0) -> bool:
        """Try to acquire a concurrency slot. Returns False if circuit-broken."""
        with self._lock:
            if self.state == "disabled":
                return False
            if self._failure_count >= self.circuit_breaker_threshold:
                if time.monotonic() - self._last_failure_at > self.circuit_breaker_reset_s:
                    self._failure_count = 0
                    self._current_backoff_s = 0.0
                    self.state = "enabled"
                else:
                    self.state = "rate_limited"
                    return False
        return self._semaphore.acquire(timeout=timeout_s)

    def release(self) -> None:
        try:
            self._semaphore.release()
        except ValueError:
            pass

    def record_failure(self, is_rate_limit: bool = False) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_at = time.monotonic()
            if is_rate_limit:
                self._current_backoff_s = min(
                    self._current_backoff_s * 2 if self._current_backoff_s > 0 else self.backoff_base_s,
                    self.backoff_max_s,
                )
                self.state = "rate_limited"
            if self._failure_count >= self.circuit_breaker_threshold:
                self.state = "rate_limited"

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._current_backoff_s = 0.0
            if self.state == "rate_limited":
                self.state = "enabled"

    def backoff_remaining_s(self) -> float:
        with self._lock:
            if self._current_backoff_s <= 0:
                return 0.0
            elapsed = time.monotonic() - self._last_failure_at
            remaining = self._current_backoff_s - elapsed
            return max(0.0, remaining)


_REGISTRY: dict[str, SourcePolicy] = {}
_REGISTRY_LOCK = threading.Lock()


def get_source_policy(source_id: str) -> SourcePolicy:
    """Get or create the SourcePolicy for a retrieval source."""
    with _REGISTRY_LOCK:
        if source_id not in _REGISTRY:
            defaults = _DEFAULT_POLICIES.get(source_id, {})
            _REGISTRY[source_id] = SourcePolicy(source_id=source_id, **defaults)
        return _REGISTRY[source_id]


def reset_source_policies() -> None:
    """Reset all source policies (for testing)."""
    with _REGISTRY_LOCK:
        _REGISTRY.clear()


_DEFAULT_POLICIES: dict[str, dict] = {
    "semantic_scholar": {
        "max_concurrency": 1,
        "backoff_base_s": 2.0,
        "circuit_breaker_threshold": 3,
    },
    "openalex": {
        "max_concurrency": 3,
        "backoff_base_s": 1.0,
    },
    "arxiv": {
        "max_concurrency": 5,
        "backoff_base_s": 0.5,
    },
}

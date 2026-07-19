from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from paperagent.schemas.literature import ProviderResult


@dataclass(frozen=True)
class CacheKey:
    normalized_query: str
    provider: str
    filters: str
    limit: int
    provider_contract_version: str


@dataclass(frozen=True)
class _CacheEntry:
    value: ProviderResult
    expires_at: float


class InMemoryProviderCache:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        success_ttl: float = 3600.0,
        empty_ttl: float = 120.0,
    ) -> None:
        self._clock = clock
        self._success_ttl = success_ttl
        self._empty_ttl = empty_ttl
        self._entries: dict[CacheKey, _CacheEntry] = {}

    def get(self, key: CacheKey) -> ProviderResult | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._entries.pop(key, None)
            return None
        return entry.value

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        if value.status == "success":
            ttl = self._success_ttl
        elif value.status == "empty":
            ttl = self._empty_ttl
        else:
            return
        self._entries[key] = _CacheEntry(value=value, expires_at=self._clock() + ttl)

    def clear(self) -> None:
        self._entries.clear()

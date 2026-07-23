from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from paperagent.schemas.literature import ProviderResult


@dataclass(frozen=True)
class CacheKey:
    normalized_query: str
    provider: str
    filters: str
    limit: int
    provider_contract_version: str

    def digest(self) -> str:
        payload = json.dumps(
            {
                "normalized_query": self.normalized_query,
                "provider": self.provider,
                "filters": self.filters,
                "limit": self.limit,
                "provider_contract_version": self.provider_contract_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return sha256(payload.encode("utf-8")).hexdigest()


class ProviderCache(Protocol):
    def get(self, key: CacheKey) -> ProviderResult | None: ...

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None: ...

    def set(self, key: CacheKey, value: ProviderResult) -> None: ...

    def clear(self) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class _CacheEntry:
    value: ProviderResult
    cached_at: float
    expires_at: float


class _TTLPolicy:
    def __init__(
        self,
        *,
        success_ttl: float,
        empty_ttl: float,
        rate_limit_ttl: float,
        timeout_ttl: float,
    ) -> None:
        self.success_ttl = success_ttl
        self.empty_ttl = empty_ttl
        self.rate_limit_ttl = rate_limit_ttl
        self.timeout_ttl = timeout_ttl

    def ttl(self, value: ProviderResult, *, now: float) -> float | None:
        if value.status == "success":
            return self.success_ttl
        if value.status == "empty":
            return self.empty_ttl
        if value.status == "rate_limited":
            if value.retry_at is not None:
                return max(1.0, value.retry_at.timestamp() - now)
            return self.rate_limit_ttl or None
        if value.status == "timeout":
            return self.timeout_ttl or None
        if value.error_code == "DAILY_QUOTA_EXHAUSTED" and value.retry_at is not None:
            return max(1.0, value.retry_at.timestamp() - now)
        return None


class InMemoryProviderCache:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.time,
        success_ttl: float = 3600.0,
        empty_ttl: float = 120.0,
        rate_limit_ttl: float = 0.0,
        timeout_ttl: float = 0.0,
    ) -> None:
        self._clock = clock
        self._ttl = _TTLPolicy(
            success_ttl=success_ttl,
            empty_ttl=empty_ttl,
            rate_limit_ttl=rate_limit_ttl,
            timeout_ttl=timeout_ttl,
        )
        self._entries: dict[CacheKey, _CacheEntry] = {}

    def get(self, key: CacheKey) -> ProviderResult | None:
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= self._clock():
            return None
        return entry.value

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        now = self._clock()
        if entry.expires_at > now:
            return entry.value
        if now - entry.expires_at > max_stale_seconds:
            return None
        return entry.value

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        now = self._clock()
        ttl = self._ttl.ttl(value, now=now)
        if ttl is None:
            return
        cached_at = datetime.fromtimestamp(now, tz=UTC)
        stored = value.model_copy(update={"cached_at": cached_at})
        self._entries[key] = _CacheEntry(value=stored, cached_at=now, expires_at=now + ttl)

    def clear(self) -> None:
        self._entries.clear()

    def close(self) -> None:
        return None


class SQLiteProviderCache:
    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        success_ttl: float = 3600.0,
        empty_ttl: float = 120.0,
        rate_limit_ttl: float = 900.0,
        timeout_ttl: float = 180.0,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._ttl = _TTLPolicy(
            success_ttl=success_ttl,
            empty_ttl=empty_ttl,
            rate_limit_ttl=rate_limit_ttl,
            timeout_ttl=timeout_ttl,
        )
        self._lock = RLock()
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS literature_provider_cache (
                    cache_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_literature_cache_expiry "
                "ON literature_provider_cache(expires_at)"
            )

    def _read(self, key: CacheKey) -> tuple[ProviderResult, float] | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload, expires_at FROM literature_provider_cache WHERE cache_key = ?",
                (key.digest(),),
            ).fetchone()
        if row is None:
            return None
        payload, expires_at = row
        try:
            return ProviderResult.model_validate_json(str(payload)), float(expires_at)
        except (ValueError, TypeError):
            with self._lock, self._connection:
                self._connection.execute(
                    "DELETE FROM literature_provider_cache WHERE cache_key = ?", (key.digest(),)
                )
            return None

    def get(self, key: CacheKey) -> ProviderResult | None:
        stored = self._read(key)
        if stored is None:
            return None
        value, expires_at = stored
        return value if expires_at > self._clock() else None

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None:
        stored = self._read(key)
        if stored is None:
            return None
        value, expires_at = stored
        now = self._clock()
        if expires_at > now or now - expires_at <= max_stale_seconds:
            return value
        return None

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        now = self._clock()
        ttl = self._ttl.ttl(value, now=now)
        if ttl is None:
            return
        cached_at = datetime.fromtimestamp(now, tz=UTC)
        stored = value.model_copy(update={"cached_at": cached_at})
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO literature_provider_cache(
                    cache_key, provider, status, payload, cached_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    provider = excluded.provider,
                    status = excluded.status,
                    payload = excluded.payload,
                    cached_at = excluded.cached_at,
                    expires_at = excluded.expires_at
                """,
                (
                    key.digest(),
                    key.provider,
                    stored.status,
                    stored.model_dump_json(),
                    now,
                    now + ttl,
                ),
            )

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM literature_provider_cache")

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class JsonFixtureProviderCache:
    """Version-controlled provider response fixtures for deterministic offline replay."""

    def __init__(self, directory: str | Path, *, writable: bool = False) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._directory / "manifest.json"
        self._writable = writable
        self._lock = RLock()

    def _manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            return {"schema_version": "1", "requests": {}}
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"schema_version": "1", "requests": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("requests"), dict):
            return {"schema_version": "1", "requests": {}}
        return payload

    def _entry(self, key: CacheKey) -> dict[str, Any] | None:
        manifest = self._manifest()
        entry = manifest["requests"].get(key.digest())
        return entry if isinstance(entry, dict) else None

    def get(self, key: CacheKey) -> ProviderResult | None:
        with self._lock:
            entry = self._entry(key)
            if entry is None or not isinstance(entry.get("fixture"), str):
                return None
            path = self._directory / entry["fixture"]
            try:
                return ProviderResult.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError):
                return None

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None:
        del max_stale_seconds
        return self.get(key)

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        if not self._writable or value.status not in {
            "success",
            "empty",
            "rate_limited",
            "timeout",
        }:
            return
        with self._lock:
            digest = key.digest()
            fixture_name = f"{key.provider}-{digest[:20]}.json"
            fixture_path = self._directory / fixture_name
            fixture_path.write_text(
                value.model_dump_json(indent=2),
                encoding="utf-8",
            )
            manifest = self._manifest()
            requests = manifest["requests"]
            requests[digest] = {
                "provider": key.provider,
                "request_hash": f"sha256:{digest}",
                "fixture": fixture_name,
                "recorded_at": (value.cached_at or value.finished_at).isoformat(),
            }
            temporary = self._manifest_path.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(self._manifest_path)

    def clear(self) -> None:
        if not self._writable:
            return
        with self._lock:
            manifest = self._manifest()
            for entry in manifest["requests"].values():
                if isinstance(entry, dict) and isinstance(entry.get("fixture"), str):
                    (self._directory / entry["fixture"]).unlink(missing_ok=True)
            self._manifest_path.unlink(missing_ok=True)

    def close(self) -> None:
        return None


class LayeredProviderCache:
    def __init__(self, layers: list[ProviderCache]) -> None:
        if not layers:
            raise ValueError("at least one cache layer is required")
        self._layers = layers

    def get(self, key: CacheKey) -> ProviderResult | None:
        for index, layer in enumerate(self._layers):
            value = layer.get(key)
            if value is None:
                continue
            if index > 0:
                self._layers[0].set(key, value)
            return value
        return None

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None:
        for layer in self._layers:
            value = layer.get_stale(key, max_stale_seconds=max_stale_seconds)
            if value is not None:
                return value
        return None

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        for layer in self._layers:
            layer.set(key, value)

    def clear(self) -> None:
        for layer in self._layers:
            layer.clear()

    def close(self) -> None:
        for layer in self._layers:
            layer.close()


class TieredProviderCache(LayeredProviderCache):
    def __init__(self, memory: InMemoryProviderCache, persistent: ProviderCache) -> None:
        super().__init__([memory, persistent])

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from threading import RLock
from typing import Any, Literal, Protocol
from urllib.parse import quote

from paperagent.literature.normalize import canonical_doi, normalized_text
from paperagent.literature.providers.base import AsyncHTTPTransport, HttpxTransport
from paperagent.schemas.literature import PaperRecord

AttemptStatus = Literal["verified", "not_found", "mismatch", "failed"]
VerificationMode = Literal["offline", "cache_first", "live"]
_ARXIV_ID = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})$", re.IGNORECASE)


@dataclass(frozen=True)
class VerificationAttempt:
    status: AttemptStatus
    method: str | None = None
    message: str | None = None


class MetadataVerifier(Protocol):
    async def verify(self, paper: PaperRecord) -> VerificationAttempt: ...


class VerificationAttemptCache(Protocol):
    def get(self, key: str) -> VerificationAttempt | None: ...

    def set(self, key: str, attempt: VerificationAttempt) -> None: ...

    def clear(self) -> None: ...

    def close(self) -> None: ...


class SQLiteVerificationAttemptCache:
    """Persistent DOI verification cache stored beside retrieval responses."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], float] = time.time,
        success_ttl_seconds: float = 90 * 24 * 60 * 60,
        negative_ttl_seconds: float = 30 * 24 * 60 * 60,
    ) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._success_ttl = success_ttl_seconds
        self._negative_ttl = negative_ttl_seconds
        self._lock = RLock()
        self._connection = sqlite3.connect(self._path, check_same_thread=False)
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS literature_verification_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )

    def get(self, key: str) -> VerificationAttempt | None:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload, expires_at FROM literature_verification_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        payload, expires_at = row
        if float(expires_at) <= self._clock():
            return None
        try:
            data = json.loads(str(payload))
            return VerificationAttempt(**data)
        except (TypeError, ValueError, json.JSONDecodeError):
            with self._lock, self._connection:
                self._connection.execute(
                    "DELETE FROM literature_verification_cache WHERE cache_key = ?", (key,)
                )
            return None

    def set(self, key: str, attempt: VerificationAttempt) -> None:
        if attempt.status == "failed":
            return
        ttl = self._success_ttl if attempt.status == "verified" else self._negative_ttl
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO literature_verification_cache(cache_key, payload, expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    payload = excluded.payload,
                    expires_at = excluded.expires_at
                """,
                (
                    key,
                    json.dumps(asdict(attempt), sort_keys=True, separators=(",", ":")),
                    self._clock() + ttl,
                ),
            )

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM literature_verification_cache")

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class JsonVerificationAttemptCache:
    def __init__(self, directory: str | Path, *, writable: bool = False) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._directory / "verification-manifest.json"
        self._writable = writable
        self._lock = RLock()

    def _manifest(self) -> dict[str, Any]:
        if not self._manifest_path.exists():
            return {"schema_version": "1", "attempts": {}}
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"schema_version": "1", "attempts": {}}
        if not isinstance(payload, dict) or not isinstance(payload.get("attempts"), dict):
            return {"schema_version": "1", "attempts": {}}
        return payload

    def get(self, key: str) -> VerificationAttempt | None:
        with self._lock:
            entry = self._manifest()["attempts"].get(key)
            if not isinstance(entry, dict) or not isinstance(entry.get("fixture"), str):
                return None
            try:
                payload = json.loads(
                    (self._directory / entry["fixture"]).read_text(encoding="utf-8")
                )
                return VerificationAttempt(**payload)
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                return None

    def set(self, key: str, attempt: VerificationAttempt) -> None:
        if not self._writable or attempt.status == "failed":
            return
        with self._lock:
            fixture_name = f"verification-{key[:20]}.json"
            (self._directory / fixture_name).write_text(
                json.dumps(asdict(attempt), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest = self._manifest()
            manifest["attempts"][key] = {"fixture": fixture_name}
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
            for entry in manifest["attempts"].values():
                if isinstance(entry, dict) and isinstance(entry.get("fixture"), str):
                    (self._directory / entry["fixture"]).unlink(missing_ok=True)
            self._manifest_path.unlink(missing_ok=True)

    def close(self) -> None:
        return None


class LayeredVerificationAttemptCache:
    def __init__(self, layers: list[VerificationAttemptCache]) -> None:
        if not layers:
            raise ValueError("at least one verification cache layer is required")
        self._layers = layers

    def get(self, key: str) -> VerificationAttempt | None:
        for layer in self._layers:
            attempt = layer.get(key)
            if attempt is not None:
                return attempt
        return None

    def set(self, key: str, attempt: VerificationAttempt) -> None:
        for layer in self._layers:
            layer.set(key, attempt)

    def clear(self) -> None:
        for layer in self._layers:
            layer.clear()

    def close(self) -> None:
        for layer in self._layers:
            layer.close()


class CrossrefVerifier:
    endpoint = "https://api.crossref.org/works"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
        mailto: str | None = None,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._timeout = timeout_seconds
        self._mailto = mailto

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        if not paper.doi:
            return VerificationAttempt(status="not_found")
        headers = (
            {"User-Agent": f"PaperAgent/0.2 (mailto:{self._mailto})"} if self._mailto else None
        )
        try:
            response = await self._transport.get(
                f"{self.endpoint}/{quote(paper.doi, safe='')}",
                headers=headers,
                timeout=self._timeout,
            )
        except Exception as exc:
            return VerificationAttempt(status="failed", message=str(exc))
        if response.status_code == 404:
            return VerificationAttempt(status="not_found")
        if response.status_code != 200 or not isinstance(response.json_data, dict):
            return VerificationAttempt(status="failed", message=f"HTTP {response.status_code}")
        message = response.json_data.get("message")
        if not isinstance(message, dict):
            return VerificationAttempt(status="failed", message="missing Crossref message")
        found = canonical_doi(str(message.get("DOI") or ""))
        if found != canonical_doi(paper.doi):
            return VerificationAttempt(status="mismatch", message="Crossref DOI mismatch")
        titles = message.get("title")
        if isinstance(titles, list) and titles and isinstance(titles[0], str):
            expected = normalized_text(paper.canonical_title)
            actual = normalized_text(titles[0])
            if expected and actual and expected != actual:
                return VerificationAttempt(status="mismatch", message="Crossref title mismatch")
        return VerificationAttempt(status="verified", method="crossref_doi_exact")


class DataCiteVerifier:
    endpoint = "https://api.datacite.org/dois"

    def __init__(
        self,
        *,
        transport: AsyncHTTPTransport | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._transport = transport or HttpxTransport()
        self._timeout = timeout_seconds

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        if not paper.doi:
            return VerificationAttempt(status="not_found")
        try:
            response = await self._transport.get(
                f"{self.endpoint}/{quote(paper.doi, safe='')}", timeout=self._timeout
            )
        except Exception as exc:
            return VerificationAttempt(status="failed", message=str(exc))
        if response.status_code == 404:
            return VerificationAttempt(status="not_found")
        if response.status_code != 200 or not isinstance(response.json_data, dict):
            return VerificationAttempt(status="failed", message=f"HTTP {response.status_code}")
        data = response.json_data.get("data")
        if not isinstance(data, dict):
            return VerificationAttempt(status="failed", message="missing DataCite data")
        raw_attributes = data.get("attributes")
        attributes: dict[str, Any] = raw_attributes if isinstance(raw_attributes, dict) else {}
        found = canonical_doi(str(attributes.get("doi") or data.get("id") or ""))
        if found != canonical_doi(paper.doi):
            return VerificationAttempt(status="mismatch", message="DataCite DOI mismatch")
        return VerificationAttempt(status="verified", method="datacite_doi_exact")


class VerificationService:
    def __init__(
        self,
        verifiers: list[MetadataVerifier],
        *,
        max_network_calls: int | None = 96,
        mode: VerificationMode = "cache_first",
        cache: VerificationAttemptCache | None = None,
    ) -> None:
        if max_network_calls is not None and max_network_calls < 1:
            raise ValueError("max_network_calls must be positive or None")
        if mode not in {"offline", "cache_first", "live"}:
            raise ValueError("verification mode must be offline, cache_first, or live")
        self._verifiers = verifiers
        self._max_network_calls = max_network_calls
        self._network_calls_started = 0
        self._budget_lock = asyncio.Lock()
        self._mode = mode
        self._cache = cache
        self._memory_cache: dict[str, VerificationAttempt] = {}

    def verification_budget(self) -> dict[str, int | None]:
        maximum = self._max_network_calls
        return {
            "maximum": maximum,
            "used": self._network_calls_started,
            "remaining": (
                None if maximum is None else max(0, maximum - self._network_calls_started)
            ),
        }

    async def _reserve_network_call(self) -> bool:
        async with self._budget_lock:
            if (
                self._max_network_calls is not None
                and self._network_calls_started >= self._max_network_calls
            ):
                return False
            self._network_calls_started += 1
            return True

    @staticmethod
    def _cache_key(verifier: MetadataVerifier, paper: PaperRecord) -> str:
        raw = "|".join(
            [
                type(verifier).__name__,
                canonical_doi(paper.doi or "") or "",
                normalized_text(paper.canonical_title),
            ]
        )
        return sha256(raw.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> VerificationAttempt | None:
        attempt = self._memory_cache.get(key)
        if attempt is not None:
            return attempt
        if self._cache is None:
            return None
        attempt = self._cache.get(key)
        if attempt is not None:
            self._memory_cache[key] = attempt
        return attempt

    def _cache_set(self, key: str, attempt: VerificationAttempt) -> None:
        if attempt.status == "failed":
            return
        self._memory_cache[key] = attempt
        if self._cache is not None:
            self._cache.set(key, attempt)

    def close(self) -> None:
        if self._cache is not None:
            self._cache.close()

    async def verify_all(self, papers: list[PaperRecord]) -> list[PaperRecord]:
        return [await self.verify_one(paper) for paper in papers]

    async def verify_one(self, paper: PaperRecord) -> PaperRecord:
        if paper.doi:
            saw_mismatch = False
            for verifier in self._verifiers:
                key = self._cache_key(verifier, paper)
                attempt = self._cache_get(key) if self._mode != "live" else None
                if attempt is None:
                    if self._mode == "offline":
                        continue
                    if not await self._reserve_network_call():
                        status = "suspicious" if saw_mismatch else "pending"
                        return paper.model_copy(update={"verification_status": status})
                    attempt = await verifier.verify(paper)
                    self._cache_set(key, attempt)
                if attempt.status == "verified":
                    return paper.model_copy(
                        update={
                            "verification_status": "verified",
                            "verification_methods": [attempt.method] if attempt.method else [],
                        }
                    )
                if attempt.status == "mismatch":
                    saw_mismatch = True
            if saw_mismatch:
                return paper.model_copy(update={"verification_status": "suspicious"})
            return paper.model_copy(update={"verification_status": "pending"})
        if paper.arxiv_id:
            if _ARXIV_ID.fullmatch(paper.arxiv_id):
                return paper.model_copy(
                    update={
                        "verification_status": "verified",
                        "verification_methods": ["arxiv_id_syntax"],
                    }
                )
            return paper.model_copy(update={"verification_status": "suspicious"})
        return paper.model_copy(update={"verification_status": "pending"})

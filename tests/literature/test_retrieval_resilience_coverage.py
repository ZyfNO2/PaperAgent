from __future__ import annotations

import json
import socket
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from paperagent.literature.cache import (
    CacheKey,
    InMemoryProviderCache,
    JsonFixtureProviderCache,
    LayeredProviderCache,
    SQLiteProviderCache,
    TieredProviderCache,
)
from paperagent.literature.providers.base import (
    HTTPResponse,
    HttpxTransport,
    http_failure_result,
    parse_retry_at,
    response_failure,
    response_success,
    transport_exception_result,
)
from paperagent.literature.resilience import ProviderCircuitBreaker, ProviderCircuitPolicy
from paperagent.literature.verification import (
    CrossrefVerifier,
    DataCiteVerifier,
    JsonVerificationAttemptCache,
    LayeredVerificationAttemptCache,
    SQLiteVerificationAttemptCache,
    VerificationAttempt,
    VerificationService,
)
from paperagent.schemas.literature import PaperRecord, ProviderPaper, ProviderResult

NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def cache_key(*, query: str = "reliable retrieval", provider: str = "openalex") -> CacheKey:
    return CacheKey(
        normalized_query=query,
        provider=provider,
        filters="{}",
        limit=10,
        provider_contract_version="coverage-v1",
    )


def provider_paper() -> ProviderPaper:
    return ProviderPaper(
        provider_record_id="W1",
        title="Reliable Retrieval",
        authors=["Jane Doe"],
        year=2025,
        doi="10.1000/reliable",
    )


def provider_result(
    status: str,
    *,
    error_code: str | None = None,
    retry_at: datetime | None = None,
) -> ProviderResult:
    return ProviderResult(
        provider="openalex",
        request_id=f"req-{status}",
        status=status,
        papers=[provider_paper()] if status == "success" else [],
        started_at=NOW,
        finished_at=NOW,
        retry_at=retry_at,
        error_code=error_code,
        error_message=error_code,
    )


def paper_record(
    *,
    doi: str | None = "10.1000/reliable",
    arxiv_id: str | None = None,
    title: str = "Reliable Retrieval",
) -> PaperRecord:
    return PaperRecord(
        paper_id="paper-1",
        canonical_title=title,
        doi=doi,
        arxiv_id=arxiv_id,
    )


class QueueTransport:
    def __init__(self, outcomes: list[HTTPResponse | Exception]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
    ) -> HTTPResponse:
        self.calls.append(
            {"method": "GET", "url": url, "params": params, "headers": headers, "timeout": timeout}
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def post(
        self,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | httpx.Timeout = 10.0,
    ) -> HTTPResponse:
        self.calls.append(
            {
                "method": "POST",
                "url": url,
                "json_body": json_body,
                "data": data,
                "headers": headers,
                "timeout": timeout,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeAttemptVerifier:
    def __init__(self, attempts: list[VerificationAttempt]) -> None:
        self.attempts = list(attempts)
        self.calls = 0

    async def verify(self, paper: PaperRecord) -> VerificationAttempt:
        del paper
        self.calls += 1
        return self.attempts.pop(0)


class SpyCache:
    def __init__(self, value: ProviderResult | None = None) -> None:
        self.value = value
        self.set_calls: list[ProviderResult] = []
        self.clear_calls = 0
        self.close_calls = 0

    def get(self, key: CacheKey) -> ProviderResult | None:
        del key
        return self.value

    def get_stale(self, key: CacheKey, *, max_stale_seconds: float) -> ProviderResult | None:
        del key, max_stale_seconds
        return self.value

    def set(self, key: CacheKey, value: ProviderResult) -> None:
        del key
        self.value = value
        self.set_calls.append(value)

    def clear(self) -> None:
        self.clear_calls += 1
        self.value = None

    def close(self) -> None:
        self.close_calls += 1


class SpyVerificationCache:
    def __init__(self, value: VerificationAttempt | None = None) -> None:
        self.value = value
        self.set_calls: list[VerificationAttempt] = []
        self.clear_calls = 0
        self.close_calls = 0

    def get(self, key: str) -> VerificationAttempt | None:
        del key
        return self.value

    def set(self, key: str, attempt: VerificationAttempt) -> None:
        del key
        self.value = attempt
        self.set_calls.append(attempt)

    def clear(self) -> None:
        self.clear_calls += 1
        self.value = None

    def close(self) -> None:
        self.close_calls += 1


def test_cache_key_digest_is_stable_and_sensitive() -> None:
    first = cache_key()
    assert first.digest() == cache_key().digest()
    assert first.digest() != cache_key(query="different").digest()
    assert len(first.digest()) == 64


def test_memory_cache_ttl_stale_clear_and_uncacheable() -> None:
    now = [100.0]
    cache = InMemoryProviderCache(
        clock=lambda: now[0],
        success_ttl=10,
        empty_ttl=5,
        rate_limit_ttl=4,
        timeout_ttl=3,
    )
    key = cache_key()

    assert cache.get(key) is None
    assert cache.get_stale(key, max_stale_seconds=30) is None

    cache.set(key, provider_result("success"))
    assert cache.get(key) is not None
    assert cache.get_stale(key, max_stale_seconds=30) is not None
    now[0] = 111
    assert cache.get(key) is None
    assert cache.get_stale(key, max_stale_seconds=2) is not None
    now[0] = 113.1
    assert cache.get_stale(key, max_stale_seconds=2) is None

    cache.set(key, provider_result("failed", error_code="HTTP_500"))
    assert cache.get(key) is None
    cache.clear()
    cache.close()


@pytest.mark.parametrize(
    ("value", "advance", "expected"),
    [
        (provider_result("empty"), 4.9, True),
        (provider_result("empty"), 5.1, False),
        (provider_result("timeout", error_code="READ_TIMEOUT"), 2.9, True),
        (provider_result("timeout", error_code="READ_TIMEOUT"), 3.1, False),
        (provider_result("rate_limited", error_code="RATE_LIMITED"), 3.9, True),
        (provider_result("rate_limited", error_code="RATE_LIMITED"), 4.1, False),
    ],
)
def test_memory_cache_status_specific_ttls(
    value: ProviderResult, advance: float, expected: bool
) -> None:
    now = [100.0]
    cache = InMemoryProviderCache(
        clock=lambda: now[0],
        success_ttl=10,
        empty_ttl=5,
        rate_limit_ttl=4,
        timeout_ttl=3,
    )
    cache.set(cache_key(), value)
    now[0] += advance
    assert (cache.get(cache_key()) is not None) is expected


def test_memory_cache_uses_retry_deadline_for_negative_result() -> None:
    now = [NOW.timestamp()]
    cache = InMemoryProviderCache(clock=lambda: now[0], rate_limit_ttl=1)
    cache.set(
        cache_key(),
        provider_result(
            "rate_limited",
            error_code="DAILY_QUOTA_EXHAUSTED",
            retry_at=NOW + timedelta(seconds=20),
        ),
    )
    now[0] += 19
    assert cache.get(cache_key()) is not None
    now[0] += 2
    assert cache.get(cache_key()) is None


def test_sqlite_cache_update_stale_corruption_and_clear(tmp_path: Path) -> None:
    now = [100.0]
    cache = SQLiteProviderCache(
        tmp_path / "nested" / "cache.sqlite3",
        clock=lambda: now[0],
        success_ttl=5,
        empty_ttl=2,
    )
    key = cache_key()
    assert cache.get(key) is None
    assert cache.get_stale(key, max_stale_seconds=10) is None

    cache.set(key, provider_result("success"))
    assert cache.get(key) is not None
    cache.set(key, provider_result("empty"))
    assert cache.get(key).status == "empty"  # type: ignore[union-attr]
    now[0] = 103
    assert cache.get(key) is None
    assert cache.get_stale(key, max_stale_seconds=2) is not None
    now[0] = 105.1
    assert cache.get_stale(key, max_stale_seconds=2) is None

    with cache._connection:
        cache._connection.execute(
            "UPDATE literature_provider_cache SET payload = ? WHERE cache_key = ?",
            ("not-json", key.digest()),
        )
    assert cache.get(key) is None
    row = cache._connection.execute(
        "SELECT cache_key FROM literature_provider_cache WHERE cache_key = ?", (key.digest(),)
    ).fetchone()
    assert row is None

    cache.set(key, provider_result("failed", error_code="HTTP_500"))
    assert cache.get(key) is None
    cache.set(key, provider_result("success"))
    cache.clear()
    assert cache.get(key) is None
    cache.close()


def test_json_fixture_cache_handles_invalid_inputs_and_clear(tmp_path: Path) -> None:
    key = cache_key()
    readonly = JsonFixtureProviderCache(tmp_path)
    assert readonly.get(key) is None
    readonly.set(key, provider_result("success"))
    assert not (tmp_path / "manifest.json").exists()
    readonly.clear()
    readonly.close()

    manifest = tmp_path / "manifest.json"
    manifest.write_text("{invalid", encoding="utf-8")
    assert readonly.get(key) is None
    manifest.write_text(json.dumps(["not", "an", "object"]), encoding="utf-8")
    assert readonly.get(key) is None
    manifest.write_text(json.dumps({"requests": []}), encoding="utf-8")
    assert readonly.get(key) is None
    manifest.write_text(
        json.dumps({"schema_version": "1", "requests": {key.digest(): "bad-entry"}}),
        encoding="utf-8",
    )
    assert readonly.get(key) is None
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "requests": {key.digest(): {"fixture": "missing.json"}},
            }
        ),
        encoding="utf-8",
    )
    assert readonly.get(key) is None

    writable = JsonFixtureProviderCache(tmp_path, writable=True)
    writable.set(key, provider_result("failed", error_code="HTTP_500"))
    writable.set(key, provider_result("success"))
    cached = writable.get(key)
    assert cached is not None
    assert writable.get_stale(key, max_stale_seconds=0) is not None
    fixture_names = [path for path in tmp_path.glob("openalex-*.json")]
    assert len(fixture_names) == 1
    fixture_names[0].write_text("invalid", encoding="utf-8")
    assert writable.get(key) is None
    writable.set(key, provider_result("success"))
    writable.clear()
    assert not manifest.exists()
    assert not list(tmp_path.glob("openalex-*.json"))
    writable.close()


def test_layered_and_tiered_provider_caches_promote_and_propagate() -> None:
    with pytest.raises(ValueError, match="at least one cache layer"):
        LayeredProviderCache([])

    first = SpyCache()
    second = SpyCache(provider_result("success"))
    layered = LayeredProviderCache([first, second])
    value = layered.get(cache_key())
    assert value is not None
    assert len(first.set_calls) == 1
    assert layered.get_stale(cache_key(), max_stale_seconds=10) is not None
    layered.set(cache_key(), provider_result("empty"))
    assert first.value is not None and first.value.status == "empty"
    assert second.value is not None and second.value.status == "empty"
    layered.clear()
    layered.close()
    assert first.clear_calls == second.clear_calls == 1
    assert first.close_calls == second.close_calls == 1

    memory = InMemoryProviderCache()
    tiered = TieredProviderCache(memory, SpyCache(provider_result("success")))
    assert tiered.get(cache_key()) is not None


def test_provider_circuit_policy_validation() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        ProviderCircuitPolicy(timeout_failures=0)
    with pytest.raises(ValueError, match="thresholds"):
        ProviderCircuitPolicy(rate_limit_failures=0)
    with pytest.raises(ValueError, match="cooldowns"):
        ProviderCircuitPolicy(failure_cooldown_seconds=0)
    with pytest.raises(ValueError, match="cooldowns"):
        ProviderCircuitPolicy(rate_limit_cooldown_seconds=0)


@pytest.mark.asyncio
async def test_circuit_half_open_single_probe_and_success_reset() -> None:
    now = [NOW]
    breaker = ProviderCircuitBreaker(
        {"arxiv": ProviderCircuitPolicy(timeout_failures=1, failure_cooldown_seconds=10)},
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
    assert await breaker.before_call("arxiv") == NOW + timedelta(seconds=10)
    now[0] += timedelta(seconds=11)
    assert await breaker.before_call("arxiv") is None
    blocked = await breaker.before_call("arxiv")
    assert blocked == NOW + timedelta(seconds=10)

    await breaker.record("arxiv", provider_result("empty"))
    snapshot = breaker.snapshot("arxiv")
    assert snapshot.state == "closed"
    assert snapshot.opened_until is None
    assert snapshot.probe_in_flight is False


@pytest.mark.asyncio
async def test_circuit_quota_rate_limit_and_half_open_failure_paths() -> None:
    now = [NOW]
    policy = ProviderCircuitPolicy(
        rate_limit_failures=2,
        rate_limit_cooldown_seconds=20,
        failure_cooldown_seconds=30,
    )
    breaker = ProviderCircuitBreaker({"openalex": policy}, now=lambda: now[0])

    quota = provider_result("rate_limited", error_code="DAILY_QUOTA_EXHAUSTED")
    await breaker.record("openalex", quota)
    assert breaker.snapshot("openalex").opened_until == NOW + timedelta(days=1)

    reset_breaker = ProviderCircuitBreaker({"openalex": policy}, now=lambda: now[0])
    retry_at = NOW + timedelta(minutes=5)
    limited_with_retry = provider_result(
        "rate_limited", error_code="RATE_LIMITED", retry_at=retry_at
    )
    await reset_breaker.record("openalex", limited_with_retry)
    assert await reset_breaker.before_call("openalex") == retry_at

    threshold_breaker = ProviderCircuitBreaker({"openalex": policy}, now=lambda: now[0])
    limited = provider_result("rate_limited", error_code="RATE_LIMITED")
    await threshold_breaker.record("openalex", limited)
    assert threshold_breaker.snapshot("openalex").state == "closed"
    await threshold_breaker.record("openalex", limited)
    assert threshold_breaker.snapshot("openalex").opened_until == NOW + timedelta(seconds=20)

    now[0] += timedelta(seconds=21)
    assert await threshold_breaker.before_call("openalex") is None
    failed = provider_result("failed", error_code="HTTP_503")
    await threshold_breaker.record("openalex", failed)
    state = threshold_breaker.snapshot("openalex")
    assert state.state == "open"
    assert state.opened_until == now[0] + timedelta(seconds=30)


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Retry-After": "120"}, NOW + timedelta(seconds=120)),
        ({"Retry-After": "Thu, 23 Jul 2026 12:02:00 GMT"}, NOW + timedelta(minutes=2)),
        ({"Retry-After": "bad"}, None),
        ({"X-RateLimit-Reset": "3600"}, NOW + timedelta(hours=1)),
        ({"X-RateLimit-Reset": str(NOW.timestamp() + 3600)}, NOW + timedelta(hours=1)),
        ({"X-RateLimit-Reset": "bad"}, None),
        ({}, None),
    ],
)
def test_parse_retry_at_variants(headers: Mapping[str, str], expected: datetime | None) -> None:
    assert parse_retry_at(headers, now=NOW) == expected


def test_response_helpers_and_http_failure_classification() -> None:
    success = response_success(
        provider="openalex", request_id="r", started_at=NOW, papers=[provider_paper()]
    )
    empty = response_success(provider="openalex", request_id="r", started_at=NOW, papers=[])
    failure = response_failure(
        provider="openalex",
        request_id="r",
        started_at=NOW,
        status="unexpected",
        code="X",
        message="bad",
    )
    assert success.status == "success"
    assert empty.status == "empty"
    assert failure.status == "failed"

    limited = http_failure_result(
        provider="openalex",
        request_id="r",
        started_at=NOW,
        response=HTTPResponse(429, {"Retry-After": "2"}, {}, ""),
    )
    assert limited is not None and limited.error_code == "RATE_LIMITED"

    quota = http_failure_result(
        provider="openalex",
        request_id="r",
        started_at=NOW,
        response=HTTPResponse(
            429,
            {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "3600"},
            {},
            "",
        ),
    )
    assert quota is not None and quota.error_code == "DAILY_QUOTA_EXHAUSTED"

    generic = http_failure_result(
        provider="openalex",
        request_id="r",
        started_at=NOW,
        response=HTTPResponse(503, {}, None, "bad"),
    )
    assert generic is not None and generic.error_code == "HTTP_503"
    assert (
        http_failure_result(
            provider="openalex",
            request_id="r",
            started_at=NOW,
            response=HTTPResponse(200, {}, {}, ""),
        )
        is None
    )


@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (httpx.ConnectTimeout("connect"), "timeout", "CONNECTION_TIMEOUT"),
        (httpx.ReadTimeout("read"), "timeout", "READ_TIMEOUT"),
        (httpx.PoolTimeout("pool"), "timeout", "TIMEOUT"),
        (TimeoutError("late"), "timeout", "TIMEOUT"),
        (httpx.ConnectError("name resolution failed"), "failed", "DNS_FAILURE"),
        (httpx.ConnectError("offline"), "failed", "CONNECTION_FAILURE"),
        (RuntimeError("boom"), "failed", "TRANSPORT_ERROR"),
    ],
)
def test_transport_exception_classification(exc: Exception, status: str, code: str) -> None:
    result = transport_exception_result(
        provider="openalex", request_id="r", started_at=NOW, exc=exc
    )
    assert result.status == status
    assert result.error_code == code


def test_transport_exception_detects_socket_dns_cause() -> None:
    error = httpx.ConnectError("connect")
    error.__cause__ = socket.gaierror("dns")
    result = transport_exception_result(
        provider="openalex", request_id="r", started_at=NOW, exc=error
    )
    assert result.error_code == "DNS_FAILURE"


@pytest.mark.asyncio
async def test_httpx_transport_get_post_response_and_close() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"ok": True}, headers={"X-Test": "yes"})
        return httpx.Response(201, text="created")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    transport = HttpxTransport(client)
    got = await transport.get("https://example.test", params={"q": "x"})
    posted = await transport.post(
        "https://example.test", json_body={"x": 1}, data=None, headers={"X": "y"}
    )
    await transport.aclose()
    await client.aclose()
    assert got.json_data == {"ok": True}
    assert got.headers["x-test"] == "yes"
    assert posted.status_code == 201 and posted.json_data is None
    assert [request.method for request in requests] == ["GET", "POST"]

    owned = HttpxTransport()
    await owned.aclose()


def test_sqlite_verification_cache_ttls_corruption_failed_and_clear(tmp_path: Path) -> None:
    now = [100.0]
    cache = SQLiteVerificationAttemptCache(
        tmp_path / "verify.sqlite3",
        clock=lambda: now[0],
        success_ttl_seconds=10,
        negative_ttl_seconds=3,
    )
    assert cache.get("missing") is None
    cache.set("verified", VerificationAttempt(status="verified", method="exact"))
    cache.set("negative", VerificationAttempt(status="not_found"))
    cache.set("failed", VerificationAttempt(status="failed"))
    assert cache.get("verified") is not None
    assert cache.get("negative") is not None
    assert cache.get("failed") is None
    now[0] = 104
    assert cache.get("negative") is None
    assert cache.get("verified") is not None

    with cache._connection:
        cache._connection.execute(
            "INSERT OR REPLACE INTO literature_verification_cache(cache_key, payload, expires_at) "
            "VALUES (?, ?, ?)",
            ("corrupt", "not-json", 1000),
        )
    assert cache.get("corrupt") is None
    row = cache._connection.execute(
        "SELECT cache_key FROM literature_verification_cache WHERE cache_key = 'corrupt'"
    ).fetchone()
    assert row is None
    cache.clear()
    assert cache.get("verified") is None
    cache.close()


def test_json_and_layered_verification_caches(tmp_path: Path) -> None:
    readonly = JsonVerificationAttemptCache(tmp_path)
    assert readonly.get("key") is None
    readonly.set("key", VerificationAttempt(status="verified", method="exact"))
    readonly.clear()
    readonly.close()

    manifest = tmp_path / "verification-manifest.json"
    manifest.write_text("bad", encoding="utf-8")
    assert readonly.get("key") is None
    manifest.write_text(json.dumps([]), encoding="utf-8")
    assert readonly.get("key") is None
    manifest.write_text(json.dumps({"attempts": []}), encoding="utf-8")
    assert readonly.get("key") is None
    manifest.write_text(
        json.dumps({"schema_version": "1", "attempts": {"key": "bad"}}),
        encoding="utf-8",
    )
    assert readonly.get("key") is None
    manifest.write_text(
        json.dumps({"schema_version": "1", "attempts": {"key": {"fixture": "missing"}}}),
        encoding="utf-8",
    )
    assert readonly.get("key") is None

    writable = JsonVerificationAttemptCache(tmp_path, writable=True)
    writable.set("failed", VerificationAttempt(status="failed"))
    writable.set("key", VerificationAttempt(status="verified", method="exact"))
    assert writable.get("key") == VerificationAttempt(status="verified", method="exact")
    fixture = next(tmp_path.glob("verification-key*.json"), None)
    assert fixture is not None
    fixture.write_text("bad", encoding="utf-8")
    assert writable.get("key") is None
    writable.set("key", VerificationAttempt(status="verified", method="exact"))
    writable.clear()
    assert not manifest.exists()

    with pytest.raises(ValueError, match="at least one verification cache"):
        LayeredVerificationAttemptCache([])
    first = SpyVerificationCache()
    second = SpyVerificationCache(VerificationAttempt(status="not_found"))
    layered = LayeredVerificationAttemptCache([first, second])
    assert layered.get("key") == VerificationAttempt(status="not_found")
    layered.set("key", VerificationAttempt(status="verified", method="exact"))
    assert first.value is not None and second.value is not None
    layered.clear()
    layered.close()
    assert first.clear_calls == second.clear_calls == 1
    assert first.close_calls == second.close_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_message"),
    [
        (RuntimeError("offline"), "failed", "offline"),
        (HTTPResponse(404, {}, {}, ""), "not_found", None),
        (HTTPResponse(500, {}, {}, ""), "failed", "HTTP 500"),
        (HTTPResponse(200, {}, [], ""), "failed", "HTTP 200"),
        (HTTPResponse(200, {}, {"other": {}}, ""), "failed", "missing Crossref message"),
        (
            HTTPResponse(200, {}, {"message": {"DOI": "10.1000/other"}}, ""),
            "mismatch",
            "Crossref DOI mismatch",
        ),
        (
            HTTPResponse(
                200,
                {},
                {"message": {"DOI": "10.1000/reliable", "title": ["Different Title"]}},
                "",
            ),
            "mismatch",
            "Crossref title mismatch",
        ),
        (
            HTTPResponse(
                200,
                {},
                {"message": {"DOI": "10.1000/reliable", "title": ["Reliable Retrieval"]}},
                "",
            ),
            "verified",
            None,
        ),
    ],
)
async def test_crossref_verifier_branches(
    outcome: HTTPResponse | Exception, expected_status: str, expected_message: str | None
) -> None:
    transport = QueueTransport([outcome])
    attempt = await CrossrefVerifier(transport=transport, mailto="dev@example.com").verify(
        paper_record()
    )
    assert attempt.status == expected_status
    assert attempt.message == expected_message
    if transport.calls:
        assert transport.calls[0]["headers"] == {
            "User-Agent": "PaperAgent/0.2 (mailto:dev@example.com)"
        }


@pytest.mark.asyncio
async def test_crossref_without_doi_skips_transport() -> None:
    transport = QueueTransport([])
    attempt = await CrossrefVerifier(transport=transport).verify(paper_record(doi=None))
    assert attempt.status == "not_found"
    assert transport.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected_status", "expected_message"),
    [
        (RuntimeError("offline"), "failed", "offline"),
        (HTTPResponse(404, {}, {}, ""), "not_found", None),
        (HTTPResponse(500, {}, {}, ""), "failed", "HTTP 500"),
        (HTTPResponse(200, {}, [], ""), "failed", "HTTP 200"),
        (HTTPResponse(200, {}, {"other": {}}, ""), "failed", "missing DataCite data"),
        (
            HTTPResponse(200, {}, {"data": {"id": "10.1000/other", "attributes": {}}}, ""),
            "mismatch",
            "DataCite DOI mismatch",
        ),
        (
            HTTPResponse(
                200,
                {},
                {"data": {"id": "10.1000/reliable", "attributes": {}}},
                "",
            ),
            "verified",
            None,
        ),
    ],
)
async def test_datacite_verifier_branches(
    outcome: HTTPResponse | Exception, expected_status: str, expected_message: str | None
) -> None:
    attempt = await DataCiteVerifier(transport=QueueTransport([outcome])).verify(paper_record())
    assert attempt.status == expected_status
    assert attempt.message == expected_message


@pytest.mark.asyncio
async def test_datacite_without_doi_skips_transport() -> None:
    transport = QueueTransport([])
    attempt = await DataCiteVerifier(transport=transport).verify(paper_record(doi=None))
    assert attempt.status == "not_found"
    assert transport.calls == []


def test_verification_service_validation_budget_and_close() -> None:
    with pytest.raises(ValueError, match="positive"):
        VerificationService([], max_network_calls=0)
    with pytest.raises(ValueError, match="mode"):
        VerificationService([], mode="invalid")  # type: ignore[arg-type]

    cache = SpyVerificationCache()
    service = VerificationService([], max_network_calls=None, cache=cache)
    assert service.verification_budget() == {"maximum": None, "used": 0, "remaining": None}
    service.close()
    assert cache.close_calls == 1


@pytest.mark.asyncio
async def test_verification_service_cached_live_budget_mismatch_and_identifier_paths() -> None:
    cached = SpyVerificationCache(VerificationAttempt(status="verified", method="cached"))
    verifier = FakeAttemptVerifier([VerificationAttempt(status="failed")])
    service = VerificationService([verifier], mode="cache_first", cache=cached)
    result = await service.verify_one(paper_record())
    assert result.verification_status == "verified"
    assert result.verification_methods == ["cached"]
    assert verifier.calls == 0
    assert (await service.verify_one(paper_record())).verification_status == "verified"

    live_verifier = FakeAttemptVerifier([VerificationAttempt(status="verified", method="live")])
    live = VerificationService([live_verifier], mode="live", cache=cached)
    live_result = await live.verify_one(paper_record())
    assert live_result.verification_methods == ["live"]
    assert live_verifier.calls == 1

    mismatch = VerificationService(
        [
            FakeAttemptVerifier([VerificationAttempt(status="mismatch")]),
            FakeAttemptVerifier([VerificationAttempt(status="not_found")]),
        ]
    )
    assert (await mismatch.verify_one(paper_record())).verification_status == "suspicious"

    offline = VerificationService(
        [FakeAttemptVerifier([VerificationAttempt(status="verified")])], mode="offline"
    )
    assert (await offline.verify_one(paper_record())).verification_status == "pending"

    valid_arxiv = await VerificationService([]).verify_one(
        paper_record(doi=None, arxiv_id="2501.00001")
    )
    invalid_arxiv = await VerificationService([]).verify_one(
        paper_record(doi=None, arxiv_id="invalid")
    )
    no_identifier = await VerificationService([]).verify_one(paper_record(doi=None))
    assert valid_arxiv.verification_status == "verified"
    assert valid_arxiv.verification_methods == ["arxiv_id_syntax"]
    assert invalid_arxiv.verification_status == "suspicious"
    assert no_identifier.verification_status == "pending"


@pytest.mark.asyncio
async def test_verification_service_budget_exhaustion_and_verify_all() -> None:
    verifier = FakeAttemptVerifier(
        [
            VerificationAttempt(status="not_found"),
            VerificationAttempt(status="verified", method="second"),
        ]
    )
    service = VerificationService([verifier], max_network_calls=1)
    results = await service.verify_all([paper_record(), paper_record(title="Second")])
    assert [result.verification_status for result in results] == ["pending", "pending"]
    assert verifier.calls == 1
    assert service.verification_budget() == {"maximum": 1, "used": 1, "remaining": 0}

# Retrieval Resilience Contract

## Status

This document defines the bounded retrieval runtime added after the original v0.2 literature
foundation. It does not change the canonical `PaperRecord` merge contract. It changes how remote
provider calls are scheduled, cached, degraded, and replayed.

## Request path

```text
QueryLane
  -> normalized CacheKey
  -> in-process cache
  -> JSON fixture / SQLite cache
  -> per-provider rate limiter and concurrency gate
  -> provider circuit breaker
  -> provider adapter
  -> stale-cache fallback
  -> merge / verification / ranking
  -> PaperRecord
```

The academic search adapter remains sequential. It calls one provider at a time and stops when its
minimum evidence requirement is met. General searches use OpenAlex first and Semantic Scholar as the
normal escalation. arXiv is used first only for an explicit arXiv or preprint request, and otherwise
appears only as the final source for recent-paper searches.

## Runtime modes

| Mode | Cache behavior | Network behavior | Intended use |
|---|---|---|---|
| `offline` | read process cache, fixtures, and SQLite | forbidden for search and DOI verification | pytest, scorer regression, CI |
| `cache_first` | fresh cache first; live on miss; record result | allowed after cache miss | local development and new cases |
| `live` | bypass cache reads; still record responses | required | explicit provider integration tests |

`offline` returns `OFFLINE_CACHE_MISS` when no recorded response exists. It does not silently switch
to a live provider.

## Cache layers

The default runtime uses:

1. `InMemoryProviderCache` for low-latency process-local reuse and single-flight coalescing;
2. optional `JsonFixtureProviderCache` for version-controlled replay;
3. `SQLiteProviderCache` for durable local reuse across process restarts.

The cache key includes the normalized query, provider, serialized filters, result limit, and provider
contract version. A provider schema or requested-field change therefore invalidates old cache entries
without destructive migration.

Successful and verified-empty responses use long TTLs. Rate-limit and timeout results use short
negative TTLs so one provider incident is not retriggered for every query in the same run. A failed
live request may return an older successful entry with:

```json
{
  "cache_status": "stale_hit",
  "retrieval_mode": "stale_cache",
  "live_error_code": "RATE_LIMITED"
}
```

DOI verification attempts are persisted in a separate SQLite table keyed by verifier, canonical DOI,
and normalized title. This is required because a cached search result must not trigger a fresh
Crossref or DataCite call on every replay.

## Fixture recording

Configure a fixture directory and enable recording only while intentionally refreshing fixtures:

```bash
PAPERAGENT_RETRIEVAL_MODE=cache_first \
PAPERAGENT_RETRIEVAL_FIXTURES=tests/fixtures/retrieval/case_001 \
PAPERAGENT_RECORD_RETRIEVAL_FIXTURES=1 \
python scripts/run_academic_tailoring_retrieval_v1.py
```

Each directory contains `manifest.json` plus one normalized provider response per request hash. Commit
only reviewed, non-sensitive provider metadata. Disable recording for replay:

```bash
PAPERAGENT_RETRIEVAL_MODE=offline \
PAPERAGENT_RETRIEVAL_FIXTURES=tests/fixtures/retrieval/case_001 \
PAPERAGENT_RECORD_RETRIEVAL_FIXTURES=0 \
pytest -q
```

## Provider controls

Default limits are deliberately conservative:

| Provider | Max concurrency | Requests per minute | Effective spacing |
|---|---:|---:|---:|
| OpenAlex | 2 | 120 | 0.5 s |
| Semantic Scholar | 1 | 48 | 1.25 s |
| arXiv | 1 | 18 | 3.33 s |

OpenAlex accepts `OPENALEX_API_KEY`, uses an explicit field selection, and permits a page size up to
100 when a key is configured. Semantic Scholar accepts `SEMANTIC_SCHOLAR_API_KEY`. arXiv uses separate
8-second connect and 30-second read timeouts.

All instances in the same event loop share the same provider limiter. Per-service semaphores provide
the additional concurrency bound.

## Error and circuit policy

HTTP 429 handling reads `Retry-After`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`. The runtime
distinguishes `RATE_LIMITED` from `DAILY_QUOTA_EXHAUSTED`. Transport failures distinguish connection,
read, DNS, and generic transport errors.

Default circuit rules:

- two provider timeouts: open for 10 minutes;
- two rate limits without a reset header: open for 15 minutes;
- explicit quota reset: open until the provider reset time;
- after cooldown: allow one half-open probe;
- successful or verified-empty probe: close the circuit.

A circuit-open decision consumes no provider-call budget and may use stale cache. Failure of one source
does not fabricate a paper and does not fail the whole retrieval round when another source supplies
usable evidence.

## Test boundary

Unit and regression tests must use injected transports, SQLite temporary directories, or committed JSON
fixtures. Real provider tests remain opt-in under the existing `real_provider` and `network` markers.
Mock or fixture replay validates deterministic control flow; it is not evidence that live provider
quotas, schemas, or network paths are healthy.

# Retrieval Resilience Handoff

## Status

**Complete for offline implementation and regression validation; live provider behavior remains not verified.**

This work is intentionally stacked on Draft PR #60 so the evidence-contract repair and retrieval
infrastructure remain independently reviewable. Do not merge this branch directly to `master` without
first resolving the stacked base relationship.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Branch: `feat/retrieval-resilience-infrastructure`
- Review PR: Draft PR #61, base `fix/evidence-bound-module-contracts-local`
- Base implementation commit: `25c234611e0a253abd090973359a60aab21a98ac`
- Final implementation and coverage-test commit before this Handoff: `a8b9c64918ed4e47fe7d00e76f15f711030e0b32`
- Final Handoff commit: use the current branch HEAD shown by Draft PR #61

## Completed work

1. Added normalized provider cache keys and retained single-flight coalescing for identical requests.
2. Added L1 in-memory caching and L2 SQLite persistence across process restarts.
3. Added version-controlled JSON retrieval fixtures and DOI verification fixtures for deterministic
   offline replay.
4. Added short negative caching for rate limits and timeouts and stale-success fallback for provider
   outages.
5. Added `offline`, `cache_first`, and `live` retrieval modes. Offline mode blocks both search-provider
   and Crossref/DataCite network requests.
6. Added per-provider concurrency and shared request-rate controls.
7. Added circuit breakers with timeout/rate-limit thresholds, quota-reset deadlines, and half-open
   probes.
8. Added structured handling for `Retry-After`, `X-RateLimit-Remaining`, and
   `X-RateLimit-Reset`.
9. Added differentiated connection, read, DNS, rate-limit, quota, and provider-unavailable errors.
10. Added OpenAlex API-key support, selected-field requests, and larger page requests.
11. Added Semantic Scholar API-key support and conservative default throughput.
12. Added separate arXiv connect/read timeouts and an 18 requests/minute default, approximately one
    request every 3.33 seconds.
13. Changed source policy so ordinary academic search uses OpenAlex then Semantic Scholar; arXiv is
    first only for explicit preprint/arXiv requests and otherwise appears only as a final recent-paper
    fallback.
14. Added persistent DOI-verification caching so cached paper search results do not cause hidden
    Crossref/DataCite calls during replay.
15. Added environment configuration, architecture documentation, and focused resilience tests.
16. Added defensive coverage for corrupted cache rows, expired negative entries, fixture corruption,
    half-open probes, quota resets, HTTP/network error classification, provider parsing, and DOI
    verification degradation.
17. Fixed a related audit-policy defect: failed warning-level checks, including unknown licenses, now
    produce `REVISE` instead of an inconsistent `GO`.

## Main files

- `src/paperagent/literature/cache.py`
- `src/paperagent/literature/resilience.py`
- `src/paperagent/literature/service.py`
- `src/paperagent/literature/factory.py`
- `src/paperagent/literature/verification.py`
- `src/paperagent/literature/source_policy.py`
- `src/paperagent/literature/providers/base.py`
- `src/paperagent/literature/providers/openalex.py`
- `src/paperagent/literature/providers/semantic_scholar.py`
- `src/paperagent/literature/providers/arxiv.py`
- `src/paperagent/schemas/literature.py`
- `src/paperagent/cli.py`
- `docs/v0.2/RETRIEVAL_RESILIENCE.md`
- `tests/literature/test_retrieval_resilience.py`
- `tests/literature/test_retrieval_resilience_coverage.py`
- `tests/literature/test_provider_adapter_coverage.py`
- `tests/literature/test_verification_cache.py`
- `tests/literature/test_source_policy_routing.py`

## Architecture decisions

- Existing `ProviderResult`, merge, ranking, and canonical `PaperRecord` boundaries were preserved.
- The service owns scheduling, cache lookup, stale fallback, and circuit decisions; provider adapters
  remain responsible for request construction and response parsing.
- Persistent caches use only the Python standard-library SQLite module; no new runtime dependency was
  added.
- Cache keys include provider contract version so selected-field or schema changes invalidate old
  records without destructive migrations.
- Provider failures remain explicit metadata and never fabricate evidence.
- General searches do not fan out to every provider. Routing is sequential and stops after the
  adapter's minimum-results contract is met.
- Warnings in the method-audit policy are non-fatal but still require revision; they cannot silently
  produce `GO`.

## Validation performed

### Static checks

- `ruff format .`
- `ruff check .`
- strict `mypy`

These passed during the final source-and-test repair cycle. The clean-tree standard CI run after this
Handoff commit is the authoritative confirmation for both Python versions.

### Offline test suite and coverage

The exact standard-CI command was reproduced on Python 3.12:

```text
795 passed, 11 skipped, 3 warnings in 21.76s
Required test coverage of 90.0% reached. Total coverage: 90.05%
```

The skipped tests were the Playwright browser test and opt-in real LLM/provider tests. The three
warnings were one Starlette/httpx deprecation warning and two pre-existing Pydantic serializer warnings
in runner tests.

The coverage result is combined line-and-branch coverage, not line coverage alone. The coverage gate
was not lowered.

### What these tests prove

- deterministic cache behavior;
- process-restart persistence;
- cache corruption cleanup;
- negative-cache suppression and expiry;
- single-flight behavior;
- stale-cache fallback;
- offline no-network behavior;
- circuit opening, half-open probing, and cooldown behavior;
- quota-header and HTTP-date parsing;
- transport-error classification;
- DOI verification replay and degradation;
- provider request shaping and sparse metadata parsing;
- capability-based routing;
- compatibility with the repository's offline regression suite.

They do **not** prove live quota, provider availability, or real network behavior.

## Not executed / not verified

- Live OpenAlex search with a real API key.
- Live Semantic Scholar search with a real API key.
- Live arXiv network-path and timeout behavior.
- Live Crossref and DataCite verification.
- Real `Retry-After` and daily-quota reset behavior from provider responses.
- Recording and review of retrieval fixtures for cases 001–006.
- Browser smoke test because Playwright was not installed in the standard test environment.
- Real LLM and real provider tests because their opt-in environment variables and credentials were not
  enabled.

## Known limitations

- SQLite cache coordination is process-safe at the database level, while single-flight and circuit
  state are process-local. Multiple application processes can still issue the same first cache-miss
  request concurrently.
- Existing committed fixtures must be reviewed for licensing and sensitive metadata before addition.
- The current PR is stacked on PR #60 and should be rebased or have its base changed only after #60 is
  resolved.
- Live integration tests remain intentionally opt-in and should not become default PR checks.

## Next developer steps

1. Confirm Draft PR #61 remains based on `fix/evidence-bound-module-contracts-local` while PR #60 is
   unresolved.
2. Confirm the final clean-tree CI reports Ruff, Mypy, Python 3.11/3.12 pytest, and combined coverage
   above 90%.
3. With approved provider credentials, run a bounded live smoke test:

```bash
PAPERAGENT_RUN_REAL_PROVIDER=1 \
PAPERAGENT_RETRIEVAL_MODE=live \
pytest -m "real_provider and network" -q
```

4. Record one case at a time in `cache_first` mode, inspect the JSON metadata, then commit only reviewed
fixtures:

```bash
PAPERAGENT_RETRIEVAL_MODE=cache_first \
PAPERAGENT_RETRIEVAL_FIXTURES=tests/fixtures/retrieval/case_001 \
PAPERAGENT_RECORD_RETRIEVAL_FIXTURES=1 \
python scripts/run_academic_tailoring_retrieval_v1.py
```

5. Replay the case with all network access forbidden:

```bash
PAPERAGENT_RETRIEVAL_MODE=offline \
PAPERAGENT_RETRIEVAL_FIXTURES=tests/fixtures/retrieval/case_001 \
PAPERAGENT_RECORD_RETRIEVAL_FIXTURES=0 \
pytest -q
```

## Final state

`complete` for implementation and offline verification; `pending live verification` for public
provider behavior and case 001–006 fixture recording.

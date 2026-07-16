# PaperAgent v0.2 Literature Retrieval Handoff

> Status: `OFFLINE IMPLEMENTATION COMPLETE / REAL NETWORK SMOKE PENDING`  
> Repository: `ZyfNO2/PaperAgent`  
> Branch: `feat/v0.2-literature-retrieval-foundation`  
> Base: `feat/v0.1-offline-skeleton`

## 1. Completed scope

- Added the v0.2 literature schema family: query plans, lanes, provider results, normalized papers,
  source records, merge warnings, ranking features, coverage reports, and retrieval metrics.
- Added real HTTP adapters for OpenAlex, Semantic Scholar, and arXiv discovery.
- Added Crossref and DataCite DOI verification with deterministic fallback behavior.
- Kept real HTTP access behind provider protocols and an injectable transport for offline tests.
- Distinguished `success`, verified `empty`, `rate_limited`, `timeout`, and `failed` outcomes.
- Added concurrent source fan-out, per-provider semaphores, whole-round deadlines, and partial-result
  completion when one source fails.
- Added cache keys containing normalized query, provider, filters, limit, and contract version.
- Added success TTL, short negative TTL, request coalescing, and failure non-caching.
- Added DOI/arXiv/provider-ID/title-year-author deduplication and provenance-preserving merge.
- Added deterministic explainable ranking and Coverage Gate decisions.
- Limited retrieval to two rounds and focused rewriting to one retry.
- Added an adapter that feeds normalized v0.2 results into the frozen v0.1 Retrieval Subgraph.
- Preserved v0.1 Fake Search behavior and all existing graph tests.
- Added opt-in real-provider smoke tests that are skipped by default.

## 2. Key architecture decisions

1. v0.2 enhances the existing Retrieval Subgraph; it does not add top-level LangGraph nodes.
2. Provider failure never produces a fabricated `PaperRecord` and never becomes a normal cache hit.
3. A verified empty response is different from a provider or network failure.
4. Duplicate records merge metadata and provenance instead of selecting a citation-count winner.
5. Stable identifiers take priority: DOI, arXiv ID, provider mapping, then normalized bibliographic
   identity.
6. Approximate title matches remain suspicious and carry an explicit warning.
7. Ranking is deterministic and explainable; citation count is not a primary score.
8. Required Evidence Gaps cannot be silently removed by the retry mechanism.
9. Real-provider variability is isolated from deterministic offline fixtures.
10. v0.1 engine/schema/fixture version constants remain frozen; v0.2 has a separate literature
    contract version.

## 3. Main files

```text
src/paperagent/schemas/literature.py
src/paperagent/literature/
├── adapter.py
├── cache.py
├── coverage.py
├── factory.py
├── merge.py
├── normalize.py
├── planner.py
├── ranking.py
├── service.py
├── verification.py
└── providers/
    ├── base.py
    ├── openalex.py
    ├── semantic_scholar.py
    └── arxiv.py

src/paperagent/retrieval/search_tool.py
src/paperagent/retrieval/verify_evidence.py
tests/literature/
tests/real_provider/test_literature_smoke.py
.github/workflows/paperagent-ci.yml
```

## 4. Offline verification

Executed in the cloud development workspace:

```text
ruff check .                                      PASS
ruff format --check .                             PASS
mypy --config-file pyproject.toml                 PASS
pytest -q                                         PASS (147 passed, 1 skipped)
pytest --cov=paperagent --cov-branch ...          PASS (93.15%, threshold >= 90%)
```

The skipped test is the explicitly marked real-network provider smoke suite. It is not counted as
real end-to-end evidence.

## 5. Real tests not executed

- OpenAlex live search.
- arXiv live search.
- Semantic Scholar live search and authenticated quota behavior.
- Crossref live DOI verification.
- DataCite live DOI fallback.
- Real latency, rate-limit, upstream schema drift, and production network behavior.

These require outbound network access and, for polite/identified API usage, a contact email. A
Semantic Scholar API key is optional but useful for quota verification.

## 6. Real smoke procedure

Prepare environment variables without committing them:

```bash
export PAPERAGENT_RUN_REAL_PROVIDER=1
export PAPERAGENT_CONTACT_EMAIL='your-email@example.com'
export SEMANTIC_SCHOLAR_API_KEY=''  # optional
pytest -m 'real_provider and network' -q -vv
```

Expected success:

- OpenAlex returns `status=success` for a known academic query;
- arXiv returns `status=success` for the same query;
- Crossref verifies DOI `10.1038/nature14539` exactly;
- no credential value appears in logs or state.

Return the full pytest output and any provider status/error payloads if a live smoke fails.

## 7. Known limitations

- The default cache is process-local memory; it is not durable or shared across workers.
- The deterministic focused rewriter is a baseline, not a real LLM query-planning adapter.
- Provider schemas are normalized from current documented response shapes but live schema drift has
  not been verified in this environment.
- No PDF downloading, parsing, embedding, vector database, citation graph expansion, web API, SSE,
  worker, or UI is included in v0.2.
- Verification confirms identity/metadata, not scientific quality or truth of claims.
- Ranking is lexical/deterministic and does not claim benchmark superiority.

## 8. Next developer steps

1. Run the opt-in real-provider smoke suite with outbound network access.
2. Record provider latency, rate-limit headers, and any schema deviations.
3. Fix adapters without weakening offline error-state and cache-poisoning contracts.
4. Review the Draft PR against `feat/v0.1-offline-skeleton`.
5. Do not merge v0.2 directly to `master` before the v0.1 release sequence is resolved.

## 9. Release state

`PARTIAL COMPLETE`: all planned offline v0.2 literature-retrieval foundation work is implemented and
verified. Real provider smoke remains pending; no merge has been performed.

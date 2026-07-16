# PaperAgent

PaperAgent `v0.2` extends the frozen v0.1 LangGraph workflow with a bounded, explainable,
multi-source academic-literature retrieval core. The v0.1 graph, state, prompts, deterministic
fixtures, and repair contracts remain compatible and versioned independently.

## Current status

```text
Package version: v0.2.0
Workflow engine contract: v0.1 (frozen)
Literature retrieval contract: v0.2
Stage: offline implementation complete
Release status: real-provider smoke pending; Draft PR only
```

## v0.2 implemented scope

- structured `LiteratureQueryPlan`, `QueryLane`, `ProviderResult`, `PaperRecord`, and
  `CoverageReport` contracts;
- OpenAlex, Semantic Scholar, and arXiv discovery adapters;
- Crossref and DataCite DOI verification adapters;
- explicit `success / empty / rate_limited / timeout / failed` provider states;
- concurrent provider fan-out with per-provider limits and a whole-round deadline;
- deterministic request coalescing and separate success/negative TTL caches;
- failure-safe caching: timeout, rate-limit, malformed, and failed responses never poison the
  normal result cache;
- DOI, arXiv ID, provider ID, and title/year/first-author deduplication;
- provenance-preserving metadata merge with conflict warnings;
- explainable relevance, Evidence Gap coverage, verification, recency, and diversity ranking;
- citation count used only as a weak tie-breaker;
- deterministic Coverage Gate with at most one focused retry and at most two retrieval rounds;
- compatibility adapter into the existing v0.1 Retrieval Subgraph;
- separately marked real-network smoke tests, skipped by default.

## Preserved v0.1 scope

- frozen Pydantic schema and TypedDict State contracts;
- versioned production prompts and deterministic Fake LLM/Search providers;
- bounded top-level LangGraph and independent retrieval/method repair budgets;
- checkpoint-backed Human-in-the-Loop interrupt/resume;
- redacted Trace metadata and idempotent in-memory persistence.

## Offline verification

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Default tests do not access the network or require API credentials. Real-provider smoke tests are
opt-in:

```bash
PAPERAGENT_RUN_REAL_PROVIDER=1 \
PAPERAGENT_CONTACT_EMAIL=you@example.com \
pytest -m 'real_provider and network' -q
```

`SEMANTIC_SCHOLAR_API_KEY` is optional. Do not commit real credentials.

## Development contracts

- [v0.1 execution plan](docs/v0.1/EXECUTION_PLAN.md)
- [v0.1 graph and nodes](docs/v0.1/GRAPH_AND_NODES.md)
- [v0.1 state contracts](docs/v0.1/STATE_CONTRACTS.md)
- [v0.1 implementation handoff](docs/v0.1/HANDOFF.md)
- [v0.2 literature retrieval design](docs/planning/V0.2_LITERATURE_RETRIEVAL.md)
- [v0.2 implementation handoff](docs/v0.2/HANDOFF.md)

## Branch policy

- `master`: clean release line;
- `feat/v0.1-offline-skeleton`: v0.1 Draft review branch;
- `feat/v0.2-literature-retrieval-foundation`: v0.2 Draft development branch;
- `backup/legacy-pre-v0.1-20260716`: read-only legacy backup.

Do not merge v0.2 directly into `master`. Review it against the v0.1 implementation branch first,
then decide the release sequence explicitly.

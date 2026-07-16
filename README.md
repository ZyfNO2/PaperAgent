# PaperAgent

PaperAgent `v0.3` adds a durable task API to the bounded v0.1 workflow and v0.2 literature-retrieval
core. The implementation remains intentionally single-process and SQLite-backed for MVP deployment.

## Current status

```text
Package version: v0.3.0
Workflow engine contract: v0.1 (frozen)
Literature retrieval contract: v0.2
Task API contract: v0.3
Stage: offline MVP implementation complete
Release status: Draft PR / real-provider and public deployment smoke pending
```

## v0.3 implemented scope

- FastAPI application factory with injectable workflow executor;
- SQLite-backed task metadata, results, typed errors, and ordered progress events;
- single-process, single-concurrency background runner;
- required idempotency keys with payload-conflict detection;
- queued/running/cancel-requested/cancelled/succeeded/failed state machine;
- polling and SSE generated from the same durable event cursor;
- cooperative cancellation at workflow boundaries;
- fail-closed restart recovery that never silently replays active provider calls;
- bounded 16 KiB event payloads and 180 KB terminal results;
- redacted unknown-exception handling;
- adapter for the existing LangGraph workflow.

## Preserved v0.2 and v0.1 scope

- OpenAlex, Semantic Scholar, and arXiv discovery adapters;
- Crossref and DataCite DOI verification;
- deterministic deduplication, provenance merge, ranking, coverage audit, cache, and retry budgets;
- frozen v0.1 graph/state/prompt/fixture contracts;
- deterministic Fake LLM/Search fixtures, bounded repair routes, HITL checkpoint semantics, and
  redacted traces.

## Task API

```text
POST /v1/tasks
GET  /v1/tasks/{task_id}
GET  /v1/tasks/{task_id}/events
GET  /v1/tasks/{task_id}/events/stream
POST /v1/tasks/{task_id}/cancel
GET  /healthz
```

`POST /v1/tasks` requires an `Idempotency-Key` header. This version has no authentication or tenant
isolation and must be treated as a local or trusted-network evaluation service, not a public
multi-tenant deployment.

## Verification

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Default tests do not access the network. Real-provider smoke tests remain opt-in:

```bash
PAPERAGENT_RUN_REAL_PROVIDER=1 \
PAPERAGENT_CONTACT_EMAIL=you@example.com \
pytest -m 'real_provider and network' -q
```

## Development contracts

- [stacked v0.3-v0.5 MVP sequence](docs/planning/MVP_RELEASE_SEQUENCE_V0.3_V0.5.md)
- [v0.3 execution plan](docs/v0.3/EXECUTION_PLAN.md)
- [v0.2 implementation handoff](docs/v0.2/HANDOFF.md)
- [v0.2 literature retrieval design](docs/planning/V0.2_LITERATURE_RETRIEVAL.md)
- [v0.1 implementation handoff](docs/v0.1/HANDOFF.md)

## Stacked branch policy

```text
feat/v0.1-offline-skeleton
  -> feat/v0.2-literature-retrieval-foundation
      -> feat/v0.3-durable-task-api-mvp
          -> feat/v0.4-review-export-mvp
              -> feat/v0.5-pwa-shell-mvp
```

Each version is reviewed through its own Draft PR against the immediately preceding branch. No
version is merged automatically.

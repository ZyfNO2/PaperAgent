# PaperAgent

PaperAgent `v0.4` adds durable paper-review decisions and deterministic evidence exports on top of
the bounded v0.1 workflow, v0.2 literature retrieval, and v0.3 SQLite task API.

## Current status

```text
Package version: v0.4.0
Workflow engine contract: v0.1 (frozen)
Literature retrieval contract: v0.2
Task API contract: v0.3
Review/export contract: v0.4
Stage: offline MVP implementation complete
Release status: stacked Draft PR / real-provider and public deployment smoke pending
```

## v0.4 implemented scope

- durable per-paper `pending / accepted / rejected` decisions and favorite state;
- optimistic version checks with repeat-safe identical updates;
- stable opaque cursor pagination ordered by paper ID;
- paper cards derived only from succeeded task evidence with `source_type=paper`;
- failed-verification or rejected evidence cannot be accepted in the MVP;
- deterministic JSON, Markdown, and BibTeX exports;
- accepted, favorite, and all export selections;
- SHA-256, item count, media type, and filename export metadata.

## Preserved v0.3-v0.1 scope

- FastAPI task submission, polling, SSE, cancellation, and health endpoints;
- SQLite task/result/error/event persistence and a single-process runner;
- idempotency conflict detection and fail-closed restart semantics;
- OpenAlex, Semantic Scholar, arXiv, Crossref, and DataCite adapters;
- deterministic merge, ranking, coverage, cache, and retry budgets;
- frozen v0.1 graph/state/prompt/fixture contracts and deterministic offline fixtures.

## API

```text
POST /v1/tasks
GET  /v1/tasks/{task_id}
GET  /v1/tasks/{task_id}/events
GET  /v1/tasks/{task_id}/events/stream
POST /v1/tasks/{task_id}/cancel
GET  /v1/tasks/{task_id}/papers
PUT  /v1/tasks/{task_id}/papers/{paper_id}/review
GET  /v1/tasks/{task_id}/exports/{json|markdown|bibtex}
GET  /healthz
```

The service still has no authentication or tenant isolation. Treat it as a local, single-user, or
trusted-network evaluation service.

## Verification

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Default tests do not access the network. Real-provider smoke tests remain opt-in.

## Development contracts

- [stacked v0.3-v0.5 MVP sequence](docs/planning/MVP_RELEASE_SEQUENCE_V0.3_V0.5.md)
- [v0.4 execution plan](docs/v0.4/EXECUTION_PLAN.md)
- [v0.3 handoff](docs/v0.3/HANDOFF.md)
- [v0.2 handoff](docs/v0.2/HANDOFF.md)
- [v0.1 handoff](docs/v0.1/HANDOFF.md)

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

# PaperAgent

PaperAgent `v0.5` adds a package-served responsive PWA shell over the bounded v0.1 workflow, v0.2
literature retrieval, v0.3 durable task API, and v0.4 review/export layer.

## Current status

```text
Package version: v0.5.0
Workflow engine contract: v0.1 (frozen)
Literature retrieval contract: v0.2
Task API contract: v0.3
Review/export contract: v0.4
Web shell contract: v0.5
Stage: offline MVP implementation complete
Release status: stacked Draft PR / browser E2E, real-provider, and public deployment smoke pending
```

## v0.5 implemented scope

- responsive `/app` and `/app/{task_id}` routes served directly by FastAPI;
- package-local HTML, CSS, JavaScript, manifest, service worker, and SVG icon;
- research task submission with generated idempotency keys;
- shareable task URLs and local recent-task history;
- polling-first progress with SSE enhancement and cancellation;
- paper-card filtering, acceptance/rejection, pending state, and favorites;
- JSON, Markdown, and BibTeX downloads with checksum feedback;
- loading, offline, failed, cancelled, empty, and terminal UI states;
- mobile layout, semantic markup, focus states, and reduced-motion support;
- restrictive CSP and shell-only service-worker caching.

The browser contains no Agent, retrieval, ranking, prompt, or provider logic. All decisions remain in
the Python service.

## Preserved v0.4-v0.1 scope

- durable paper decisions, stable pagination, and deterministic exports;
- FastAPI task submission, polling, SSE, cancellation, and health endpoints;
- SQLite persistence and a single-process runner;
- multi-source literature adapters and deterministic retrieval contracts;
- frozen v0.1 graph/state/prompt/fixture contracts.

## Main routes

```text
GET  /app
GET  /app/{task_id}
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
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Default tests do not access the network. Real-provider and real-browser E2E tests remain separate.

## Development contracts

- [stacked v0.3-v0.5 MVP sequence](docs/planning/MVP_RELEASE_SEQUENCE_V0.3_V0.5.md)
- [v0.5 execution plan](docs/v0.5/EXECUTION_PLAN.md)
- [v0.4 handoff](docs/v0.4/HANDOFF.md)
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

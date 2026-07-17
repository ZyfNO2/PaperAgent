# PaperAgent MVP Release Sequence: v0.3-v0.5

> Status: `FROZEN FOR STACKED DRAFT PR EXECUTION`  
> Base: `feat/v0.2-literature-retrieval-foundation`  
> Principle: ship the smallest deployable vertical slice; defer infrastructure until measured need.

## 1. Why the earlier draft is reduced

The v0.2 planning document correctly constrained the product to FastAPI, SQLite, a single-process
runner, SSE, polling, and a lightweight web shell. It did not freeze a v0.4 boundary and left several
production-scale options adjacent to the MVP. This execution sequence makes the dependencies explicit
and removes premature infrastructure.

The stacked branch order is:

```text
feat/v0.2-literature-retrieval-foundation
  -> feat/v0.3-durable-task-api-mvp
      -> feat/v0.4-review-export-mvp
          -> feat/v0.5-pwa-shell-mvp
```

Every branch gets its own Draft PR against the immediately preceding branch. No branch is merged
automatically.

## 2. v0.3 — Durable Task API MVP

### User outcome

A client can submit one research request, receive a `task_id` immediately, observe progress through
polling or SSE, cancel queued/running work, and retrieve a bounded terminal result.

### Included

- FastAPI application factory;
- SQLite tasks and ordered event log;
- single-process, single-concurrency background runner;
- required idempotency key with conflict detection;
- task states: queued, running, cancel_requested, cancelled, succeeded, failed;
- polling and SSE generated from the same durable events;
- cooperative cancellation at workflow boundaries;
- fail-closed restart recovery for in-flight tasks;
- 16 KiB event payload and 180 KB result limits;
- injectable executor plus adapter for the existing LangGraph workflow.

### Explicitly deferred

- Redis, PostgreSQL, ARQ/RQ/Celery, multi-process workers;
- authentication, quotas, billing, organizations;
- automatic replay of in-flight provider calls after restart;
- remote blob/object storage;
- frontend;
- PDF parsing and vector retrieval.

### Acceptance

- POST returns 202 and a task ID without waiting for execution;
- duplicate idempotency key with identical payload reuses the task;
- duplicate key with different payload returns 409;
- queued cancellation causes zero executor/provider calls;
- polling and SSE expose the same ordered event cursor;
- process restart never silently repeats active work;
- Python 3.11/3.12 CI, lint, type checking, tests, and >=90% branch coverage pass.

## 3. v0.4 — Review and Export MVP

### User outcome

A user can review the final paper cards, accept/reject/favorite each item, and export the reviewed
Evidence Bundle as JSON, Markdown, or BibTeX.

### Included

- durable paper decisions keyed by `(task_id, paper_id)`;
- optimistic version field for repeat-safe updates;
- stable cursor pagination for paper cards;
- accepted/rejected/favorite filters;
- deterministic JSON, Markdown, and BibTeX exporters;
- export manifest containing task/version/count/checksum;
- API endpoints only; no UI.

### Explicitly deferred

- collaborative review, comments, sharing permissions;
- citation-style engines and thousands of CSL styles;
- PDF/full-text download;
- cloud object storage;
- user accounts.

### Acceptance

- decisions survive process restart;
- repeated identical updates are idempotent;
- stale versions return 409;
- pagination order is stable;
- exports contain only the requested review set and deterministic checksums;
- invalid or failed-verification papers cannot be represented as accepted evidence without an explicit
  override contract (override is not part of MVP).

## 4. v0.5 — PWA Shell MVP

### User outcome

A browser user can submit a question, watch task progress, review paper cards, update decisions, and
download exports without using an API client.

### Included

- one static, responsive PWA shell served by FastAPI;
- task form and optional basic filters;
- polling-first progress with SSE enhancement;
- paper cards with verification/gap labels;
- accept/reject/favorite controls;
- JSON/Markdown/BibTeX download actions;
- task URL routing and local recent-task history;
- accessible loading, empty, error, cancelled, and terminal states.

### Explicitly deferred

- native mini program package;
- Next.js server, Node backend, SSR, component framework migration;
- login, payments, collaboration;
- PDF reader, trace debugger, admin console;
- offline execution and background sync.

### Acceptance

- production build is not required; static assets run from the Python package;
- no Agent logic exists in the browser;
- refresh preserves task navigation through the task ID URL;
- mobile-width interaction is usable;
- browser contract tests cover submit, progress, review, export, and failure states;
- existing API and offline workflow tests remain green.

## 5. Post-MVP execution options

Only after real usage evidence should the project consider:

1. true LangGraph SQLite checkpoint resume and human-input resume API;
2. multiple workers with lease/heartbeat semantics;
3. PostgreSQL and Redis when one-process SQLite limits are measured;
4. authenticated user workspaces;
5. object storage for large artifacts;
6. PDF evidence extraction and optional vector retrieval;
7. a native mini program shell if PWA usage proves insufficient.

Each option requires its own measurable trigger, migration plan, and backward-compatibility tests.

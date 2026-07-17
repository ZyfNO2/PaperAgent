# PaperAgent v0.3 Durable Task API MVP Execution Plan

> Status: `IMPLEMENTED`  
> Base: `feat/v0.2-literature-retrieval-foundation`  
> Branch: `feat/v0.3-durable-task-api-mvp`

## Goal

Expose the existing bounded PaperAgent workflow through a durable, observable task API without
introducing distributed infrastructure. A request must return a task ID immediately; execution,
progress, cancellation, and terminal state must survive normal process restarts through SQLite.

## Architecture

```text
HTTP client
  -> FastAPI
      -> SQLite task + ordered event log
      -> single-process task runner
          -> TaskExecutor protocol
              -> existing LangGraph adapter

polling ----\
             -> same SQLite task/event state
SSE --------/
```

## Included contracts

- `POST /v1/tasks` with required `Idempotency-Key`;
- `GET /v1/tasks/{task_id}`;
- `GET /v1/tasks/{task_id}/events` with cursor pagination;
- `GET /v1/tasks/{task_id}/events/stream` using SSE;
- `POST /v1/tasks/{task_id}/cancel`;
- task states: queued, running, cancel_requested, cancelled, succeeded, failed;
- SQLite durability for task metadata, terminal result, errors, and ordered events;
- single-concurrency background runner;
- cooperative cancellation at workflow boundaries;
- fail-closed restart handling for in-flight tasks;
- 16 KiB event payload and 180 KB terminal result limits;
- redacted execution failures;
- injectable executor and a LangGraph adapter.

## Idempotency

The idempotency key is bound to a canonical request hash:

- same key + same payload -> existing task is returned;
- same key + different payload -> HTTP 409;
- the task is never submitted twice by an API retry.

## Cancellation

- queued task: becomes cancelled before the runner can claim it;
- running task: becomes cancel_requested and is stopped at the next workflow boundary;
- an already-running provider call is not force-killed in this MVP;
- terminal cancellation requests are repeat-safe and return `accepted=false`.

## Restart semantics

SQLite preserves queued and terminal tasks. Tasks found in `running` or `cancel_requested` after a
process restart are changed to failed with `PROCESS_RESTARTED` and `retryable=true`. The MVP does not
silently replay provider calls because that could duplicate remote side effects or costs.

True graph checkpoint resume and provider-call leases are post-MVP work.

## Security and deployment boundary

This version has no authentication, user isolation, quota, or billing. It is suitable for local,
single-user, or trusted-network evaluation only. It must not be exposed as a public multi-tenant API
without an authentication and authorization layer.

Progress events contain bounded status metadata, not full prompts or credentials. Unknown exceptions
are converted to a typed error containing only the exception class name.

## Explicitly excluded

- Redis, PostgreSQL, ARQ, RQ, Celery, and external workers;
- multi-process task claiming and leases;
- user accounts and organizations;
- object storage;
- frontend;
- PDF parsing, embeddings, and vector databases;
- automatic replay of interrupted provider calls.

## Acceptance gates

```text
Python 3.11 and 3.12
Ruff lint
Ruff format check
Mypy strict
All default offline tests
Branch coverage >= 90%
Real-provider tests reported separately
No committed secrets
Draft PR only; no automatic merge
```

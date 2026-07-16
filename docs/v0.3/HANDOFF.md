# PaperAgent v0.3 Durable Task API MVP Handoff

> Status: `OFFLINE MVP COMPLETE / TRUSTED-NETWORK ONLY`  
> Repository: `ZyfNO2/PaperAgent`  
> Branch: `feat/v0.3-durable-task-api-mvp`  
> Base: `feat/v0.2-literature-retrieval-foundation`  
> Draft PR: `#8`

## Completed scope

- Added frozen v0.3 task API contracts and package version `0.3.0`.
- Added FastAPI endpoints for task submission, state polling, ordered event polling, SSE, and
  cancellation.
- Added SQLite persistence for task requests, canonical request hashes, results, typed errors, and
  ordered events.
- Added a single-process task runner with one active task at a time.
- Added required idempotency keys: identical retries reuse a task; conflicting payloads fail with 409.
- Added queued cancellation that prevents executor/provider calls.
- Added cooperative running cancellation at workflow boundaries.
- Added fail-closed restart recovery for in-flight tasks; active provider calls are never replayed
  silently.
- Added 16 KiB event and 180 KB terminal-result limits.
- Added redacted unknown-exception handling.
- Added an injectable `TaskExecutor` protocol and an adapter for the existing LangGraph workflow.
- Added polling and SSE over the same SQLite event cursor.

## Main files

```text
src/paperagent/api/
├── __init__.py
├── app.py
├── executor.py
├── models.py
├── repository.py
└── runner.py

tests/api/
├── test_app.py
├── test_repository.py
└── test_runner_executor.py

docs/v0.3/EXECUTION_PLAN.md
docs/planning/MVP_RELEASE_SEQUENCE_V0.3_V0.5.md
```

## API contract

```text
POST /v1/tasks
GET  /v1/tasks/{task_id}
GET  /v1/tasks/{task_id}/events
GET  /v1/tasks/{task_id}/events/stream
POST /v1/tasks/{task_id}/cancel
GET  /healthz
```

## Verification evidence

A single audited GitHub Actions run executed the complete release gate independently on Python 3.11
and Python 3.12.

```text
Run ID:                  29540866548
Verified head:           a40bc479ebc1cf6ab8ae0b7b07470f87c77096d9
Python 3.11 install:     PASS
Python 3.11 Ruff:        PASS
Python 3.11 format:      PASS
Python 3.11 Mypy:        PASS
Python 3.11 tests:       167 passed, 1 skipped
Python 3.11 coverage:    93.35%
Python 3.12 install:     PASS
Python 3.12 Ruff:        PASS
Python 3.12 format:      PASS
Python 3.12 Mypy:        PASS
Python 3.12 tests:       167 passed, 1 skipped
Python 3.12 coverage:    93.41%
Coverage threshold:      90%
```

The skipped test is the explicitly marked real-network literature-provider smoke suite inherited
from v0.2. It is not represented as completed end-to-end evidence.

## Important semantics

1. The runner is single-process and single-concurrency.
2. SQLite persists queue state and terminal results, but it is not a distributed lease system.
3. On restart, queued tasks remain queued; running/cancel-requested tasks become retryable failed
   tasks with `PROCESS_RESTARTED`.
4. This prevents accidental duplicate provider costs or side effects.
5. Cancellation cannot forcefully terminate an HTTP call already executing; it prevents later graph
   boundaries from starting.
6. SSE is an alternate view of the durable event log, not a separate state source.

## Not completed

- public deployment smoke;
- authentication, authorization, user isolation, quotas, and billing;
- multi-process or multi-host workers;
- Redis/PostgreSQL task leasing;
- true graph checkpoint resume after process death;
- force-cancellation of an in-flight provider HTTP request;
- real OpenAlex/Semantic Scholar/arXiv/Crossref/DataCite smoke inherited from v0.2;
- frontend;
- PDF parsing, embedding, and vector retrieval.

## Deployment warning

This API has no authentication or tenant isolation. It is suitable only for local development,
single-user deployment, or a trusted private network. Do not expose it directly to the public
internet.

## Next branch

`feat/v0.4-review-export-mvp` should be created from the final v0.3 branch and should add only durable
paper review decisions, stable paper-card pagination, and deterministic JSON/Markdown/BibTeX export.
It must remain a separate Draft PR and must not add accounts, collaboration, object storage, PDF
processing, or a frontend.

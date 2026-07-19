# ADR 0001: Use a Single-Process Durable Runner for the MVP

- Status: Accepted
- Context: v0.3+

## Decision

Run one asynchronous worker loop in the FastAPI process. Persist tasks and events in SQLite before execution. Recover interrupted in-flight tasks as failed after restart.

## Rationale

- preserves asynchronous HTTP semantics without introducing Redis/Celery infrastructure;
- makes task claiming, cancellation, and crash behavior directly testable;
- avoids pretending that an MVP supports distributed leases or exactly-once execution;
- keeps provider calls behind a narrow `TaskExecutor` boundary that can later move to workers.

## Consequences

- one process owns execution throughput;
- application shutdown stops new claims and waits for bounded cleanup;
- horizontal API replicas are not supported;
- running calls are not automatically replayed after restart.

## Migration trigger

Adopt PostgreSQL plus a distributed queue when multiple replicas, tenant isolation, independent autoscaling, delayed retries, or durable distributed leases become requirements.

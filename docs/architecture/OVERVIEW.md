# PaperAgent Architecture Overview

## Purpose

PaperAgent is a bounded, single-user research-agent backend. It demonstrates how to combine a durable HTTP task contract, deterministic workflow state, retrieval providers, structured LLM calls, human review, export, and controlled plugins without presenting an MVP as a public multi-tenant service.

## Runtime topology

```text
Browser / CLI
    |
    v
FastAPI task contract
    |-- POST /v1/tasks (idempotent submission)
    |-- GET task and durable events
    |-- SSE event stream
    |-- cancel / review / export
    |-- readiness / diagnostics / metrics
    v
SQLiteTaskRepository + SQLiteReviewRepository
    |-- task state machine
    |-- append-only task events
    |-- review versions
    |-- schema version metadata
    v
SingleProcessTaskRunner
    v
TaskExecutor
    |-- deterministic DemoTaskExecutor
    `-- RealTaskExecutor
          |-- bounded LangGraph workflow
          |-- literature providers
          |-- structured LLM provider
          `-- retry, repair, budget, telemetry

Controlled plugin runtime
    |-- built-ins loaded deterministically
    `-- external entry points require exact command-local authorization
```

## Principal boundaries

| Boundary | Current decision | Reason |
|---|---|---|
| Deployment | Local single user / trusted network | No authentication, tenancy, public quotas, or hostile-plugin sandbox |
| Queue | Single-process durable polling runner | Keeps task semantics inspectable while retaining crash detection and persisted state |
| Database | SQLite with WAL and explicit transactions | Sufficient for the MVP; easy to reproduce; supports transactional idempotency and task claims |
| Workflow | Bounded LangGraph graph | Explicit node order, retry boundaries, cancellation probes, and typed state |
| LLM | Provider protocol with structured schemas | Separates workflow logic from vendor transport and validates every persisted output |
| Plugins | Explicitly authorized Python entry points | Prevents automatic code loading; authorization is documented as distinct from sandboxing |
| Observability | Durable events, readiness, JSON diagnostics, Prometheus text | Provides correlation and operational evidence without persisting prompts or credentials |

## Durable task invariants

1. One idempotency key is bound to one canonical request hash.
2. Reusing the key with the same request returns the original task.
3. Reusing the key with a different request returns a conflict.
4. A queued task can be claimed once because selection and state transition occur in one immediate transaction.
5. Every lifecycle transition appends a monotonically increasing task event.
6. Running tasks are failed closed after process restart instead of replaying potentially billable provider calls.
7. Cancellation is cooperative at workflow boundaries; already-issued provider calls may still be billable.
8. Review updates use optimistic versions to reject stale writes.

## Scaling path

The MVP should move to PostgreSQL and a distributed queue when any of these become requirements:

- multiple application replicas;
- horizontal workers;
- high write concurrency;
- tenant isolation;
- distributed leases and retries;
- strict service-level objectives;
- centralized tracing and metrics retention.

The task, event, idempotency, and executor protocols are deliberately separated so that the durable contract can survive that migration.

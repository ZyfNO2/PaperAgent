# Request Lifecycle

## 1. Submission

The client sends `POST /v1/tasks` with an `Idempotency-Key`. The API canonicalizes the validated request, hashes it, and enters an immediate SQLite transaction.

```text
no existing key -> insert queued task + task.queued event
same key/hash    -> return original task with reused=true
different hash   -> HTTP 409
```

The API returns `202 Accepted`; execution is asynchronous.

## 2. Claim

`SingleProcessTaskRunner` polls or receives an in-process notification. `claim_next_task()` selects the oldest queued task and changes it to `running` within the same immediate transaction. A `task.started` event is appended before the claim is returned.

The compare-and-update condition prevents a second claimant from taking the same task.

## 3. Execution

The executor receives only:

- immutable research request;
- task identifier;
- event emitter;
- cancellation probe.

The real executor invokes a bounded graph. Provider calls are subject to call, token, time, and optional monetary budgets. Structured responses are validated before they enter graph state. A single repair call is permitted only for malformed structured output.

## 4. Progress

Workflow and provider milestones are appended to `task_events`. Consumers can read them with cursor pagination or Server-Sent Events.

SSE uses the persisted event sequence as the event identifier. A reconnecting client can resume from its last cursor without requiring an in-memory subscription registry.

## 5. Cancellation

- Queued task: transitions directly to `cancelled`.
- Running task: transitions to `cancel_requested`.
- Executor: checks cancellation at bounded workflow boundaries.
- Completion after accepted cancellation: runner records `cancelled` rather than success.

Cancellation cannot guarantee that an already-issued remote request is free of cost.

## 6. Terminal persistence

The runner stores one terminal state:

- `succeeded` with result JSON;
- `failed` with typed error JSON;
- `cancelled` without result.

The terminal transition and terminal event are written transactionally.

## 7. Review and export

Successful evidence results are projected into durable paper cards. Review writes use an expected version. A stale reviewer receives a conflict rather than silently overwriting a newer decision.

Exports are deterministic for the selected review set and return:

- content type;
- stable filename;
- item count;
- SHA-256 digest.

## 8. Process restart

At runner startup, tasks left in `running` or `cancel_requested` are marked failed with `PROCESS_RESTARTED`.

The system intentionally does not replay them because the previous process may already have issued provider calls. Automatic replay could duplicate side effects or billing without a durable provider idempotency guarantee.

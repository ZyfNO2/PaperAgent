# Interview Demo Runbook

## One-command demo

From the repository root after installing development dependencies:

```bash
python scripts/interview_demo.py --output interview-demo-summary.json
```

The script runs entirely against a temporary SQLite database and the deterministic demo executor. It does not require external credentials or network access.

## Demonstrated contracts

1. Submit a task with an idempotency key.
2. Submit the same request and key again; verify task reuse.
3. Submit a different request with the same key; verify HTTP 409.
4. Wait for asynchronous execution to reach a terminal state.
5. Read persisted task events.
6. List review cards.
7. Accept one verified card with optimistic review versioning.
8. Export accepted evidence and verify digest headers.
9. Run the deterministic academic-method audit.
10. Read runtime diagnostics, schema version, and Prometheus metrics.

## Expected summary fields

```json
{
  "idempotency_reused": true,
  "idempotency_conflict_rejected": true,
  "task_terminal": "succeeded",
  "review_created": true,
  "export_created": true,
  "export_item_count": 1,
  "plugin_verdict": "GO",
  "schema_version": 1,
  "metrics_exposed": true
}
```

## Five-minute presentation sequence

- **00:00–00:30**: explain the bounded research-agent goal and deployment boundary.
- **00:30–01:30**: run the script and point to idempotency and asynchronous task state.
- **01:30–02:15**: show durable events and explain SSE reconnect by cursor.
- **02:15–03:00**: show review/export and optimistic versioning.
- **03:00–03:45**: show diagnostics and metrics; explain what is intentionally not logged.
- **03:45–04:30**: show plugin verdict and explicit plugin authorization boundary.
- **04:30–05:00**: state current limits and the PostgreSQL/distributed-worker migration triggers.

## Honest boundary

This demo validates backend contracts. It does not prove live model quality, scientific correctness, public multi-tenant security, or external plugin isolation.

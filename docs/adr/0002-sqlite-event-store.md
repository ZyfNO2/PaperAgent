# ADR 0002: Use SQLite as Task State and Event Store

- Status: Accepted
- Context: local single-user MVP

## Decision

Store task records, task events, review state, and schema metadata in one SQLite database using foreign keys, busy timeout, WAL mode, and explicit immediate transactions for write coordination.

## Rationale

- zero external service dependency;
- reproducible local and CI behavior;
- transactional idempotency-key binding;
- transactional claim and lifecycle-event persistence;
- cursor-based event replay survives browser and process reconnects.

## Consequences

- writes are serialized and performance is bounded by one database file;
- schema changes require explicit version checks and migrations;
- network filesystems and multi-host writers are outside the support boundary;
- operational diagnostics must avoid exposing request content.

## Rejected alternatives

- In-memory state: loses crash evidence and idempotency.
- Redis only: insufficient as the sole durable review/export store.
- PostgreSQL immediately: operational cost exceeds the current single-user requirement.

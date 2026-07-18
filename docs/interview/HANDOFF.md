# PaperAgent Interview Hardening Handoff

## Delivery state

```text
Branch:             feat/interview-hardening
Stack base:         feat/v0.6-v0.8-mvp-plugins / PR #14
Follow-up PR:       #16
Package version:    unchanged at 0.5.1
Merge performed:    no
Release performed:  no
```

PR #16 is intentionally stacked on PR #14. Merge or retarget it only after the v0.6-v0.8 integration
base has landed.

## Delivered work

### Runtime operations

- `paperagent diagnostics --database ...`
- `GET /v1/diagnostics/runtime`
- `GET /metrics`
- schema compatibility in `/readyz`
- low-cardinality task, event, database, and schema information
- no task request bodies, idempotency values, prompts, model responses, or provider configuration

### SQLite schema metadata

- `PRAGMA user_version` compatibility gate
- durable `schema_migrations` records
- rejection of missing, uninitialized, task-only, and unknown-future schemas
- diagnostics never creates a missing database as a side effect
- readiness disk work runs outside the event loop

### Concurrency evidence

- concurrent identical submissions create one durable task
- concurrent claims return every task at most once
- reproducible 500-task benchmark and interpretation boundary

### Interview demonstration

`python scripts/interview_demo.py --output interview-demo-summary.json` demonstrates:

- asynchronous submission
- idempotency reuse and conflict rejection
- durable lifecycle events
- successful terminal persistence
- optimistic Review update
- deterministic export with digest metadata
- v0.8 method-plugin verdict
- schema version reporting
- metrics availability

### Package and extension evidence

- OpenAPI compatibility manifest and export utility
- independent `paperagent.plugins` package example
- external plugin remains unloaded by default
- exact command-local authorization is required
- CI builds the main Wheel, installs it in a fresh environment, installs the plugin, and invokes it
  through the installed CLI

### Architecture and interview material

- architecture overview, request lifecycle, and failure model
- five ADRs
- 30-second, two-minute, and five-minute project pitch
- backend and Agent Q&A
- incident cases and demo runbook
- benchmark methodology and measured CI run
- STRIDE-oriented threat model

## Primary commands

```bash
python -m pip install -e '.[dev,release]'
python scripts/interview_demo.py --output build/interview-demo-summary.json
python scripts/export_openapi.py --output build/openapi.json
python scripts/repository_benchmark.py --tasks 500 --output build/repository-benchmark.json
paperagent diagnostics --database paperagent.db
paperagent serve
```

External plugin example:

```bash
python -m pip install --no-deps ./examples/external_plugin
paperagent plugins inspect interview-summary \
  --enable-external-plugin interview-summary
paperagent plugins run interview-summary \
  --enable-external-plugin interview-summary \
  --operation summarize \
  --input examples/external_plugin/input.json \
  --output build/interview-summary-plugin.json
```

## Cloud evidence

Verified functional run before documentation-only closeout commits:

```text
Workflow:       PaperAgent Interview Evidence
Run:            29623311677 — SUCCESS
Head SHA:       62e649ff84da77e5c2546ce914c759565819c864
Python 3.11:    Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Python 3.12:    Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Wheel smoke:    SUCCESS
External plugin installed smoke: SUCCESS
Interview demo: SUCCESS
OpenAPI export: SUCCESS
500-task benchmark: SUCCESS
Artifact ID:    8422947228
```

The final PR head must pass the same workflow after this Handoff and the code-review record are
committed. Use the latest PR check as the merge-time source of truth.

## Interview preparation order

1. Practice `PROJECT_PITCH.md`, especially the two-minute version.
2. Run the demo and explain every output field.
3. Answer `BACKEND_QA.md` without reading the prepared answer.
4. Use `AGENT_QA.md` to distinguish workflow control from model behavior.
5. Use `INCIDENT_CASES.md` to practice failure-first explanations.
6. Use the ADRs when asked why a technology or boundary was chosen.
7. State the current scaling limit before proposing PostgreSQL or distributed workers.

## Remaining boundaries

This PR does not add or claim:

- public authentication or tenant isolation
- distributed workers or exactly-once remote execution
- external-plugin process isolation
- production metrics retention or dashboards
- live Mistral scientific-quality evidence
- external holdout or human blind review
- a production throughput service-level objective

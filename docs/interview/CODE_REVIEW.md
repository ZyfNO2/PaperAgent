# PR #16 Interview Hardening Code Review

## Review state

```text
Scope:             PR #16 / feat/interview-hardening
Base:              feat/v0.6-v0.8-mvp-plugins at 500c4cf737eca6a37af9aaa80264eac1be86042d
Disposition:       PASS WITH STACK AND DEPLOYMENT CONDITIONS
Open code blocker: 0
Merge performed:   no
```

This review covers only the follow-up interview-hardening delta. The v0.6-v0.8 runtime remains reviewed
in PR #14.

## Reviewed surfaces

- runtime diagnostics and Prometheus text rendering
- schema version metadata and startup/readiness behavior
- CLI diagnostics behavior
- concurrency tests and benchmark methodology
- deterministic interview demo
- OpenAPI compatibility manifest
- independently packaged external plugin example
- installed-Wheel evidence workflow
- architecture, ADR, interview, benchmark, and threat-model documentation

## Findings fixed during review

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | Running diagnostics against a nonexistent path could create an empty SQLite file and then mark it as migrated. | Diagnostics now rejects nonexistent files and never creates them as a read-side effect. |
| HIGH | The version gate checked only task tables while the migration record claimed the task and Review schema. | `tasks`, `task_events`, and `paper_reviews` are all required before version metadata is applied. A task-only database is rejected. |
| MEDIUM | Schema readiness performed a synchronous SQLite check in the async request handler. | The check now runs through `asyncio.to_thread`. |
| MEDIUM | CLI diagnostics exposed raw exception tracebacks for expected operator errors. | Known filesystem, SQLite, and schema errors are converted into a concise `SystemExit` message. |
| MEDIUM | The external plugin README used a `--payload-json` flag that the CLI does not implement. | The example now uses the real `--input` and `--output` file contract. |
| MEDIUM | The plugin example was initially validated only from source. | CI now builds the main Wheel, installs it in a fresh environment, installs the external plugin package, and invokes the installed CLI. |
| LOW | A benchmark could be presented without its environment and product boundary. | The script emits an explicit single-process boundary and the measured GitHub Actions run is documented with p50, p95, maximum, runner, SHA, and artifact identity. |

## Contract checks

### Diagnostics

- no task request body or idempotency value is returned
- status and event labels are bounded by application enums and event types
- missing and partial databases fail explicitly
- future schema versions fail closed
- `/metrics` emits stable Prometheus text

### Concurrency

- identical concurrent submissions create one durable task
- only one submission is reported as newly created
- concurrent claim operations never return a task twice
- the result is not represented as a distributed-worker guarantee

### Interview demo

- credential-free and network-free
- temporary database by default
- proves idempotency reuse and mismatch rejection
- proves asynchronous execution and durable events
- proves Review and export paths
- proves diagnostics, metrics, schema metadata, and built-in plugin behavior

### External plugin

- separate Python distribution
- declared through the `paperagent.plugins` entry-point group
- not loaded without exact authorization
- installed-Wheel invocation covered in CI
- still documented as trusted in-process code rather than isolated code

## Verified evidence

Functional verification before documentation-only closeout commits:

```text
Workflow run:       29623311677 — SUCCESS
Verified code SHA:  62e649ff84da77e5c2546ce914c759565819c864
Python 3.11:        lint, format, strict Mypy, tests, coverage — SUCCESS
Python 3.12:        lint, format, strict Mypy, tests, coverage — SUCCESS
Main Wheel:         built and installed in a fresh environment
External plugin:    installed and invoked through installed CLI
Interview artifacts generated successfully
```

The latest PR head must pass the same workflow before merge.

## Residual conditions

- PR #16 is stacked and must not merge before PR #14 or equivalent base content.
- Diagnostics and metrics are suitable only for the current local/trusted-network boundary.
- Metrics have no server-side retention, dashboards, or alerting.
- Schema version 1 adds metadata and compatibility checks; future structural changes still require an
  explicit migration implementation and rehearsal.
- The benchmark is a regression baseline, not a public capacity claim.
- External plugins remain in-process trusted code.
- Live LLM and scientific-quality gates remain owned by the v0.6 release-evidence plan.

## Decision

```text
Engineering interview evidence: READY
Code review:                   PASS
Deployment boundary:          unchanged
Release status:                not a release
Merge order:                   PR #14 first, then PR #16
```

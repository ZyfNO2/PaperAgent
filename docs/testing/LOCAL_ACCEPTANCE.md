# PaperAgent Local Acceptance

## Purpose

This is the authoritative offline test plan for consolidated PR #17. It is designed for a developer laptop or an isolated CI runner and does not require network access, a model provider key, or a literature-provider credential.

Local acceptance answers three separate questions:

1. Does the source tree satisfy static and unit/integration gates?
2. Can durable local state survive a consistent SQLite backup and restore?
3. Does a clean installed Wheel expose the expected CLI and built-in plugin surface?

It does not establish live-model quality, real-paper reproducibility, scientific novelty, multi-tenant security, or production capacity.

## Prerequisites

- Python 3.11 or 3.12;
- repository checkout at the exact PR head under review;
- development and release dependencies installed:

```bash
python -m pip install -e '.[dev,release]'
```

On Windows PowerShell use the same Python commands. The full profile creates its own temporary virtual environment under `build/local-acceptance/venv` and selects `Scripts` or `bin` automatically.

## One-command profiles

### Quick local gate

```bash
python scripts/local_acceptance.py \
  --profile quick \
  --output build/local-acceptance/summary.json
```

The quick profile runs:

- bytecode compilation;
- Ruff lint and format check;
- strict Mypy;
- targeted local, consolidated-review, diagnostics, and release-path tests;
- SQLite state backup/restore/restart roundtrip;
- deterministic interview demo;
- OpenAPI export;
- 100-task local SQLite benchmark;
- academic-tailoring corpus evaluation.

### Full local gate

```bash
python scripts/local_acceptance.py \
  --profile full \
  --output build/local-acceptance/summary.json
```

The full profile additionally runs:

- the complete Pytest suite with branch coverage;
- the 500-task benchmark;
- Wheel build;
- clean virtual-environment installation;
- installed `paperagent --help` and `paperagent plugins list` smoke.

The runner stops on the first failure unless `--continue-on-error` is supplied. Every command writes a log under `build/local-acceptance/logs/`. The summary records the Python version, platform, command, duration, result, artifact path, and SHA-256 digest.

To inspect the exact plan without executing it:

```bash
python scripts/local_acceptance.py --profile full --print-plan
```

## Durable-state roundtrip

The following command exercises the local state boundary directly:

```bash
python scripts/local_state_roundtrip.py \
  --workdir build/local-state-roundtrip \
  --output build/local-state-roundtrip/summary.json
```

It performs this sequence:

1. creates a new SQLite-backed demo application;
2. submits and completes a deterministic task;
3. accepts and favorites a verified paper;
4. exports all papers and validates the export digest;
5. creates a consistent SQLite backup with the SQLite backup API;
6. restores the backup into a separate database;
7. verifies that the task, review state, paper cards, diagnostics, and export digest survive restore;
8. creates and claims a new task so that it is durably `running`;
9. starts a new application instance on the same database;
10. verifies fail-closed recovery to `failed` with `PROCESS_RESTARTED` and a terminal `task.failed` event.

Acceptance requires:

- backup SHA-256 is present;
- restored review is still accepted and favorite;
- live and restored export SHA-256 values match;
- restored database reports WAL mode;
- in-flight task is never replayed and ends with `PROCESS_RESTARTED`.

## Local test matrix

| Area | Automated locally | Main evidence |
|---|---:|---|
| Source compilation | Yes | `local_acceptance.py` compile step |
| Ruff lint/format | Yes | quick/full profiles |
| Strict Mypy | Yes | quick/full profiles |
| Unit and integration tests | Yes | targeted quick or complete full Pytest |
| Branch coverage | Full profile | Pytest coverage report |
| Task API, review, export | Yes | release tests and state roundtrip |
| SQLite schema and diagnostics | Yes | diagnostics tests |
| Backup and restore | Yes | `local_state_roundtrip.py` |
| Review/export persistence after restore | Yes | state roundtrip |
| Restart fail-closed behavior | Yes | state roundtrip |
| Concurrency | Yes | repository concurrency tests |
| OpenAPI stability | Yes | contract test and export step |
| Academic method/tailoring | Yes | plugin tests and corpus evaluation |
| Deterministic demo | Yes | interview demo step |
| Local benchmark | Yes | 100 or 500 tasks |
| Wheel build | Full profile | build step |
| Clean Wheel install and CLI | Full profile | installed-Wheel smoke |
| Browser UI | CI/manual | Release Hardening Chromium job |
| Docker | CI/manual | Release Hardening Docker job |
| Live literature providers | No, external | opt-in provider smoke |
| Live Mistral | No, external | credentialed workflow |
| Real scientific validity | No, external | frozen holdout and human review |

## Manual local checks

These remain manual because they require an actual socket, browser, or container runtime:

```bash
paperagent serve --database build/manual/paperagent.db --port 8765
```

Then verify:

- `http://127.0.0.1:8765/readyz` returns ready;
- `http://127.0.0.1:8765/v1/diagnostics/runtime` contains no prompt, key, request body, or idempotency value;
- `http://127.0.0.1:8765/metrics` contains bounded labels;
- the browser can submit, observe progress, review a paper, and export;
- restarting the process preserves terminal tasks;
- non-loopback binding is rejected without `--allow-public-bind`.

A Docker-capable machine should also build and run the image with a persistent `/data` volume and confirm `/readyz` after restart.

## Failure interpretation

- A quick-profile failure blocks local development handoff.
- A full-profile failure blocks merge acceptance.
- A browser or Docker failure blocks engineering release acceptance, but not necessarily source-level review.
- Missing live-provider or scientific evidence must remain `INCOMPLETE`; it cannot be converted to pass by local fixtures.
- The committed synthetic academic corpus evaluates deterministic contract handling, not global novelty or empirical effectiveness.

## Cleanup

All generated files are under `build/local-acceptance/` or the explicitly supplied state-roundtrip work directory. They may be deleted after artifact digests have been recorded.

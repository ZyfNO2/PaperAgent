# PaperAgent PR #17 Consolidated Handoff

## Authority

This file supersedes the earlier stacked-PR handoff text for PRs #14 and #16. The only integration surface is PR #17.

```text
Repository:       ZyfNO2/PaperAgent
Pull request:     #17
Base branch:      master
Feature branch:   feat/academic-tailoring-evaluation
Merge state:      NOT MERGED
Release state:    NOT RELEASED
Package metadata: 0.5.1
Deployment scope: local single user / trusted network
```

Always use the current PR head and current checks as the source of truth. Historical SHAs and run IDs from the former stacked PRs are evidence history only.

## Delivered scope

PR #17 consolidates:

- the real-LLM engineering MVP and typed provider runtime;
- durable task, event, cancellation, review, export, readiness, diagnostics, and metrics contracts;
- the controlled local plugin runtime and external-entry-point authorization boundary;
- deterministic academic method audit and proposal generation;
- synthetic academic-tailoring Agent evaluation;
- concurrency, OpenAPI, Wheel, browser, Docker, benchmark, architecture, security, and interview evidence.

The deterministic proposal path now reports `evidence_scope`, `readiness`, `scientific_release_ready`, and explicit release conditions. A synthetic `GO` is not scientific release evidence.

## Local acceptance status

The earlier handoffs did not contain a complete PR #17 local test plan. PR #17 now includes an authoritative plan and executable local harness:

- `docs/testing/LOCAL_ACCEPTANCE.md`;
- `scripts/local_acceptance.py`;
- `scripts/local_state_roundtrip.py`;
- `tests/local/test_local_acceptance_plan.py`;
- `tests/local/test_local_state_roundtrip.py`.

### Closed local-test gaps

| Previous gap | Current implementation |
|---|---|
| No single local command covering the consolidated PR | quick and full profiles in `local_acceptance.py` |
| No machine-readable local acceptance record | JSON summary, per-step logs, artifact SHA-256 values |
| No consistent SQLite backup/restore integration test | SQLite backup API roundtrip |
| No validation that reviews survive restore | restored paper decision/favorite assertion |
| No validation that exports remain deterministic after restore | live/restored export digest equality |
| Restart recovery tested only at repository level | application startup roundtrip with `PROCESS_RESTARTED` assertion |
| Installed Wheel tests existed only as CI shell steps | full local profile builds, installs, and smokes the Wheel |
| Local plan could accidentally include credentialed work | plan regression test rejects provider smoke and secret requirements |

### Quick gate

```bash
python -m pip install -e '.[dev,release]'
python scripts/local_acceptance.py \
  --profile quick \
  --output build/local-acceptance/summary.json
```

### Full merge gate

```bash
python scripts/local_acceptance.py \
  --profile full \
  --output build/local-acceptance/summary.json
```

The full profile is the local equivalent of the source, test, coverage, benchmark, build, and installed-Wheel portions of CI. Browser and Docker verification remain separate because they require those runtimes.

### Direct durable-state gate

```bash
python scripts/local_state_roundtrip.py \
  --workdir build/local-state-roundtrip \
  --output build/local-state-roundtrip/summary.json
```

Expected terminal facts:

```text
status:                  passed
review_restored:         true
export digests equal:    true
journal_mode:            wal
restart_recovery_code:   PROCESS_RESTARTED
```

## Automated test inventory

### Core API and persistence

- idempotent task creation and conflict rejection;
- queued/running/terminal state transitions;
- persisted event ordering and SSE cursor behavior;
- queued and running cancellation;
- fail-closed process restart recovery;
- result-size and typed failure boundaries;
- review optimistic concurrency;
- deterministic JSON, Markdown, and BibTeX export;
- concurrent idempotent submission and exactly-once local claim behavior.

### Database and operations

- schema initialization and idempotent metadata migration;
- rejection of missing, empty, task-only, and future-version databases;
- observed SQLite journal mode;
- secret-free diagnostics and Prometheus text metrics;
- consistent backup and restored-state verification;
- 100-task quick and 500-task full local benchmark profiles.

### Provider and Agent contracts

- typed provider errors, retry/repair, timeout, token/cost budget, and redaction;
- deterministic plugin contracts, authorization, no-overwrite output, and external plugin package smoke;
- academic provenance, license, reproduction, semantic compatibility, fairness, ablation, novelty, and result-evidence gates;
- synthetic corpus snapshots and grader regressions;
- distinction between synthetic evaluation and scientific release readiness.

### Packaging and UI

- source-tree CLI and plugin smoke;
- Wheel build and clean installed-Wheel smoke in the full local profile;
- packaged web assets, Chromium vertical flow, and Docker readiness in Release Hardening CI.

## Required takeover sequence

1. Fetch PR #17 and record `git rev-parse HEAD`.
2. Install `.[dev,release]` in Python 3.11 or 3.12.
3. Run the quick local profile while iterating.
4. Run the full local profile before merge approval.
5. Inspect `build/local-acceptance/summary.json` and all failing logs.
6. Confirm the PR checks pass on the same head.
7. Record run IDs and primary artifact digests in the PR body or final review comment.
8. Do not merge if the PR head changes after the final verified run.

## Acceptance levels

```text
Merge acceptance:                 requires full local/CI engineering gates
Engineering release acceptance:   additionally requires merged-SHA package, browser,
                                  container, backup/restore/rollback operations, and release notes
Scientific capability acceptance: additionally requires live model, real sources,
                                  baseline reproduction, frozen holdout, statistics, and blind review
```

Local deterministic tests can satisfy merge acceptance. They cannot satisfy the live-provider or scientific capability levels.

## External and still-incomplete evidence

The following are intentionally outside the offline local harness:

- live Mistral validation for all production schemas;
- three consecutive frozen-input real-provider vertical runs;
- provider-specific 429, timeout, thinking-only, latency, token, and cost distributions;
- real-paper baseline reproduction;
- external scientific holdout;
- statistical experiment results;
- blinded domain-expert review and agreement measurement;
- authentication, tenant isolation, distributed workers, hostile-plugin sandboxing, and production SLOs.

## Merge rule

PR #17 is merge-ready only when:

- the quick and full local plans are structurally intact;
- new local roundtrip tests pass on Python 3.11 and 3.12;
- the final PR head is mergeable;
- all required GitHub workflows are green on that head;
- no P0/P1 review finding remains;
- the PR body records the exact final head, workflow runs, and artifact digests.

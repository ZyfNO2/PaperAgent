# PaperAgent PR #17 Consolidated Handoff

> **SUPERSEDED BY PR #25 (merged)**
>
> This document is retained for historical review and diagnostic evidence only.
> The accepted implementation is now on `master` at `4f81e19a`.
> Current authority: `docs/interview/HANDOFF.md`.

## Authority

This file supersedes the earlier stacked-PR handoff text for PRs #14 and #16. The only integration surface is PR #17.

```text
Repository:       ZyfNO2/PaperAgent
Pull request:     #17
Review base:      integration/pre-rewrite-v0.5.1-base
Pinned base SHA:  497982242023e3b621fa8b31816a6f2b8d899d4a
Feature branch:   feat/academic-tailoring-evaluation
Merge state:      NOT MERGED
Release state:    NOT RELEASED
Package metadata: 0.5.1
Deployment scope: local single user / trusted network
```

The repository `master` history was rewritten after the original consolidation review. PR #17 is therefore pinned to the pre-rewrite base so that its intended diff remains reviewable. Do not merge this branch directly into the rewritten `master`; first perform a separate clean-tree migration and reconciliation.

Always use the current PR head and current checks as the source of truth. Historical SHAs and run IDs from the former stacked PRs are evidence history only.

## Delivered scope

PR #17 consolidates:

- the real-LLM engineering MVP and typed provider runtime;
- durable task, event, cancellation, review, export, readiness, diagnostics, and metrics contracts;
- the controlled local plugin runtime and external-entry-point authorization boundary;
- deterministic academic method audit and proposal generation;
- synthetic academic-tailoring Agent evaluation;
- concurrency, OpenAPI, Wheel, browser, Docker, benchmark, architecture, security, and interview evidence.

The deterministic proposal path reports `evidence_scope`, `readiness`, `scientific_release_ready`, and explicit release conditions. A synthetic `GO` is not scientific release evidence.

## Local acceptance status

The earlier handoffs did not contain a complete PR #17 local test plan. PR #17 now includes an authoritative plan and executable local harness:

- `docs/testing/LOCAL_ACCEPTANCE.md`;
- `scripts/local_acceptance.py`;
- `scripts/local_state_roundtrip.py`;
- `tests/local/test_local_acceptance_plan.py`;
- `tests/local/test_local_state_roundtrip.py`;
- `.github/workflows/local-acceptance.yml`;
- `acceptance/local-pr17/latest.json`.

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
| PR merge-ref testing could be polluted by rewritten `master` | dedicated branch-push Local Acceptance workflow |

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

## Verified local evidence

### Branch one-command acceptance

```text
Source SHA:       591ff5d8354d69b6606820263e1eed9fc7403787
Workflow:         PaperAgent Local Acceptance
Run ID:           29630172738
Run number:       18
Python matrix:    3.11 and 3.12 — SUCCESS
Quick profile:    SUCCESS
Network required: false
Live LLM required:false
```

The persisted record is `acceptance/local-pr17/latest.json`. The quick profile passed compilation, Ruff lint/format, strict Mypy, targeted Pytest, durable-state roundtrip, interview demo, OpenAPI export, 100-task SQLite benchmark, and academic-tailoring evaluation.

### Final code-head verification

```text
Code HEAD:        37572aba81070fe0b4df5df5f3708a94cf825368
Interview run:    29630259329 — SUCCESS
Academic run:     29630259297 — SUCCESS
Python 3.11:      Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Python 3.12:      Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Installed Wheel:  SUCCESS
External plugin:  SUCCESS
State roundtrip:  SUCCESS
Demo/OpenAPI/500-task benchmark: SUCCESS
```

Primary final-head artifact:

```text
Artifact name:    paperagent-interview-evidence
Artifact ID:      8425220815
SHA-256:          a8e9d60be337ef4e6ddcede1cea3b3bc2e5cb4b97e9a526cce87b0813125ee79
```

The final-head state-roundtrip artifact recorded:

```text
status:                    passed
review_restored:           true
journal_mode:              wal
restart_recovery_code:     PROCESS_RESTARTED
backup_sha256:             fa01fca97af37f3d13a8a66b149d4df3a4bc3cf22bffa016e44cfd882b548470
export_sha256:             2f9e0c62e2540558a59a50ef586fe07a40846742d064f45d66916e8351ea4915
restored_export_sha256:    2f9e0c62e2540558a59a50ef586fe07a40846742d064f45d66916e8351ea4915
```

The matching export digests prove that application-level review/export state survived the consistent SQLite backup and restore. The restart assertion proves that in-flight work is failed closed rather than replayed.

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
- review and export persistence after restore;
- application-startup recovery of in-flight tasks;
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
2. Confirm the PR remains based on `integration/pre-rewrite-v0.5.1-base` while reconciliation is pending.
3. Install `.[dev,release]` in Python 3.11 or 3.12.
4. Run the quick local profile while iterating.
5. Run the full local profile before merge approval.
6. Inspect `build/local-acceptance/summary.json` and all failing logs.
7. Confirm the PR checks pass on the same code head.
8. Record run IDs and primary artifact digests in the PR body or final review comment.
9. Do not merge into rewritten `master` until clean-tree reconciliation is complete.

## Acceptance levels

```text
Local test implementation:         COMPLETE
Offline local acceptance:          PASS
Merge to pinned review base:        code/test gates pass
Merge to rewritten master:          BLOCKED pending clean-tree reconciliation
Engineering release acceptance:     requires merged-SHA package, browser,
                                    container, operational rollback, and release notes
Scientific capability acceptance:   requires live model, real sources,
                                    baseline reproduction, frozen holdout, statistics, and blind review
```

Local deterministic tests can satisfy offline engineering acceptance. They cannot satisfy live-provider or scientific capability acceptance.

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

PR #17 may be treated as locally tested only when:

- the quick and full local plans are structurally intact;
- new local roundtrip tests pass on Python 3.11 and 3.12;
- the current code head is mergeable against the pinned review base;
- all required GitHub workflows are green on that code head;
- no P0/P1 review finding remains;
- the PR body records the exact tested code head, workflow runs, and artifact digests.

A separate migration PR or clean-tree transplant is required before any merge into the rewritten `master`.

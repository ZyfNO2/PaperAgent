# PaperAgent Interview and Local Verification Handoff

## Current integration state

```text
Repository:        ZyfNO2/PaperAgent
Pull request:       #22
Head SHA:           2f459a35fd4e9762817f15b387769e5458a1cad6
Base branch:        fix/academic-tailoring-contract-convergence
Base SHA:           ba1f04bb10e576a1d815312cb76e49a42ab8ce99
Branch:             fix/academic-tailoring-review-hardening
Package version:    0.5.1
CI runs:            29689274176 / 29689274159
Merge performed:    no
Release performed:  no
Status:             engineering review passed, Draft, not merged
```

PR #22 is stacked on Draft PR #21 (`fix/academic-tailoring-contract-convergence`). It should remain Draft until the parent branch is reviewed and merged. Do not merge directly into `master`.

## Interview evidence already delivered

- durable asynchronous task API;
- idempotency, event cursor, SSE, cancellation, restart recovery, review, and export;
- SQLite schema metadata, diagnostics, metrics, concurrency, backup, and restore evidence;
- real-LLM runtime contracts, bounded retry/repair, budgets, pricing, and redaction;
- controlled plugin runtime and independent external-plugin package;
- deterministic academic method audit/proposal and Agent evaluation;
- OpenAPI export, deterministic demo, benchmark, browser, Docker, and Wheel evidence;
- architecture ADRs, failure model, threat model, pitch, backend Q&A, Agent Q&A, and incident cases.

## Local verification commands

Install once:

```bash
python -m pip install -e '.[dev,release]'
```

Fast interview rehearsal and regression gate:

```bash
python scripts/local_acceptance.py \
  --profile quick \
  --output build/local-acceptance/summary.json
```

Complete pre-merge local gate:

```bash
python scripts/local_acceptance.py \
  --profile full \
  --output build/local-acceptance/summary.json
```

Focused durability demonstration:

```bash
python scripts/local_state_roundtrip.py \
  --workdir build/local-state-roundtrip \
  --output build/local-state-roundtrip/summary.json
```

The focused demonstration proves that a completed task, review state, and deterministic export survive a consistent SQLite backup/restore, and that an in-flight task fails closed with `PROCESS_RESTARTED` after application restart.

Detailed procedure and expected evidence: `docs/testing/LOCAL_ACCEPTANCE.md`.

## Verified evidence for the new local tests

```text
One-command local run:  29630172738 — SUCCESS
Source SHA:             591ff5d8354d69b6606820263e1eed9fc7403787
Python matrix:          3.11 and 3.12 — SUCCESS
Quick profile:          SUCCESS

Final code-head run:    29630259329 — SUCCESS
Final tested code SHA:  37572aba81070fe0b4df5df5f3708a94cf825368
Academic run:           29630259297 — SUCCESS
Interview artifact ID:  8425220815
Artifact SHA-256:       a8e9d60be337ef4e6ddcede1cea3b3bc2e5cb4b97e9a526cce87b0813125ee79
```

Final-head durable-state evidence:

```text
status:                  passed
review_restored:         true
journal_mode:            wal
restart_recovery_code:   PROCESS_RESTARTED
backup_sha256:           fa01fca97af37f3d13a8a66b149d4df3a4bc3cf22bffa016e44cfd882b548470
export_sha256:           2f9e0c62e2540558a59a50ef586fe07a40846742d064f45d66916e8351ea4915
restored_export_sha256:  2f9e0c62e2540558a59a50ef586fe07a40846742d064f45d66916e8351ea4915
```

## Primary interview commands

```bash
python scripts/interview_demo.py --output build/interview-demo-summary.json
python scripts/export_openapi.py --output build/openapi.json
python scripts/repository_benchmark.py --tasks 500 --output build/repository-benchmark.json
python scripts/run_academic_tailoring_eval.py --output-dir build/academic-tailoring-eval
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

## What to explain in an interview

1. The system is a deterministic workflow around bounded LLM calls, not an autonomous unbounded agent.
2. SQLite plus a single-process runner is an explicit MVP boundary.
3. Startup fails in-flight tasks closed instead of replaying potentially billable provider calls.
4. Local backup uses the SQLite backup API, not a blind copy of a live WAL database.
5. Restored review and export digests demonstrate durable application-level state, not merely file existence.
6. External plugin authorization is not process isolation.
7. Synthetic academic `GO` means the contract passed deterministic gates; it does not prove novelty or empirical effectiveness.
8. Merge, engineering release, and scientific capability acceptance are separate decisions.

## Remaining boundaries

The handoff does not claim:

- authentication, accounts, tenant isolation, quotas, billing, or public deployment approval;
- distributed workers or exactly-once remote execution;
- hostile external-plugin isolation;
- live Mistral scientific-quality evidence;
- real-paper reproduction, external holdout, or blinded expert review;
- production throughput, availability, or cost SLOs.
- independent execution or verification of baseline training and reproduction experiments; PaperAgent only consumes and binds trusted server-owned execution metadata, and missing metadata results in REVISE or NO_GO.

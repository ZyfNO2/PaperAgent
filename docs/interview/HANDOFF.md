# PaperAgent Interview and Local Verification Handoff

## Current integration state

```text
Repository:        ZyfNO2/PaperAgent
Integration PR:    #17
Base:              master
Branch:            feat/academic-tailoring-evaluation
Package version:   0.5.1
Merge performed:   no
Release performed: no
```

PR #17 supersedes the former stacked PR #14 and PR #16 handoff model. Use `docs/v0.6-v0.8/HANDOFF.md` as the consolidated authority.

## Interview evidence already delivered

- durable asynchronous task API;
- idempotency, event cursor, SSE, cancellation, restart recovery, review, and export;
- SQLite schema metadata, diagnostics, metrics, and concurrency evidence;
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

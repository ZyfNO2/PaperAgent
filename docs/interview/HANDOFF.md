# PaperAgent Interview and Local Verification Handoff

## Current integration state

```text
Repository:                 ZyfNO2/PaperAgent
Master baseline:            4599053b6efda464aee1fe242db801427384a6c2
Historical integration PR:  #25 (merged)
Current development PR:     #28 (Draft)
Development branch:         feat/gold-case-rag-interview-readiness
Validated implementation:   f5b4b8ca5c063033a76131c727cd861333e2a6c6
Package version:             0.5.1
Merge performed:             no
Release performed:           no
Status:                      engineering readiness passed; scientific acceptance not claimed
```

PR #25 integrated the canonical academic-tailoring and backend-hardening implementation into
`master`. PR #28 adds a separate Gold Case, layered RAG/evidence evaluation, and evidence-bound
interview material. It does not modify or supersede formal Gate L PR #26.

## Gold Case and RAG readiness delivered

- one deterministic NPC/Game-AI Gold Case using the existing canonical proposal and audit contract;
- a source-to-decision chain from research contract through GO / REVISE / NO_GO;
- server-owned baseline, provenance, license, compatibility, and fingerprint fields;
- Recall@K and Precision@K;
- evidence precision and duplicate-source rate;
- citation support, unsupported claims, and critical unsupported claims;
- context utilization, LLM calls, tokens, estimated cost, terminal state, and blocker taxonomy;
- a generated interview evidence report bound to a stable SHA-256 digest;
- Chinese interview explanation and Japanese technical keywords;
- Python 3.11/3.12 focused validation plus full repository regression.

## Exact implementation evidence

```text
Validated implementation SHA:  f5b4b8ca5c063033a76131c727cd861333e2a6c6
Gold Case workflow run:         29691477087 — SUCCESS
Main repository CI run:         29691477085 — SUCCESS
Academic tailoring eval run:    29691477095 — SUCCESS
Interview evidence run:         29691477083 — SUCCESS
Release hardening run:          29691477117 — SUCCESS
Gold Case artifact ID:          8443722395
Gold Case artifact digest:      sha256:a8cd587f69666b86b21eac71c04fdc9d1f9d4b4a3ec8edc5a6624e0a99a2a812
Gold Case report digest:        7a959215fffbedfa8191fc30ce2c888e84ef28713211ef6441f98c37611a7b6e
```

The implementation run passed Ruff, Ruff format, strict Mypy, and focused tests on Python 3.11 and
3.12. The full repository regression, report generation, interview document generation, and artifact
upload also passed. The branch head containing this Handoff changes documentation and CI evidence
capture only; no product implementation changed after the validated implementation SHA above.

## Gold Case result

```text
case_id:                    npc-go-complete
status:                     passed
proposal_decision:          GO
audit_verdict:              GO
rubric_score:               100
minimum_score:              90
evidence_scope:             synthetic_evaluation
readiness:                  synthetic_evaluation_only
scientific_release_ready:   false
Recall@1:                   0.25
Recall@3:                   0.75
Recall@5:                   1.00
Precision@1/3/5:            1.00
citation_support_rate:      1.00
unsupported_claim_rate:     0.00
duplicate_source_rate:      0.00
context_utilization:        1.00
LLM calls/tokens/cost:      0 / 0 / $0.00
```

These values are deterministic engineering evidence from synthetic fixtures. They do not establish
real-provider retrieval quality, real-paper correctness, empirical improvement, novelty, or external
scientific acceptance.

## Interview evidence already delivered

- durable asynchronous task API;
- idempotency, event cursor, SSE, cancellation, restart recovery, review, and export;
- SQLite schema metadata, diagnostics, metrics, concurrency, backup, and restore evidence;
- real-LLM runtime contracts, bounded retry/repair, budgets, pricing, and redaction;
- controlled plugin runtime and independent external-plugin package;
- deterministic academic method audit/proposal and Agent evaluation;
- OpenAPI export, deterministic demo, benchmark, browser, Docker, and Wheel evidence;
- architecture ADRs, failure model, threat model, pitch, backend Q&A, Agent Q&A, and incident cases;
- Gold Case and layered RAG/evidence evaluation tied to the game-AI research plan.

## Primary interview commands

Install once:

```bash
python -m pip install -e '.[dev,release]'
```

Build the Gold Case and evidence-bound interview report:

```bash
python scripts/run_gold_case_readiness.py \
  --output build/gold-case/report.json
python scripts/build_interview_readiness.py \
  --input build/gold-case/report.json \
  --output build/gold-case/interview-readiness.md
```

Existing interview and repository demonstrations:

```bash
python scripts/interview_demo.py --output build/interview-demo-summary.json
python scripts/export_openapi.py --output build/openapi.json
python scripts/repository_benchmark.py --tasks 500 --output build/repository-benchmark.json
python scripts/run_academic_tailoring_eval.py --output-dir build/academic-tailoring-eval
paperagent diagnostics --database paperagent.db
paperagent serve
```

Fast local rehearsal and regression gate:

```bash
python scripts/local_acceptance.py \
  --profile quick \
  --output build/local-acceptance/summary.json
```

Complete local gate:

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

The durability demonstration proves that a completed task, review state, and deterministic export
survive a consistent SQLite backup/restore, and that an in-flight task fails closed with
`PROCESS_RESTARTED` after application restart.

## What to explain in an interview

1. The system is a bounded workflow around limited LLM calls, not an autonomous unbounded Agent.
2. The model proposes content, while provenance, baseline facts, fingerprints, and audit verdicts are
   server-owned contracts.
3. A plausible final paragraph is not retrieval evidence; retrieval, grounding, context use, cost,
   and terminal failures are evaluated separately.
4. The NPC Gold Case maps directly to the research plan: behavior cloning under distribution shift,
   invalid or unintended actions, action constraints, uncertainty-triggered residual correction, and
   evaluation of task success, invalid-action rate, adjustment cost, and latency.
5. SQLite plus a single-process runner is an explicit MVP boundary.
6. Startup fails in-flight tasks closed instead of replaying potentially billable provider calls.
7. External plugin authorization is not process isolation.
8. Synthetic academic `GO` means typed contracts passed deterministic gates; it does not prove
   novelty or empirical effectiveness.
9. Engineering integration, release readiness, formal Gate L, and scientific capability acceptance
   are separate decisions.

## Recommended answer to “What problem did you solve?”

Earlier execution paths could disagree about GO / REVISE / NO_GO or collapse every failure into a
single final-output judgment. The implementation converged proposal generation and methodology audit
onto one canonical contract, then added a Gold Case and layered RAG metrics. This makes it possible to
locate whether failure came from retrieval, citation grounding, baseline reproduction, module
compatibility, methodology audit, budget exhaustion, or the provider, instead of saying only that the
model produced a bad answer.

## Remaining boundaries

This handoff does not claim:

- authentication, accounts, tenant isolation, quotas, billing, or public deployment approval;
- distributed workers or exactly-once remote execution;
- hostile external-plugin isolation;
- formal Gate L scientific acceptance;
- live Mistral scientific-quality evidence;
- real-paper reproduction, external holdout, or blinded expert review;
- production throughput, availability, or cost SLOs;
- independent execution or verification of baseline training and reproduction experiments.

PaperAgent consumes and binds trusted server-owned execution metadata. Missing, unverified, or
incompatible critical evidence must produce REVISE or NO_GO rather than a fabricated GO decision.

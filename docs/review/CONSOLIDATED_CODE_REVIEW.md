# Consolidated Integration Code Review

## Review identity

```text
Repository:          ZyfNO2/PaperAgent
Pull request:        #17
Review date:         2026-07-18
Review scope:        former PRs #14 and #16 plus academic-tailoring evaluation
Stable review base:  integration/pre-rewrite-v0.5.1-base
Stable base SHA:     497982242023e3b621fa8b31816a6f2b8d899d4a
Final clean head:    pending clean-history rewrite and current-head CI
Disposition:         PENDING FINAL CURRENT-HEAD CI
Merge performed:     no
Release performed:   no
```

## Repository-history safety finding

During this review, `master` was force-rewritten from the lineage containing
`497982242023e3b621fa8b31816a6f2b8d899d4a` to a different lineage ending at
`8661084f2ef0210241c2143eca8db981222413a9`. A direct comparison then appeared to delete roughly
487,000 lines across more than 1,300 files.

Those deletions are not part of this PaperAgent change set. PR #17 is therefore reviewed against the
pinned branch `integration/pre-rewrite-v0.5.1-base`. Direct integration into the rewritten `master` is
blocked until the clean-tree reconciliation gate in the acceptance plan proves that no unrelated
repository content is removed.

## Consolidation result

- PR #17 is the only open integration PR for this work.
- PRs #14 and #16 were closed without merge and marked superseded.
- The intended consolidated diff is approximately 150 files rather than the destructive cross-history
  comparison.
- No merge, release tag, or package release was performed.

## Scope reviewed

- FastAPI asynchronous task contract, idempotency, durable events, SSE, cancellation, restart recovery,
  review, export, readiness, diagnostics, and metrics;
- SQLite transactions, WAL behavior, schema metadata, task claiming, and concurrency tests;
- LangGraph workflow boundaries and structured LLM calls;
- Mistral configuration, typed provider failures, bounded retry/repair, budgets, pricing, and redaction;
- plugin contracts, authorization, discovery, invocation, and atomic output;
- deterministic academic-method audit and academic-tailoring proposal generation;
- synthetic Agent evaluation corpus, grader, fixtures, and snapshots;
- wheel, CLI, browser, Docker, OpenAPI, benchmark, threat model, architecture, and interview evidence;
- release, deployment, and scientific-quality claims in code and documentation.

## Findings and corrective changes

| Severity | Finding | Corrective change |
|---|---|---|
| P0 safety | The rewritten `master` produced a destructive-looking cross-history diff. | Isolated review on the immutable pre-rewrite base and added a mandatory current-master reconciliation gate. |
| HIGH | Academic policy modules modified core functions and plugin classes through import-time monkey patching. | Moved all policy and `propose` behavior into core implementations; guard modules are compatibility-only re-exports. |
| HIGH | Synthetic fixtures could receive internal `GO` without a machine-readable scientific-release boundary. | Added `evidence_scope`, `readiness`, `scientific_release_ready=false`, and explicit release conditions. |
| HIGH | `verified=true` provenance could pass without a stable identifier or supported claim. | Baseline and module evidence now require verification, stable identifiers, and non-empty supported claims. |
| MEDIUM | Composition-only novelty checks were easy to bypass with wording variants. | Added normalized English/Chinese composition and mechanism signals; weak composition claims return `REVISE`. |
| MEDIUM | Duplicate identifiers, seeds, resources, metrics, and non-finite values were not fully rejected. | Added strict uniqueness, non-empty-contract, and finite-number validators. |
| MEDIUM | Experiment fairness compared too few fields. | Added data, preprocessing, tuning budget, metrics, seeds, uncertainty, resources, and stopping criteria to the fairness signature. |
| MEDIUM | Experiment arms could reference undeclared modules; trainable modules could omit loss terms. | Added declared-module checks and explicit loss requirements for trainable modules. |
| LOW | Runtime diagnostics inferred WAL from the database path. | Diagnostics now reports the observed `PRAGMA journal_mode`. |
| LOW | README and review material contained stale stacked-PR and evidence wording. | Consolidated documentation and separated engineering, synthetic-evaluation, and scientific-release claims. |

## Invariants after correction

1. Critical scientific, budget, provenance, and safety rules are deterministic code, not prompt prose.
2. Importing a compatibility module cannot change runtime behavior.
3. Internal `GO` means the supplied deterministic contract passed; it does not mean publication-ready
   science.
4. Synthetic, mixed/unverified, and real-verified evidence are separate machine-readable states.
5. Real-verified evidence permits controlled experimentation only; scientific release remains false
   until immutable observed evidence and expert review exist.
6. Every comparison arm has the same fairness signature except the intended intervention.
7. Unknown module references, contaminated baselines, unsupported observed results, incompatible
   licenses, and non-finite metrics fail closed.
8. Diagnostics and metrics exclude prompts, request bodies, credentials, and idempotency keys.
9. The old-history integration branch must not be merged directly into the rewritten `master`.

## Required final-head verification

```bash
python -m compileall -q src/paperagent
ruff check .
ruff format --check --diff .
mypy --config-file pyproject.toml
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
python -m build --wheel
python scripts/interview_demo.py --output build/interview-demo-summary.json
python scripts/export_openapi.py --output build/openapi.json
python scripts/repository_benchmark.py --tasks 500 --output build/repository-benchmark.json
python scripts/run_academic_tailoring_eval.py --output-dir build/academic-tailoring-eval
```

GitHub Actions must pass on Python 3.11 and 3.12. Installed-Wheel, external-plugin, browser, Docker,
OpenAPI, benchmark, and academic-evaluation checks must pass where configured. Only workflow runs
attached to the final clean-history head are valid acceptance evidence.

## Residual non-claims

The following block broader production or scientific claims:

- no authentication, tenant isolation, public abuse controls, distributed workers, or hostile-plugin
  sandbox;
- no completed live Mistral validation across every production schema and failure class;
- no three consecutive frozen-input real-provider vertical runs;
- no representative external scientific holdout;
- no real-paper reproduction package for the academic-tailoring path;
- no exhaustive prior-art search or proof of global novelty;
- no blinded domain-expert review or calibrated scientific acceptance threshold;
- no production throughput, availability, or cost SLO;
- no completed clean-tree migration into the force-rewritten `master` lineage.

## Decision model

- **Review-base acceptance:** final clean-head CI passes and no open P0/P1 code finding remains.
- **Current-master migration acceptance:** review-base acceptance plus the clean-tree reconciliation gate
  passes with zero unrelated deletion.
- **Engineering release acceptance:** migration acceptance plus installed artifact, migration, rollback,
  backup, and operational sign-off.
- **Scientific capability acceptance:** engineering release plus live providers, real sources,
  reproduction, frozen holdout, statistical evaluation, and blinded human review.

The authoritative execution procedure is `docs/acceptance/CONSOLIDATED_ACCEPTANCE_PLAN.md`.

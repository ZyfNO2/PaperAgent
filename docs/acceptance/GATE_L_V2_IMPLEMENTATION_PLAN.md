# Gate L v2 formal acceptance implementation plan

## Objective

Move Gate L from diagnostic remediation to a formally auditable scientific-capability acceptance path without weakening the existing quality gate or reusing holdout v1 as release evidence.

Scientific behavior cutoff candidate:

- branch: `scientific-gate-l`
- cutoff SHA: `d4fef014932d084a0addd4a588b3431d2c08628b`
- planning prompt: `planning.v0.1.2`
- holdout v1: diagnostic-only and permanently excluded from final Gate L acceptance

The implementation after this cutoff may add validation, freezing, execution, review-packaging, scoring, and CI infrastructure. Any later change to scientific prompts, routing semantics, retrieval policy, quality-gate rules, deterministic acceptance rules, or case-specific behavior invalidates the next frozen holdout and requires a new version.

## Non-negotiable integrity boundary

The developer implementing the harness must not author the final unseen holdout v2 cases or fill blinded expert scores. Those inputs must be supplied independently after the harness is complete.

The repository may contain:

- a case schema/template;
- validators;
- a freeze tool;
- an execution harness;
- blinded review-package generation;
- score aggregation and threshold evaluation.

It must not contain developer-authored final v2 case answers used for acceptance before freeze.

## Phase 1 — acceptance infrastructure

Implement a single Gate L v2 acceptance toolchain with these capabilities:

1. validate candidate v2 case files before freeze;
2. enforce exactly 16 cases and four cases per category: `in_domain`, `ood`, `insufficient_evidence`, `adversarial`;
3. validate required case metadata, expected terminal class, deterministic checks, reference provenance, human rubric fields, and strict per-case call/token/time/cost budgets;
4. freeze a validated case file into an immutable manifest with SHA-256 digest, scientific behavior cutoff SHA, prompt version, freeze timestamp, category counts, and acceptance thresholds;
5. reject a frozen manifest when the case digest changes;
6. generate a blinded reviewer package from real execution evidence while removing provider/model identity and expected labels from reviewer-visible artifacts;
7. aggregate two independent reviewer score files, compute per-case averages and terminal-decision agreement, calculate Cohen's kappa, record adjudication requirements, and evaluate hard Gate L thresholds;
8. fail closed when required evidence, telemetry, pricing, token accounting, review data, or adjudication is missing.

## Phase 2 — formal execution harness

Generalize the existing Gate L runner so formal v2 execution is parameterized by a frozen manifest rather than hard-coded to holdout v1.

Required behavior:

- load the case file only through its manifest;
- verify the case-file SHA-256 before execution;
- require manifest status `frozen_pending_execution` for formal runs;
- retain targeted `--case-id` execution for diagnostics, but mark targeted output as non-final;
- run all 16 cases for formal evidence;
- enforce each case's exact `max_calls`, `max_total_tokens`, `max_wall_seconds`, and `max_cost_usd`;
- never clamp reported cost to the budget limit;
- record repo SHA, provider, model, endpoint identity, price-table identity, prompt/config identity, case digest, execution timestamps, token/call/retry/repair/error telemetry, output digest, trace digest, terminal status, deterministic check inputs, and reference evidence;
- mark any unknown token/cost/trace field as a hard acceptance failure rather than silently passing.

## Phase 3 — CI and tests

Add offline tests for:

- valid v2 candidate structure;
- duplicate IDs;
- wrong category counts;
- missing or invalid budgets;
- invalid expected terminal class;
- missing deterministic checks/reference provenance/rubric fields;
- freeze digest correctness;
- digest tamper detection;
- scientific-cutoff identity recording;
- reviewer blinding;
- score aggregation;
- kappa calculation;
- mandatory adjudication on reviewer disagreement;
- zero-tolerance hard-failure precedence;
- final threshold pass/fail calculation;
- merge-conflict-marker regression protection.

CI must run Ruff, format, strict Mypy, and full Pytest/branch coverage through existing workflows.

## Phase 4 — human input checkpoint

After infrastructure is green, stop before creating final acceptance evidence and request the following external inputs:

1. independently authored unseen holdout v2 JSONL containing exactly 16 cases;
2. author/provenance attestation confirming the cases were not used during remediation;
3. explicit approval to freeze that exact candidate against the recorded scientific behavior cutoff;
4. after real-provider execution, two independent blinded reviewer score files;
5. adjudication decisions for every terminal-decision disagreement or critical-defect disagreement.

## Phase 5 — final Gate L decision

The final scorer must require all hard gates simultaneously, including at minimum:

- at least 14/16 accepted cases;
- at least 3/4 accepted in every category;
- zero false-GO events;
- zero critical safety events;
- zero fabricated identifiers;
- zero critical unsupported claims;
- non-critical unsupported-claim rate <= 5%;
- citation mismatch rate <= 5%;
- mean human score >= 80;
- no reviewer score below 70 on an accepted case;
- Cohen's kappa >= 0.70;
- at least 80% of cases with reviewer score delta <= 15;
- repair success rate >= 80% where repair is applicable;
- 100% fail-closed behavior for budget exhaustion;
- all required adjudications complete.

No average score may override a zero-tolerance failure.

## Deliverables

Implementation completion requires:

- Gate L v2 acceptance CLI/tooling;
- case and reviewer templates;
- formal execution manifest support;
- offline tests;
- CI green;
- updated Gate L handoff/status document;
- explicit `WAITING_FOR_HUMAN_INPUT` state identifying exactly what the user must provide next.

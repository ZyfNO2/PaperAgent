# PaperAgent v0.6 Development Status

## Current state

`OFFLINE MVP COMPLETE / LIVE MISTRAL AND SCIENTIFIC QUALITY NOT VERIFIED`

```text
Repository:               ZyfNO2/PaperAgent
Implementation branch:    feat/v0.6-v0.8-mvp-plugins
Draft PR:                 #14
Base:                     master at b01dbfa86de345b3d468240cc1b5a478c8cb0746
```

No Fake, Mock, Stub, static check, deterministic demo, or literature-provider smoke is represented as
real LLM end-to-end evidence.

## Phase status

| Phase | Status | Evidence boundary |
|---|---|---|
| A — provider contracts and policy | COMPLETE | configuration, errors, budgets, pricing, telemetry, redaction, and offline tests implemented |
| B — Mistral adapter | IMPLEMENTED / LIVE PENDING | adapter and failure-injection tests exist; four production-schema live tests require credentials |
| C — real runtime integration | OFFLINE COMPLETE / LIVE PENDING | explicit CLI selection, lifecycle, readiness, graph, persistence, cancellation, and budget integration are implemented |
| D — evaluation harness | DEVELOPMENT CORPUS COMPLETE / HOLDOUT PENDING | deterministic loader, graders, reports, manifest, and balanced 48-case corpus are committed; external observations and human review remain pending |
| E — release hardening | FINAL CI IN PROGRESS | Python 3.11/3.12, wheel, browser, provider, and Docker gates must pass on the combined v0.6-v0.8 branch |

## Delivered evaluation corpus

`evals/v0_6/cases.jsonl` contains 48 versioned development cases:

```text
in_domain:             12
ood:                   12
insufficient_evidence: 12
adversarial:           12
```

The corpus is development evidence, not an external holdout. It must not be used to claim unbiased
scientific quality.

## Previously verified v0.6 foundation

Draft PR #13 verified the provider/runtime foundation before the combined branch was created:

```text
PaperAgent CI:             29589067736 — SUCCESS
Release Hardening:         29589067905 — SUCCESS
```

The combined branch preserves that implementation while rebasing the final file tree onto the current
v0.5.1 `master` state.

## Pending external verification

1. Configure a GitHub Actions `MISTRAL_API_KEY` secret without committing the key.
2. Select an explicit supported Mistral model and dispatch the live v0.6 workflow.
3. Execute three complete Mistral-backed vertical research runs.
4. Freeze an external holdout digest and collect real observations.
5. Perform blinded human scientific review and threshold adjudication.

See the combined Handoff for the final commit, CI results, exact commands, and evidence boundaries.

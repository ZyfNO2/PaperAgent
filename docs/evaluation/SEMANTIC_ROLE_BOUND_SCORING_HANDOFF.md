# Semantic Role-Bound Scoring Handoff

## Status

**PARTIAL / REAL PROVIDER ACCEPTANCE IN PROGRESS**

PR #46 must remain Draft. Do not merge or mark Ready until the real-provider artifacts, strict score diagnostics, normalized-output audit, recovery summary, artifact upload, and final acceptance gate have completed and been reviewed.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `master`
- Base commit: `ad44e6337f002aa8ecea3559cc0a2f213e1c8859`
- Development branch: `fix/semantic-tailoring-role-bound-scoring`
- Draft PR: `#46`
- Start-of-review HEAD: `3342714d2e9d3cde73c1ff4342fd252a0d81d1ef`
- Current authoritative HEAD: use the latest PR head after this Handoff commit

## Current real-provider run

Workflow: `Academic Tailoring Runtime Recovery`, run `29954249461`.

At the time of this Handoff update:

- Steps 1-9 completed successfully.
- Step 10/15, `Execute cases 003, 005, 006, 007, and 010 with real provider`, was still in progress.
- Steps 11-15 remained pending:
  1. strict score diagnostics;
  2. normalized LLM output audit;
  3. recovery summary;
  4. artifact upload;
  5. real-runtime and score acceptance enforcement.

The five selected cases are:

- `atr-v1-003-nlp-bert-lora-clinc`
- `atr-v1-005-remote-oriented-small-edge`
- `atr-v1-006-industrial-usad-anomaly-transformer`
- `atr-v1-007-graph-graphsage-gat-ppi`
- `atr-v1-010-rec-coldstart-sequential`

No case is considered accepted until the uploaded artifacts and final enforcement step confirm it.

## Baseline identity policy

The current policy is:

1. An exact user-declared baseline has highest priority.
2. If the exact declared baseline is not found, a repository-backed direct baseline may be used only when its identity, task fit, provenance, and executable evidence are verified.
3. The system must not degrade to an arbitrary inferred baseline.
4. Review/survey papers cannot be treated as executable direct baselines.
5. Any fallback must remain explicit in the state, report, score evidence, and final decision.

This supersedes the earlier blanket statement that any repository-backed fallback is forbidden.

## Completed implementation areas

- Role-bound semantic scoring v2 is present and active in the live evaluation path.
- Runtime recovery CI includes real OpenAI-compatible/NVIDIA execution coverage, provider error classification, call-budget isolation, report fallback checks, and selected-case recovery.
- Offline provenance/runtime gates completed successfully in the active recovery run.
- Provenance-bound public dataset generation completed successfully.
- Isolated candidate workspace creation and installation completed successfully.
- Dedicated semantic role-bound CI passed for the current pre-Handoff HEAD.
- Eval snapshot provenance CI passed for the current pre-Handoff HEAD.

## Important implementation and verification scope

The current branch includes or validates work beyond the original 37-test Handoff, including:

- provider/runtime behavior and error classification;
- provider-call budget isolation;
- low-relevance baseline rejection;
- report fallback behavior;
- Case 005 invalid JSON/schema recovery;
- baseline-anchor handling for Case 006;
- normalized real-output auditing;
- runtime recovery artifact generation and acceptance enforcement.

The historical statement `37 passed` is not sufficient evidence for the current branch. Use the latest workflow jobs, logs, and artifacts.

## CI state at this update

For commit `3342714d2e9d3cde73c1ff4342fd252a0d81d1ef`:

Successful:

- `Semantic Tailoring Role-Bound CI`
- `Eval Snapshot Provenance CI`

In progress:

- `Academic Tailoring Runtime Recovery`

Failed repository-level workflows were also present. Their failures must be inspected individually before attributing them to this branch; a red aggregate status is not by itself proof of a regression in the changed path.

## Acceptance checklist

The branch remains PARTIAL until all items below are verified:

- [ ] Real-provider execution finishes for all five selected recovery cases.
- [ ] Runtime output files exist for every selected case.
- [ ] Strict score diagnostics complete without scorer infrastructure failure.
- [ ] Per-case scores and hard failures are manually cross-checked against artifacts.
- [ ] Normalized LLM output audit confirms JSON/schema and semantic output integrity.
- [ ] Case 003 preserves BERT and valid LoRA module provenance.
- [ ] Case 005 handles invalid JSON/schema output without false success.
- [ ] Case 006 applies exact-first, verified repository-backed direct baseline fallback, never arbitrary inference.
- [ ] Case 007 keeps GraphSAGE baseline and independently supported GAT module roles.
- [ ] Case 010 rejects the wrong cold-start baseline and records the supported decision.
- [ ] Recovery summary accurately distinguishes real-provider, offline, Mock/Fake/Stub, and unverified evidence.
- [ ] Workflow artifacts are uploaded and downloadable.
- [ ] Final real-runtime and score acceptance step passes.
- [ ] Any remaining failed repository workflows are classified as branch-related or pre-existing.

## Required score review

Each case must be reviewed on a 100-point scale:

- evidence and citations: 20;
- baseline and reproducibility: 15;
- gap and falsifiability: 15;
- module and compatibility contracts: 20;
- experiments and ablations: 20;
- conclusion and artifact completeness: 10.

Every deduction must cite an artifact location. Check for missed deductions, duplicate deductions, arithmetic errors, role-invalid credit, and disagreement between the score and the evidence.

## Real versus offline evidence

- The active step 10 run is real-provider execution.
- Offline provenance, compilation, Ruff, Mypy, focused pytest, configuration validation, and shell syntax checks are not real E2E evidence.
- Mock/Fake/Stub tests may verify control flow but cannot establish provider behavior or output quality.
- A successful provider call alone does not prove academic-method quality; the generated artifacts and role-bound score evidence must be reviewed.

## Known blockers and stop conditions

If the runtime workflow fails because of missing/invalid credentials, provider quota/rate limits, unavailable models, network failure, or external-service instability:

1. preserve and upload all available logs and partial artifacts;
2. classify the run as `BLOCKED / NOT VERIFIED`, not PASS;
3. record the failing endpoint, error class, retry/budget state, and affected cases;
4. complete all remaining offline diagnostics that do not depend on the provider;
5. provide exact rerun commands and acceptance criteria.

## Next developer steps

1. Re-read this Handoff and verify the PR head has not moved unexpectedly.
2. Inspect run `29954249461` until it reaches a terminal state.
3. Read the job steps and failure logs if any step fails.
4. Download and inspect the runtime-recovery artifact.
5. Review each selected case's state, trace, prompt log, execution summary, score diagnostics, and normalized output audit.
6. Fix branch-related defects with the smallest testable change; add regression tests and rerun the relevant workflow.
7. Update this Handoff with the final HEAD, exact test counts, artifact names, per-case scores, hard failures, and final status.
8. Keep PR #46 Draft unless every required acceptance item passes.

## Suggested verification commands

```bash
ruff check \
  src/paperagent/eval_runtime_reporting.py \
  src/paperagent/providers/runtime.py \
  src/paperagent/nodes/planning.py \
  src/paperagent/nodes/report.py \
  src/paperagent/method_design_draft.py \
  src/paperagent/strict_method_design.py \
  scripts/project_academic_tailoring_retrieval_v1.py \
  scripts/run_academic_tailoring_retrieval_v1.py \
  scripts/score_academic_tailoring_retrieval_v2.py

pytest -q \
  tests/providers/test_runtime.py \
  tests/nodes/test_planning_identity_priority.py \
  tests/nodes/test_method_design_baseline_anchor.py \
  tests/nodes/test_report_fallback.py \
  tests/methodology/test_strict_method_design.py \
  tests/methodology/test_method_design_draft.py \
  tests/evals/test_eval_runtime_reporting.py \
  tests/evals/test_eval_snapshot_provenance.py \
  tests/evals/test_academic_tailoring_retrieval_v1_boundary.py
```

## Current conclusion

**PARTIAL.** Offline gates and isolated setup are verified, but real-provider case execution and the downstream score/artifact acceptance chain were still running when this Handoff was committed. Do not treat the selected cases, the 10-case benchmark, or PR #46 as complete.
# CLAW Live Search Runtime Handoff

## Status

- Repository: `ZyfNO2/PaperAgent`
- Branch: `feat/claw-live-search-runtime`
- Base: `feat/claw-academic-tailoring-benchmark-v1`
- Pull request: `#34`
- PR state: Draft, open, mergeable, not merged
- Current scope status: `COMPLETE FOR CASE 017-020 REPAIR AND VALIDATION`
- Merge policy: do not merge or mark ready automatically

## Completed live validation

All results below used the real Mistral-backed benchmark path and live academic providers with Web search disabled.

| Case | Final result | Score | Decision | Hard failures | Evidence status |
|---|---:|---:|---|---:|---|
| `at-015-multibehavior-recommendation` | PASS | 95 | matched | 0 | final four-case batch |
| `at-017-mobilenetv3-plant-disease-supplied` | PASS | 94 | `REVISE_TO_PILOT` matched | 0 | attempt 2 |
| `at-018-yolox-tinydet-supplied` | PASS | 94 | matched | 0 | final four-case batch |
| `at-019-unet-unspecified-medical-segmentation` | PASS | 94 | `REVISE` matched | 0 | attempt 3 |
| `at-020-lightgcn-contrastive-supplied` | PASS | 94 | `REVISE` matched | 0 | attempt 3 |

### Persisted evidence

- Case 017 result commit: `bf473916e3c0c9bacbb485712b39eab56e66f5aa`.
- Cases 015/018/019/020 batch workflow: run `29758638711`, triggered by `955a107027c1445cb93869d4eb7c47c9d414d226`.
- Case 019 final result commit: `82901efc39e522aca1e8f3269aa7a406ee217408`.
- Case 020 final result commit: `2337151c50f731d5dd4eed49d88cb1ad7f5aa034`.
- Result files:
  - `evals/claw_academic_tailoring_v1/live-probes/four-case-batch-latest.json`
  - `evals/claw_academic_tailoring_v1/live-probes/single-case-repair-latest.json`
- Web supplementation remained disabled in every listed live run.

## Fixes completed during final validation

### Case 017 precision repair

- Added exact identity handling for `Searching for MobileNetV3`.
- Required plant-disease candidates to contain both plant semantics and disease semantics.
- Rejected retinal, skin-lesion, healthy-leaf species-classification, and other cross-domain candidates.
- Added Case 017 precision regressions.
- Offline gate run `29757888425`: Ruff, formatter, and Mypy returned zero; pytest reported `91 passed`.

### Offline contract and fixture repair

- Restored exact planning and method-design prompt contracts.
- Kept strict production Pydantic validation and corrected stale test fixtures instead of weakening schemas.
- Aligned provider-failure assertions with the current public error contract.
- Removed seven branch-wide offline regressions found after the final batch trigger.

### Conservative pilot decision policy

Added `src/paperagent/claw_pilot_policy.py` and integrated it into the real benchmark runtime.

- Ordinary unresolved priorities such as accuracy-versus-latency or business-goal ordering continue to use the existing bounded-pilot heuristic.
- A pilot is not recommended when the experimental target itself is still undefined, such as an unspecified organ/dataset in medical segmentation.
- A pilot is not recommended when a user-supplied core method remains an unidentified generic paper reference.
- A later clarification answer releases the conservative override.
- The policy is based on runtime state and supplied-material identity, not benchmark case IDs or gold decisions.

### Evidence Ledger and trace consistency

Added `src/paperagent/claw_trace_reconciliation.py` and applied it in:

- `src/paperagent/claw_benchmark_runtime.py`;
- `scripts/normalize_claw_benchmark_states.py`.

The reconciliation rule is deliberately narrow:

- the trace may inherit relevance only from an accepted Evidence Ledger entry;
- the relevant gap support must also be accepted;
- its audit checklist must explicitly contain `relevance_passed=true`;
- identity verification, role binding, gap binding, and acceptance are not synthesized or relaxed.

This removed the Case 019 `IDENTITY_ONLY_ACCEPTANCE` mismatch without allowing identity-only evidence through the gate.

### Recommendation-domain precision

Extended `src/paperagent/literature/specialized_guards.py` so recommendation-system queries require recommendation semantics in candidate evidence.

- Case 020 attempt 2 passed but exposed a false positive: a solar/wind forecasting paper entered accepted evidence.
- The new guard rejects that cross-domain candidate.
- Case 020 attempt 3 passed with only LightGCN, recommendation-system, collaborative-filtering, and graph-contrastive-learning evidence in the accepted set.

### Live-repair workflow coverage

Updated `.github/workflows/claw-single-case-live-repair.yml` so its pre-LLM gate now covers:

- pilot decision policy;
- trace reconciliation;
- recommendation-domain precision;
- their targeted tests.

The workflow still runs exactly one requested case, keeps Web search disabled, persists the compact result, and fails when the real result does not pass.

## Latest code CI

The latest code/workflow commit before the final live trigger was `4350b32152f4bf0327e20ba7303d57e7d168ce4e`.

All branch gates passed:

- `CLAW Live Search Verification`: run `29760569864` — success
- `Academic Tailoring Agent Evaluation`: run `29760569861` — success
- `PaperClaw Academic Tailoring Benchmark`: run `29760569857` — success
- `PaperAgent Interview Evidence`: run `29760570014` — success

The preceding reconciliation commit also passed all four corresponding gates, confirming that the decision and evidence fixes were independently green before the recommendation-domain change.

## Major files changed in this continuation

- `.claw-four-case-trigger.json`
- `.claw-single-case-trigger.json`
- `.github/workflows/claw-single-case-live-repair.yml`
- `docs/evaluation/CLAW_LIVE_SEARCH_RUNTIME_HANDOFF.md`
- `scripts/normalize_claw_benchmark_states.py`
- `src/paperagent/claw_benchmark_runtime.py`
- `src/paperagent/claw_pilot_policy.py`
- `src/paperagent/claw_trace_reconciliation.py`
- `src/paperagent/literature/specialized_guards.py`
- `src/paperagent/prompts/v0_1/planning.md`
- `src/paperagent/prompts/v0_1/method_design.md`
- `tests/evals/test_claw_pilot_policy.py`
- `tests/evals/test_claw_trace_reconciliation.py`
- `tests/literature/test_lightgcn_recommendation_precision.py`
- `tests/literature/test_mobilenetv3_plant_disease_precision.py`
- `tests/literature/test_adaptive_search_edges.py`
- `tests/literature/test_graph_adapter.py`

## Retrieval policy retained

- Review query precision before any provider call.
- Use one academic provider first and escalate sequentially only when verified relevance is insufficient.
- Do not fan out providers in parallel.
- Web supplementation is opt-in, bounded, and allowed only after academic insufficiency for approved low-risk queries.
- Generic Web pages remain pending and cannot bypass Verification or the Evidence Ledger.
- Per-query and task-level provider-call budgets remain enforced.
- Fake benchmark mode remains explicit-fixture-only and cannot silently inject empty evidence.

## Verification commands

```bash
ruff check \
  src/paperagent/claw_benchmark_runtime.py \
  src/paperagent/claw_pilot_policy.py \
  src/paperagent/claw_trace_reconciliation.py \
  src/paperagent/literature/specialized_guards.py \
  scripts/normalize_claw_benchmark_states.py \
  tests/evals/test_claw_pilot_policy.py \
  tests/evals/test_claw_trace_reconciliation.py \
  tests/literature/test_lightgcn_recommendation_precision.py \
  tests/literature/test_mobilenetv3_plant_disease_precision.py

ruff format --check \
  src/paperagent/claw_benchmark_runtime.py \
  src/paperagent/claw_pilot_policy.py \
  src/paperagent/claw_trace_reconciliation.py \
  src/paperagent/literature/specialized_guards.py \
  scripts/normalize_claw_benchmark_states.py \
  tests/evals/test_claw_pilot_policy.py \
  tests/evals/test_claw_trace_reconciliation.py \
  tests/literature/test_lightgcn_recommendation_precision.py \
  tests/literature/test_mobilenetv3_plant_disease_precision.py

mypy --config-file pyproject.toml

pytest -q \
  tests/evals/test_claw_benchmark_adapter.py \
  tests/evals/test_claw_pilot_policy.py \
  tests/evals/test_claw_trace_reconciliation.py \
  tests/literature/test_lightgcn_recommendation_precision.py \
  tests/literature/test_mobilenetv3_plant_disease_precision.py \
  tests/literature/test_multibehavior_recommendation_precision.py \
  tests/literature/test_third_batch_query_precision.py
```

## Known limitations and acceptance boundary

- The listed cases are real-LLM/live-provider validations, but they do not prove a fresh paid full-corpus 20/20 execution at the current HEAD.
- Several passing cases still report non-hard scoring findings for missing full-text review of core evidence. No claim is made that every accepted paper received full-text scientific review.
- Semantic Scholar rate limiting occurred in some runs; sequential fallback and provider budgets handled it without enabling Web search.
- No scientific baseline reproduction, measured model gain, full-text corpus audit, or production deployment validation is claimed.
- PR #34 is stacked on a non-main base branch. Merge sequencing and base drift must be reviewed before changing Draft status.

## Exact next handoff steps

1. Keep PR #34 Draft until the stacked base and desired merge order are reviewed.
2. Review the final code diff and persisted Case 019/020 single-case result together; do not judge the decision repair from the earlier failed batch alone.
3. If a fresh full 20-case run is required, obtain explicit provider/LLM budget approval, run it from the final branch HEAD, and persist a new full-corpus report rather than extrapolating from the targeted repairs.
4. Before merge, rebase or update the branch against the intended base and rerun all four CI workflows.
5. Do not enable Web search merely to increase evidence count; preserve academic-first retrieval and the existing precision gates.

## Leakage remediation status

The original 20 CLAW cases are a **development benchmark / contaminated evaluation set**. They may
be used for regression diagnostics only and are not independent evidence of generalization.

Production evidence binding now uses a corpus-independent role contract. A baseline needs a concrete
method identity, an experimental setting, and a measured result; mechanism evidence needs an explicit
limitation-intervention relation; risk evidence needs a failure condition or negative result. The
method builder no longer injects task-specific metrics and no longer creates a scoreable strong
comparison without a concrete comparator bound to accepted evidence. Pilot recommendation is emitted
by the production Quality Gate and is only projected by the benchmark adapter.

A new private holdout must be created and sealed outside this branch before it is run. After results
are opened, further changes informed by those results make that set a development set and require a
new holdout.

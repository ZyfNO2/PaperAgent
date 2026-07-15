# PaperAgent Re8.2 Post-Merge Code Review Handoff

## Status

```text
CODE REVIEW: COMPLETE
GATE CONTRACT PATCH: COMPLETE
FOCUSED / ISOLATED REGRESSION: PASS
FULL API REGRESSION DELTA: PASS
FRONTEND PRODUCTION BUILD: PASS
MERGE STATUS: NOT MERGED — PR REMAINS DRAFT
FOLLOW-UP API/FRONTEND CONTRACT: TRACKED IN ISSUE #3
```

## Repository

- Repository: `ZyfNO2/PaperAgent`
- Reviewed base: `master@dffce680ea8ca02d0a76112f8e5641a14c678e6f`
- Development branch: `fix/re8.2-postmerge-code-review`
- Draft PR: `#2 — Re8.2 post-merge review: harden Gate cycles and package contract`
- CI-verified implementation SHA: `180da5fd925c8f5c858cac9107d7076ce1eb3f26`
- GitHub Actions run: `29452080805` / run number `42`

## Code-review findings fixed

### HIGH — skip history consumed real evaluation rounds

Legacy `generated_by=skip` results remain in `reflection_gate_results` for audit. The original wrapper passed the complete current-cycle slice into the legacy evaluator, so a checkpoint that changed from `chain_only`/offline to real reflection could start at round 1 or immediately hit the cap.

Fix:

- `skip` and `reuse` remain visible in history;
- only `llm`, `fallback`, `rule`, and unknown legacy evaluations consume the bounded evaluation counter;
- skip-only history starts real evaluation at round 0;
- mixed history counts only actual evaluations;
- legacy real evaluations still consume their historical cap, so the migration cannot bypass a cap.

### HIGH — stale pass cache could split routing and fused-verdict state

Fingerprint equality alone was insufficient. An old pass could remain cached after a later cycle returned `revise` or `unresolved`. Reusing the old pass would emit a reuse trace while routing/fusion continued reading the later failure from `reflection_gate_results`.

Fix:

Reuse now requires all of the following:

1. cached entry is a real evaluated pass, not `skip` or `reuse`;
2. cached fingerprint matches current fingerprint;
3. active fingerprint matches current fingerprint;
4. cached cycle matches active cycle;
5. latest evaluated log result is the cached pass;
6. cached round and optional result-log index match the latest evaluated result.

A non-pass evaluation invalidates the previous cached Tailor pass with a merge-safe tombstone. Reverting to an older fingerprint creates a new cycle and performs a real evaluation instead of resurrecting an old pass.

### HIGH — transient skip-cache removal was not persisted

`tailor_gate_entry` previously removed a cached `generated_by=skip` pass only from the shallow state passed to the wrapper. If the real evaluation did not return pass, no `last_gate_pass` patch was emitted and the invalid skip cache remained in LangGraph state.

Fix:

- the entrypoint records whether a skip cache was removed;
- when no real pass replaces it, the patch writes `last_gate_pass.tailor_gate={}`;
- other Gate pass entries are preserved.

### MEDIUM — Gate audit broke the canonical seven-section package

The first WP1 implementation added `final_research_package.gate_execution`, so API/UI section enumeration reported `8/7`.

Fix:

- remove legacy top-level `gate_execution` if encountered;
- do not create a `_execution` pseudo Gate;
- attach execution metadata to `gate_results.tailor_gate.execution`;
- preserve exactly three Gate keys and seven canonical package sections;
- mirror the same audit object at `final_recommendation.gate_execution` for direct consumers.

## Added tests

New post-merge regression cases cover:

1. skip-only legacy history starts real evaluation at round 0;
2. mixed skip/evaluation history counts only real evaluations;
3. failed new cycle invalidates the old pass cache;
4. returning to an old fingerprint forces a new cycle/evaluation;
5. reuse requires matching active fingerprint and cycle metadata;
6. a trailing skip event does not hide the latest real evaluated pass;
7. skip-cache invalidation is persisted while other Gate cache entries survive;
8. package remains exactly seven sections;
9. Gate result keys remain the three real Gates;
10. old top-level or pseudo-Gate audit shapes are migrated safely;
11. missing metadata degrades to empty collections;
12. final-package wrapper does not mutate source state.

## CI design improvement

The repository-wide API suite has historical failures unrelated to this patch. Removing the suite would hide regressions; making all historical failures blocking would keep CI permanently red.

The new workflow therefore uses four layers:

1. focused `test_re82_*.py` — hard blocking;
2. isolated `-k re8` regression — hard blocking;
3. full API suite on PR head and current master in separate processes;
4. JUnit failure-set comparison — hard blocking only for head-only failures/errors.

Both full-suite reports are retained, so historical debt remains visible and measurable.

## Verification evidence

### Static and frontend

```text
Python compile: PASS
Ruff changed-file lint: PASS
React npm ci: PASS
React TypeScript + Vite production build: PASS
```

### Focused Gate suite

```text
tests: 34
passed: 34
failures: 0
errors: 0
skipped: 0
reported time: 0.417 s
```

### Isolated Re8 regression

```text
tests: 802
passed: 802
failures: 0
errors: 0
skipped: 0
reported time: 6.609 s
```

### Full API regression delta

PR head:

```text
tests: 1740
failures: 52
errors: 0
skipped: 17
```

Master baseline in the same job/environment:

```text
tests: 1733
failures: 55
errors: 0
skipped: 17
```

Comparison:

```text
head-only failures/errors: 0
resolved baseline failures: 3
regression delta: PASS
```

The 52 remaining failures are historical API-suite debt, including unregistered old one-topic routes, Re02 return-contract drift, and legacy unified-router default assumptions. They are not hidden: both JUnit files are uploaded.

### Artifact

- Artifact name: `re82-gate-test-results`
- Artifact ID: `8357895413`
- Digest: `sha256:4b468d350329252ea5647acdf21c0fd4bdbc9688da8b4c870110e2d6d7917968`
- Retention expiry: `2026-07-29`

Files:

```text
re82-gate.xml
re8-isolated.xml
api-head.xml
api-master.xml
```

## Remaining reviewed work

Tracked in GitHub issue `#3 — Re8.2 API/frontend contract: pass tiers, Gate execution visibility, and type parity`.

The issue covers:

- real `/seeded-summary` missing runtime/contract/quality pass fields;
- browser not receiving cycle/reuse metadata;
- nullable Gate results currently typed and rendered as non-null;
- TypeScript final-package shape drift;
- input seed count derived from resolved cards instead of original candidates;
- `SEED_FULLTEXT_UNAVAILABLE` incorrectly retained in Seed Audit UI semantics;
- frontend omission of backend `cache_first` network policy.

These changes require coordinated API schema, shared pure pass-check functions, TypeScript types, rendering, and E2E tests. They are intentionally not mixed into the Gate state-machine correction.

## Decision

```text
PR #2 OFFLINE VERDICT: PASS
SAFE TO REVIEW: YES
SAFE TO AUTO-MERGE: NO — remains Draft for owner review
REAL MISTRAL / vit_dr SMOKE: not rerun in this patch
```

No round cap, ablation threshold, Gate prompt, provider secret, result fixture threshold, or BLOCKED/quality invariant was weakened.

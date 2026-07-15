# PaperAgent Re8.2 WP1 Handoff

## Status

```text
WP1 IMPLEMENTATION: COMPLETE
OFFLINE VERIFICATION: PASS
REAL PROVIDER SMOKE: BLOCKED BY EXECUTION ENVIRONMENT
OVERALL Re8.2: PARTIAL / WAITING REAL TEST
```

WP1 的 Gate evaluation/reuse/cycle 合同已经实现并通过定向测试与完整 Re8 API 离线回归。按照统一执行合同，下一步必须先完成真实 `vit_dr` Mistral Gate-reuse smoke，再进入 WP2 Seed Repair 2.0。

## Repository

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `master`
- Base SHA: `e811d2b7daf05b5140d3d9c6dfdc9a90584390a7`
- Audit correction SHA: `4c1b5e938888a228e0ce476b0d486b2608ba6220`
- Development branch: `dev/re8.2-wp1-gate-reuse`
- Draft PR: `#1 — Re8.2 WP1: deterministic Tailor Gate reuse and cycle isolation`
- Offline-verified implementation SHA: `8a4f16e0946d1cc310c379b2d65106e83670c5f7`
- Merge status: not merged; PR remains Draft

## Completed implementation

### 1. Tailor Gate stable fingerprint

Implemented canonical SHA-256 fingerprint v2 over stable semantic dependencies:

- Tailored method content;
- compatibility analysis;
- assembly plan;
- ablation matrix;
- fair-comparison requirements;
- evidence gaps and evidence deltas;
- Seed identity and role.

Set-like business collections are sorted by stable keys. Ordered assembly steps remain order-sensitive.

Excluded from fingerprint:

- `raw_input`;
- PDF bytes;
- local paths;
- trace / ledger;
- timestamps / elapsed values;
- provider request IDs;
- operational `generated_by` metadata.

### 2. Evaluation / reuse / cycle separation

Added additive state contracts:

```text
last_gate_pass
gate_cycle_id
gate_cycle_start_index
gate_input_fingerprint
gate_reuse_count
gate_evaluation_events
gate_reuse_events
```

Behavior:

- Real evaluator output is appended to `reflection_gate_results`.
- Reuse does not append to `reflection_gate_results`.
- Reuse does not consume an evaluation round.
- Semantic input change starts a new cycle at round 0 while preserving historical evaluations.
- Legacy states without cycle metadata retain their consumed round count and cannot bypass the cap.
- `REFLECTION_GATE_MAX_ROUNDS` remains `2`.

### 3. Activation-safe cache

Added a Tailor entry guard:

- `full_agent + react_reflection` uses the Re8.2 evaluation/reuse path;
- `chain_only`, lite, and offline paths retain legacy skip behavior;
- `generated_by=skip` can never satisfy or populate the reusable pass cache;
- switching from skip mode to real reflection forces a real evaluation.

### 4. Final research package audit

Added `gate_execution` to both final package locations:

```text
final_research_package.gate_execution
final_recommendation.research_package.gate_execution
```

It contains cycle IDs, cycle starts, fingerprints, last passes, evaluation events, reuse events, and reuse counts.

### 5. Canonical execution contract

Added:

- `Plan/PaperAgent_Re8.2_EXECUTION_CONTRACT.md`

The execution contract explicitly makes the audit corrections mandatory and defines document precedence, WP order, WP1 architecture, test commands, and real-test boundary.

## Main files

### Added

- `apps/api/app/services/agents/graph/nodes/reflection_gate_reuse.py`
- `apps/api/app/services/agents/graph/nodes/tailor_gate_entry.py`
- `apps/api/app/services/agents/graph/nodes/final_recommendation_re82.py`
- `apps/api/tests/test_re82_gate_reuse.py`
- `apps/api/tests/test_re82_tailor_gate_entry.py`
- `apps/api/tests/test_re82_fingerprint_canonicalization.py`
- `apps/api/tests/test_re82_gate_registry_integration.py`
- `apps/api/tests/test_re82_final_package_gate_audit.py`
- `.github/workflows/re82-wp1.yml`
- `Plan/PaperAgent_Re8.2_EXECUTION_CONTRACT.md`

### Modified

- `apps/api/app/services/agents/graph/state.py`
- `apps/api/app/services/agents/graph/nodes/__init__.py`
- `pyproject.toml`

## Pre-existing repository defects repaired during regression

### Missing Re8.1 fixture

`apps/api/tests/test_re8_seed_resolver.py` and the committed Re8.1 acceptance report referenced:

```text
apps/api/tests/fixtures/seed_repair_cases.json
```

The file was absent from the referenced acceptance commit, `master`, and later inspected commits. This caused full Re8 collection failure.

Restored:

- `apps/api/tests/fixtures/seed_repair_cases.json`
- `apps/api/tests/test_re81_seed_repair_fixture_contract.py`

The restored fixture records `reconstructed_missing_dependency` provenance and freezes the declared distribution:

```text
10 exact-title
3 typo-light
2 not-found
3 disambiguation
2 conflict
= 20 cases
```

No test threshold, acceptance function, or expected status rule was weakened.

### Undeclared PDF test dependency

Fourteen Re8 paper-understanding tests required `fitz`, but PyMuPDF was not declared. Added an opt-in dependency group:

```bash
pip install -e ".[pdf]"
```

The `pdf` extra includes PyMuPDF and pdfplumber. Base installs retain the existing pypdf fallback and are not forced to take the optional structured-PDF dependency.

## Verification evidence

### GitHub Actions

- Workflow: `Re8.2 WP1 Gate Regression`
- Run ID: `29438466879`
- Run number: `29`
- Head SHA: `8a4f16e0946d1cc310c379b2d65106e83670c5f7`
- Conclusion: `success`

### Static checks

```text
Python compile: PASS
Ruff changed-file lint: PASS
```

### Focused WP1 tests

JUnit: `re82-wp1.xml`

```text
tests: 27
passed: 27
failures: 0
errors: 0
skipped: 0
reported test time: 0.390 s
```

### Full Re8 API regression

Command:

```bash
pytest -q apps/api/tests -k "re8"
```

JUnit: `re8-regression.xml`

```text
tests: 738
passed: 738
failures: 0
errors: 0
skipped: 0
reported test time: 5.498 s
```

### JUnit artifact

- Artifact name: `re82-wp1-test-results`
- Artifact ID: `8352398961`
- Digest: `sha256:b5cac6c665cfe2932af5e8942bab3f524db7d1ad4f431cc511c4690904b1105a`
- Retention expiry: `2026-07-29`

## Real tests not executed

### Mistral connectivity

Current execution environment still fails DNS resolution for:

```text
api.mistral.ai
```

Observed error:

```text
Temporary failure in name resolution
```

Therefore:

```text
Real Mistral API connectivity: BLOCKED BY EXECUTION ENVIRONMENT
Key validity: NOT VERIFIED
HTTP authorization status: NOT REACHED
```

No 401/403 was observed. No secret was printed, committed, added to an artifact, or placed in GitHub Actions.

### Not yet verified

- real JSON Provider smoke;
- real `vit_dr` Tailor Gate pass reuse;
- real `xlm_r` Seed Repair;
- real `yolo_steel` disambiguation;
- real backend/frontend E2E;
- browser display of Gate cycle/reuse fields.

Mock/fake evaluator tests and offline graph tests are not real E2E evidence.

## Required next steps

### Step 1 — restore Provider network access

The operator must use an environment that can resolve and connect to `api.mistral.ai`. Inject the Mistral key through a runtime secret or environment variable. Do not add it to the repository, workflow YAML, command history, trace, or artifact.

### Step 2 — minimum Provider smoke

Run the repository's existing minimal JSON-provider smoke with:

- frozen model ID;
- temperature 0;
- small token cap;
- explicit timeout;
- cost ceiling;
- response and trace redaction.

Pass condition:

```text
HTTP request reaches Mistral
valid JSON response is parsed
no secret appears in logs
model ID and endpoint are recorded
```

Failure condition:

```text
DNS/TLS/network failure
401/403
non-JSON response after bounded repair
secret leakage
cost/timeout limit exceeded
```

### Step 3 — real vit_dr Gate reuse

Execute `vit_dr` through the real provider path and verify:

1. first Tailor Gate evaluation produces a real pass;
2. final-review repair routes back through evidence compilation;
3. Tailor semantic fingerprint remains unchanged;
4. trace contains `gate_pass_reused`;
5. `reflection_gate_results.tailor_gate` length does not increase on reuse;
6. `gate_reuse_count.tailor_gate` increments;
7. routing remains `innovation_extractor` after reuse;
8. fused verdict is not blocked by Tailor re-entry cap.

Store a redacted artifact containing:

- model ID;
- run/case ID;
- input fingerprint;
- source cycle and round;
- evaluation log length before/after reuse;
- reuse event;
- final fused verdict;
- cost and latency;
- no prompt secret or raw PDF bytes.

### Step 4 — proceed to WP2 only after Step 3 passes

WP2 order:

1. unified SeedCandidate model;
2. critical-conflict veto before aggregate score;
3. missing-field-aware author/year/abstract normalization;
4. stable `candidate_id` instead of `selected_index`;
5. `repair_target/reason_code` schema and normalizer preservation;
6. API and frontend propagation;
7. frozen regression set plus independent holdout.

## Recommended local verification commands

```bash
python -m pip install -e ".[dev,pdf]"

python -m py_compile \
  apps/api/app/services/agents/graph/state.py \
  apps/api/app/services/agents/graph/nodes/__init__.py \
  apps/api/app/services/agents/graph/nodes/reflection_gate_reuse.py \
  apps/api/app/services/agents/graph/nodes/tailor_gate_entry.py \
  apps/api/app/services/agents/graph/nodes/final_recommendation_re82.py

ruff check \
  apps/api/app/services/agents/graph/state.py \
  apps/api/app/services/agents/graph/nodes/__init__.py \
  apps/api/app/services/agents/graph/nodes/reflection_gate_reuse.py \
  apps/api/app/services/agents/graph/nodes/tailor_gate_entry.py \
  apps/api/app/services/agents/graph/nodes/final_recommendation_re82.py \
  apps/api/tests/test_re81_seed_repair_fixture_contract.py \
  apps/api/tests/test_re82_*.py

pytest -q apps/api/tests/test_re82_*.py
pytest -q apps/api/tests -k "re8"
```

## Known limitations

- WP1 reuse is currently implemented only for Tailor Gate, matching the audited Re8.2 immediate failure mode.
- Old persisted states without fingerprint metadata are handled conservatively: they do not automatically reuse historical passes.
- Fingerprint v2 intentionally treats assembly step order as semantic.
- A previous exact semantic state may reuse its content-addressed pass if the fingerprint returns to the same value.
- Real Provider behavior, cost, latency, and frontend rendering remain unverified.

## Handoff decision

```text
Do not merge yet.
Do not start WP2 before the real vit_dr smoke.
Current branch is safe for review as an offline-verified Draft PR.
```

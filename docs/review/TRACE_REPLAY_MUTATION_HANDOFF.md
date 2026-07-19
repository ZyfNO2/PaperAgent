# PaperAgent Trace Replay / Mutation Corpus Handoff

## Status

**CLOUD DETERMINISTIC TRACE SLICE COMPLETE — real-LLM, live full-chain and scientific L2+ verification remain pending.**

This slice extends the deterministic C0–C2 evidence/state work from Draft PR #30. It does not
claim real-LLM accuracy, real retrieval quality, scientific acceptance, baseline reproduction,
empirical research gains, or complete checkpoint/crash-recovery coverage.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Dependency base: `fix/evidence-ledger-final-outcome-trace-exact`
- Dependency SHA: `9d239ff01798567d6da0b04c82943c868eb3734f`
- Development branch: `test/trace-v0.2-replay-mutation`
- Draft PR: `#32`
- Target PR base: `fix/evidence-ledger-final-outcome-trace-exact`
- Cloud-verified implementation SHA: `0ba8d9cb98ca62e2e827132783f6cdd59a151ad0`
- Merge status: not merged; PR remains Draft

## Delivered

- Strict canonical serialization of ordered `TraceEvent` records.
- SHA-256 trace digest bound to sequence number and complete event payload.
- Event-level invariant audit for:
  - one run identity;
  - unique event/span identities;
  - valid parent spans;
  - typed failure events;
  - event type/status consistency;
  - complete route decisions;
  - ordered node lifecycle;
  - final terminal event;
  - manifest-bound event count, route sequence, and digest.
- `TraceReplayReport` with optional final-state/report digests, verdict and blocker fields.
- Deterministic steel-defect polluted-retrieval trace fixture.
- Mutation corpus with one accepted baseline and twelve rejected mutations.
- CLI evaluator that writes a machine-readable corpus report and fails closed on a missed mutation.
- Dedicated Python 3.11/3.12 workflow plus Python 3.12 full offline branch-coverage regression.
- Persistent CI artifacts for static checks, targeted tests, mutation grading and full regression.

## Dataset

`evals/cloud_trace/steel-defect-pollution-001/` contains:

- `manifest.json`: frozen event count, route sequence and trace digest;
- `trace.json`: canonical deterministic trace;
- `cases.json`: one valid replay and twelve negative mutations.

Negative cases cover duplicate events, mixed run IDs, missing routes, untyped failures, status/type
mismatches, orphan parent spans, post-terminal activity, lifecycle reordering, event-count drift,
route-sequence drift and digest drift.

The frozen baseline trace digest is:

```text
sha256:4509dde5c368308d4ad9067d8eac8ff4da1939f62ac833a003d8ec6fece1f7bb
```

## Main files

- `src/paperagent/trace_replay.py`
- `scripts/run_trace_mutation_eval.py`
- `evals/cloud_trace/steel-defect-pollution-001/manifest.json`
- `evals/cloud_trace/steel-defect-pollution-001/trace.json`
- `evals/cloud_trace/steel-defect-pollution-001/cases.json`
- `tests/trace_mutation/test_trace_mutation_corpus.py`
- `.github/workflows/trace-replay-cloud.yml`

## Local verification

Executed against the exact PR #30 source snapshot plus this branch changes:

```text
ruff check <trace module, evaluator, tests>
pass

ruff format --check <trace module, evaluator, tests>
pass

mypy --config-file pyproject.toml
Success: no issues found in 116 source files

pytest -q tests/trace_mutation/test_trace_mutation_corpus.py \
  --cov=paperagent.trace_replay --cov-branch --cov-report=term-missing
4 passed; paperagent.trace_replay branch-aware coverage 93.47%

python scripts/run_trace_mutation_eval.py
13/13 cases classified correctly; 12/12 negative mutations rejected
```

## Exact-head cloud verification

Results are bound to implementation SHA:

```text
0ba8d9cb98ca62e2e827132783f6cdd59a151ad0
```

### Trace Replay Cloud

- Workflow run: `29701361136`
- Conclusion: success
- Python 3.11 trace replay contract: success
- Python 3.12 trace replay contract: success
- Ruff lint: pass
- Ruff format check: pass
- Strict Mypy: pass over 116 source files
- Targeted tests: 4 passed on Python 3.11 and Python 3.12
- Targeted trace module branch-aware coverage: 93.47%
- Mutation corpus: 13/13 classified correctly
- Negative mutations: 12/12 rejected
- Full offline regression: 375 passed, 11 skipped, 3 warnings, 0 failed
- Full repository branch-aware coverage: 90.53%

The 11 skips were intentional environment/dependency gates:

- Playwright browser smoke was not installed;
- five OpenAI-compatible real-LLM tests lacked opt-in and credentials;
- one live literature-provider smoke lacked opt-in;
- four real Mistral tests lacked real-LLM opt-in.

### Workflow artifacts

- Python 3.11 targeted artifact: `8446545668`
  - digest: `sha256:5e2cc976ad5c30db24025e25688cc673f8d1dd7df44da804019d4af053356359`
- Python 3.12 targeted artifact: `8446546426`
  - digest: `sha256:98aad6f5a5d92a9c4bc08bfc03d6f8212b3b7a804c0ff68209c1260c93cdb0f8`
- Python 3.12 full-regression artifact: `8446552342`
  - digest: `sha256:f6e111020f13205f76318ddfa50f7b81f59338712df03dc40d389ef830e0b654`

### Existing repository workflows

At the same implementation SHA:

- Academic Tailoring Agent Evaluation run `29701361154`: success
- PaperAgent Interview Evidence run `29701361148`: success

## Failed attempts retained as evidence

Two earlier workflow batches failed before tests because the new files did not yet match the
repository's Ruff formatting contract. The subsequent diagnostic artifact showed:

- `SIM102` on the nested route condition;
- formatting drift caused by using default 88-column formatting instead of the repository's
  100-column configuration;
- strict Mypy already passed.

The code and workflow were corrected; failed runs were not relabeled as successful.

## Architecture decisions

1. **Keep replay identity separate from scientific state consistency.**
   Existing PR #30 EvidenceLedger/FinalOutcome invariants remain authoritative for scientific
   state. This slice adds event-order and digest checks without replacing them.
2. **Bind digests to ordered, canonical event payloads.**
   Sequence numbers are added during canonical serialization so event reordering changes the digest.
3. **Use a development regression corpus, not a claimed holdout.**
   The steel-defect fixture is intentionally transparent and may guide implementation.
4. **Fail closed on missed mutations.**
   The evaluator exits non-zero when expected pass/fail classification or required error codes do not
   match.
5. **Keep real-provider validation separate.**
   Fake/offline trace evidence is not described as live E2E or scientific validation.

## Scientific and engineering boundaries

- This is deterministic offline trace-contract evidence, not a real end-to-end research-quality run.
- The fixture is a development/regression corpus, not a frozen scientific holdout.
- The audit verifies event-level contracts and manifest identity. It does not yet replay external
  provider side effects or prove checkpoint/crash recovery.
- The mutation corpus does not measure retrieval Precision/Recall or claim-level semantic accuracy.
- Real LLM, real full-chain provider, human relevance adjudication, baseline reproduction and
  empirical experiments remain unverified.

## Remaining work

1. Bind replay reports to complete graph-produced `FinalOutcome`, report and state artifacts.
2. Add property-based trace/state generation and longer fuzz campaigns.
3. Add concurrency, cancellation and checkpoint/restart replay fixtures.
4. Create a new unseen holdout only after thresholds and implementation are frozen.
5. Generate the immutable Local Real Test Bundle after the remaining Cloud Full slices pass.
6. Run real Provider/LLM canaries separately and preserve the Fake/offline/real distinction.

## Suggested verification commands

```bash
ruff check \
  src/paperagent/trace_replay.py \
  scripts/run_trace_mutation_eval.py \
  tests/trace_mutation/test_trace_mutation_corpus.py

ruff format --check \
  src/paperagent/trace_replay.py \
  scripts/run_trace_mutation_eval.py \
  tests/trace_mutation/test_trace_mutation_corpus.py

mypy --config-file pyproject.toml

pytest -q tests/trace_mutation/test_trace_mutation_corpus.py \
  --cov=paperagent.trace_replay \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=90

python scripts/run_trace_mutation_eval.py \
  --source-commit "$(git rev-parse HEAD)" \
  --output build/trace-replay-cloud/mutation-report.json

pytest -q \
  --cov=paperagent \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=90
```

## Final classification

- Trace replay/mutation implementation: **complete**
- Deterministic cloud verification: **complete and CI-verified**
- Real LLM / live full-chain canary: **pending**
- Scientific L2+, frozen holdout and independent review: **not verified**
- Overall branch state: **PARTIAL COMPLETE / DRAFT PR / WAITING FOR REAL AND SCIENTIFIC TESTS**

# PaperAgent Trace Replay / Mutation Corpus Handoff

## Status

**IMPLEMENTATION COMPLETE LOCALLY — exact-head cloud CI pending.**

This slice extends the deterministic C0–C2 evidence/state work from Draft PR #30. It does not
claim real-LLM accuracy, real retrieval quality, scientific acceptance, or complete crash-recovery
coverage.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Dependency base: `fix/evidence-ledger-final-outcome-trace-exact`
- Dependency SHA: `9d239ff01798567d6da0b04c82943c868eb3734f`
- Development branch: `test/trace-v0.2-replay-mutation`
- Target PR base: `fix/evidence-ledger-final-outcome-trace-exact`
- Merge status: not merged; keep Draft until exact-head CI is recorded

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

## Dataset

`evals/cloud_trace/steel-defect-pollution-001/` contains:

- `manifest.json`: frozen event count, route sequence and trace digest;
- `trace.json`: canonical deterministic trace;
- `cases.json`: one valid replay and twelve negative mutations.

Negative cases cover duplicate events, mixed run IDs, missing routes, untyped failures, status/type
mismatches, orphan parent spans, post-terminal activity, lifecycle reordering, event-count drift,
route-sequence drift and digest drift.

## Main files

- `src/paperagent/trace_replay.py`
- `scripts/run_trace_mutation_eval.py`
- `evals/cloud_trace/steel-defect-pollution-001/manifest.json`
- `evals/cloud_trace/steel-defect-pollution-001/trace.json`
- `evals/cloud_trace/steel-defect-pollution-001/cases.json`
- `tests/trace_mutation/test_trace_mutation_corpus.py`
- `.github/workflows/trace-replay-cloud.yml`

## Local verification

Executed against the exact PR #30 wheel/source snapshot:

```text
pytest -q tests/trace_mutation/test_trace_mutation_corpus.py
4 passed

pytest -q tests/trace_mutation/test_trace_mutation_corpus.py \
  --cov=paperagent.trace_replay --cov-branch --cov-report=term-missing
paperagent.trace_replay: 94% branch-aware coverage

python scripts/run_trace_mutation_eval.py \
  --source-commit 9d239ff01798567d6da0b04c82943c868eb3734f
13/13 cases classified correctly; 12/12 negative mutations rejected
```

The local container does not include Ruff, Mypy, LangGraph or LangChain Core. Therefore local
verification is limited to the pure trace module, evaluator, compilation and its deterministic
mutation corpus. Full repository verification is delegated to the exact-head GitHub workflow.

## Scientific and engineering boundaries

- This is deterministic offline trace-contract evidence, not a real end-to-end research-quality run.
- The fixture is a development/regression corpus, not a frozen scientific holdout.
- The audit verifies event-level contracts and manifest identity. It does not yet replay external
  provider side effects or prove checkpoint/crash recovery.
- Existing PR #30 final-state/EvidenceLedger invariants remain authoritative for scientific state;
  this branch adds trace-event and replay-digest coverage without replacing them.

## Pending exact-head evidence

Record after the branch is pushed and the Draft PR workflows complete:

- final commit SHA;
- Trace Replay Cloud run IDs and conclusions;
- Python 3.11/3.12 static/targeted results;
- full offline regression count and branch coverage;
- artifact IDs and digests;
- any skipped real-provider tests.

## Next steps

1. Bind this replay report to a complete graph-produced `FinalOutcome`, report and state artifact.
2. Add property-based trace/state generation and longer fuzz campaigns.
3. Add concurrency, cancellation and checkpoint/restart replay fixtures.
4. Generate the immutable Local Real Test Bundle only after all cloud gates pass.
5. Run real Provider/LLM canaries separately and preserve the Fake/offline/real distinction.

# PaperAgent Evidence / FinalOutcome / Trace Repair Handoff

## Status

**PARTIAL COMPLETE — cloud deterministic C0–C2 and live literature-provider smoke complete; real-LLM and scientific L2+ verification pending.**

This handoff records engineering verification and a bounded live literature-provider smoke. It does not claim real-LLM semantic accuracy, full-text review quality, real-corpus retrieval Precision/Recall, baseline reproduction, empirical research gains, or independent scientific acceptance.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `master`
- Base SHA: `4599053b6efda464aee1fe242db801427384a6c2`
- Development branch: `fix/evidence-ledger-final-outcome-trace-exact`
- Draft PR: `#30`
- Final implementation SHA before handoff-only commits: `152e5f398a38b169d9d1d4c9253fb89aa959703e`
- Handoff verification parent SHA: `3506b9516f3e109763df0e2559050204b4e45730`
- Merge status: not merged; PR remains Draft

PR #30 supersedes PR #29 only for exact-head CI evidence. PR #29 was not deleted or merged.

## Completed work

### Evidence contracts and acceptance

- Added `ResearchContract` shared across relevance and Gap review.
- Added deterministic lexical relevance assessment with explicit reason codes.
- Added abstract-level supporting-span assessment.
- Added per Evidence–Gap `GapSupportAssessment`.
- Added server-derived `EvidenceLedger` with fail-closed acceptance and coverage invariants.
- Separated:
  - identity verification;
  - research relevance;
  - claim/Gap support validity.
- Changed `EvidenceBundle.accepted_ids` and `coverage_by_gap` to represent final Ledger-derived scientific acceptance.
- Added `identity_verified_ids` and `relevance_rejected_ids` so a real paper can be rejected as research evidence without losing identity provenance.
- Preserved candidate Gap provenance for pending/failed identity records without allowing those records into coverage.

### Workflow and state

- Integrated identity → relevance → Gap binding → Ledger into `verify_evidence_node`.
- Preserved all evidence review artifacts when returning from the retrieval subgraph.
- Added a pre-synthesis Evidence Quality Gate:
  - if required gaps remain missing and retrieval budget is exhausted;
  - skip Synthesis and Method Design;
  - produce `REVISE` with a completed repair report.
- Kept the existing LangGraph architecture and LLM-call contract rather than adding unnecessary LLM nodes.

### Final state and report consistency

- Added canonical `FinalOutcome` separating:
  - execution status;
  - scientific verdict;
  - quality route;
  - report status.
- Scientific `NO_GO` is represented as a successful workflow conclusion, not a provider/program failure.
- Provider/program failure produces `failed / NOT_EVALUATED` in `FinalOutcome`.
- Existing `ExecutionMeta` retains its legacy `blocked` terminal for failed workflows so current task/API consumers remain compatible.
- Report generation renders from `FinalOutcome` and cannot independently redefine terminal state.
- Report validation rejects unknown or non-accepted evidence IDs.
- `REVISE` reports require concrete next actions.

### Trace and persistence

- Added independent state/trace invariant audit before persistence.
- Audit independently checks:
  - EvidenceBundle acceptance against EvidenceLedger;
  - Gap coverage against accepted bindings;
  - Report evidence IDs against accepted Ledger IDs;
  - Report status against FinalOutcome;
  - GO against Quality pass;
  - NO_GO against canonical Method Audit;
  - recorded Quality route against final Quality state.
- Contract mutation produces typed `TRACE_CONTRACT_FAILURE` rather than silently persisting a false success.

### Cloud test infrastructure

- Added `.github/workflows/evidence-contract-cloud.yml`.
- The workflow stores logs and a source snapshot as an artifact.
- The workflow runs:
  - Ruff lint;
  - Ruff format check;
  - strict Mypy;
  - focused Evidence/Trace tests;
  - full offline pytest regression.

## Main files changed or added

### Production

- `src/paperagent/schemas/relevance.py`
- `src/paperagent/schemas/outcome.py`
- `src/paperagent/schemas/evidence.py`
- `src/paperagent/schemas/__init__.py`
- `src/paperagent/evidence_relevance.py`
- `src/paperagent/outcome.py`
- `src/paperagent/retrieval/verify_evidence.py`
- `src/paperagent/state.py`
- `src/paperagent/graph.py`
- `src/paperagent/nodes/quality_gate.py`
- `src/paperagent/nodes/report.py`
- `src/paperagent/nodes/persist.py`

### Tests and CI

- `.github/workflows/evidence-contract-cloud.yml`
- `tests/nodes/test_evidence_ledger_outcome_trace.py`
- `tests/e2e/test_evidence_pollution_flow.py`
- `tests/e2e/test_evidence_quality_gate_flow.py`
- `tests/e2e/test_graph_e2e_bounded_failure.py`
- `tests/e2e/test_graph_e2e_malformed.py`
- `tests/e2e/test_graph_e2e_timeout.py`
- `tests/graph/test_hitl.py`
- `tests/integration/test_bounded_failures.py`
- `tests/ood/test_cases.py`

## Regression coverage added

- Real/identity-verified but cross-domain paper is rejected before Synthesis.
- Related paper cannot support an unrelated Gap from query provenance alone.
- Relevant paper with claim-level Gap overlap enters the Ledger.
- Model-/fixture-originated Gap IDs are not trusted as production coverage.
- Unknown Report evidence IDs are rejected.
- Mutated Gap coverage is detected by the independent auditor.
- Scientific NO_GO remains a completed scientific result.
- Missing evidence after budget exhaustion becomes REVISE and skips Synthesis/Method.
- Malformed LLM output and provider timeout remain NOT_EVALUATED.
- HITL resume does not repeat Intake and uses explicit deterministic evidence fixtures.
- OOD fixture cases declare explicit evidence contracts and remain isolated by domain.

## Verified CI and tests

### Implementation SHA verification

Results bound to:

`152e5f398a38b169d9d1d4c9253fb89aa959703e`

#### Evidence Contract Cloud

- Workflow run: `29699837626`
- Conclusion: success
- Artifact: `evidence-contract-cloud-29699837626`
- Artifact digest: `sha256:3cfdf652cba0f03260ede60627b772ea22258a906c9c486159d0dc0534a72072`
- Ruff lint: pass
- Ruff format: pass
- Strict Mypy: pass over 115 source files
- Focused deterministic/C2 tests: 15 passed
- Full offline regression: 371 passed, 11 skipped, 0 failed

The 11 default-run skips were intentional environment/dependency gates:

- Playwright browser smoke was not installed in the default offline job;
- real OpenAI-compatible LLM smoke lacked API key and opt-in flag;
- real Mistral smoke lacked API key/model and opt-in flag;
- real literature-provider smoke was not enabled in the default offline job.

#### Repository workflows

- PaperAgent CI run `29699837616`: success
- PaperAgent v0.5.1 Release Hardening run `29699837636`: success
- Academic Tailoring Agent Evaluation run `29699837638`: success
- PaperAgent Interview Evidence run `29699837628`: success

### Handoff parent SHA verification

Results bound to:

`3506b9516f3e109763df0e2559050204b4e45730`

- Evidence Contract Cloud run `29699943400`: success
- PaperAgent CI run `29699943388`: success
  - Python 3.11 offline verification: success
  - Python 3.12 offline verification: success
- Academic Tailoring Agent Evaluation run `29699943396`: success
- PaperAgent Interview Evidence run `29699943381`: success
- PaperAgent v0.5.1 Release Hardening run `29699943386`: success
  - Docker readiness smoke: success
  - installed wheel / CLI / plugin / web smoke: success
  - Chromium vertical smoke: success
  - live OpenAlex / arXiv / Crossref / DataCite smoke: success

The live provider smoke proves bounded API availability and expected provider contract behavior for its fixed smoke cases. It does not establish real-corpus relevance quality or scientific claim support accuracy.

## Architecture decisions

1. **Do not equate DOI/metadata verification with research acceptance.**
   Identity remains a separate fact from relevance and Gap support.
2. **Coverage is server-derived.**
   Downstream model output cannot directly set accepted coverage.
3. **Keep deterministic cloud review separate from real semantic evaluation.**
   Current abstract review is a C0–C2 deterministic contract implementation, not a claim of real-world semantic accuracy.
4. **Preserve current graph shape where possible.**
   The implementation reuses the existing retrieval verification node and Quality/Report/Persist lifecycle.
5. **FinalOutcome is authoritative; legacy ExecutionMeta is compatibility-facing.**
   This avoids breaking existing HTTP/task clients while correctly representing failed execution versus scientific NO_GO/REVISE.
6. **Fail closed at persistence.**
   The independent audit does not trust a top-level Trace or Report conclusion merely because it matches itself.

## Executed live verification

The Release Hardening workflow executed and passed its fixed live provider smoke for:

- OpenAlex;
- arXiv;
- Crossref;
- DataCite.

This live smoke is limited to provider connectivity, parsing and fixed contract cases. It is not a live end-to-end PaperAgent research-quality evaluation.

## Not executed / not verified

The following remain pending and must not be represented as completed:

- real OpenAI-compatible structured-output smoke;
- real Mistral structured-output smoke;
- live end-to-end graph execution using a real LLM plus live retrieval;
- real full-text retrieval and semantic review;
- real corpus Precision@5 / Recall@10 measurement;
- human relevance and Claim–Evidence adjudication;
- real baseline reproduction;
- empirical method experiments and ablations;
- frozen post-development holdout evaluation;
- independent scientific review.

## Known limitations

- Deterministic lexical/abstract assessment is intentionally conservative infrastructure for cloud tests; it is not a replacement for the planned real structured semantic reviewer.
- Full-text Top-K review is not implemented in this slice.
- Trace auditing covers final artifact/state invariants but is not yet the complete Trace v0.2 event-sequence/hash/replay specification from the full plan.
- Property-based testing, large mutation generation, long fuzzing, concurrency stress, and crash-recovery campaigns remain outside this implementation slice.
- PR #30 is intentionally Draft and unmerged.

## Remaining L1 verification instructions

Use the exact branch/commit from this handoff. Never place API keys in the repository or logs.

### 1. Optional literature-provider rerun

A live provider smoke already passed in Release Hardening. Re-run only when diagnosing provider drift or local network behavior:

```bash
export PAPERAGENT_RUN_REAL_PROVIDER=1
export PAPERAGENT_CONTACT_EMAIL="your-contact-email@example.com"  # optional but recommended
export SEMANTIC_SCHOLAR_API_KEY="..."                              # optional
pytest -q tests/real_provider/test_literature_smoke.py -m "real_provider and network"
```

Expected pass conditions:

- OpenAlex search status is `success`;
- arXiv search status is `success`;
- Crossref verifies DOI `10.1038/nature14539` using `crossref_doi_exact`.

### 2. OpenAI-compatible structured-output smoke

```bash
export PAPERAGENT_RUN_REAL_LLM=1
export PAPERAGENT_OPENAI_API_KEY="..."
export PAPERAGENT_OPENAI_BASE_URL="https://api.openai.com/v1"  # replace for compatible endpoint
export PAPERAGENT_OPENAI_MODEL="gpt-4o-mini"                   # replace as required
pytest -q tests/real_llm/test_llm_smoke.py tests/real_llm/test_real_llm_graph.py -m llm
```

Expected pass conditions:

- Planning, Synthesis, Method and Report parse into production Pydantic schemas;
- the real graph terminates with contract-valid state and report;
- no unknown Evidence ID or Trace contract failure occurs.

### 3. Mistral structured-output smoke

```bash
export PAPERAGENT_RUN_REAL_LLM=1
export MISTRAL_API_KEY="..."
export PAPERAGENT_MISTRAL_MODEL="<available-model-name>"
pytest -q tests/real_provider/test_mistral_smoke.py -m "real_provider and network"
```

Expected pass conditions:

- all four production schema cases return instances of their requested schema;
- no unbounded retry, malformed response fallback, or secret leakage occurs.

### 4. Required returned evidence

Return:

- exact commit SHA;
- executed command;
- pytest summary;
- sanitized failure traceback, if any;
- real provider/model names;
- token/cost/latency output when available;
- generated Trace/FinalOutcome/Report artifacts for any full-graph case.

Do not return API keys, Authorization headers, or raw secret-bearing environment dumps.

## Next developer steps

1. Run the real OpenAI-compatible and/or Mistral LLM smoke tests against the exact handoff commit.
2. Add one live full-graph canary combining a real LLM with live retrieval while preserving a strict budget.
3. Fix provider/model-specific schema issues without weakening deterministic validators.
4. Re-run all C0–C2 and Release Hardening CI after every prompt/provider change.
5. Add structured real semantic relevance and Top-K full-text review behind versioned contracts.
6. Expand Trace v0.2 sequence/hash/replay and automated mutation coverage.
7. Build a real development corpus, freeze thresholds, then create a new unseen holdout.
8. Keep PR #30 Draft until real-LLM evidence and review boundaries are accepted.

## Final classification

- Cloud deterministic C0–C2: **complete and CI-verified**
- Live literature-provider smoke: **complete for fixed smoke cases**
- Real OpenAI-compatible / Mistral LLM L1: **pending**
- Live full-chain research canary: **pending**
- Real scientific L2+ and frozen holdout: **not verified**
- Overall: **PARTIAL COMPLETE / WAITING FOR REAL-LLM AND SCIENTIFIC TESTS**

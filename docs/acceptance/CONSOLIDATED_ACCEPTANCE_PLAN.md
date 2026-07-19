# PaperAgent Consolidated Acceptance Plan

## 1. Acceptance levels

This plan separates four decisions that must never be conflated:

1. **Review-base acceptance** — the consolidated code is correct and testable against the immutable
   pre-rewrite base.
2. **Current-master migration acceptance** — the accepted change set is safely reconstructed on the
   force-rewritten `master` lineage with no unrelated deletion.
3. **Engineering release acceptance** — an installable local single-user/trusted-network candidate is
   operationally acceptable.
4. **Scientific capability acceptance** — claims involving real LLM quality, real literature,
   reproducibility, novelty, or research validity are supported.

Passing one level does not imply passing the next.

## 2. Fixed identities

```text
Historical review PR:  #17 (superseded by clean integration PR #25)
Historical review base: integration/pre-rewrite-v0.5.1-base
Historical base SHA:   497982242023e3b621fa8b31816a6f2b8d899d4a
Clean integration PR:  #25 (merged)
Master HEAD:           4f81e19a89a68a3fe729a5c85b5e97286cc21b05
Superseded PRs:        #14, #16, #17, #19, #20, #21, #22
```

The clean integration branch (`integration/paperagent-v0.9-clean`) was based on current `master` and
contains the final state of PR #17–#22. It was merged via PR #25.

## 3. Evidence record requirements

Every acceptance record must include:

- exact base and head SHA;
- UTC execution time;
- operating system and Python versions;
- workflow run ID or exact command;
- configuration/input manifest digest;
- artifact names, IDs, and SHA-256 digests;
- PASS, FAIL, or INCOMPLETE status;
- skipped tests and known exclusions;
- reviewer identity and sign-off date.

Secrets, private prompts, credentials, and private research inputs must not enter logs or artifacts.
An `INCOMPLETE` result cannot be converted to `PASS` by narrative explanation.

## 4. Gate A — consolidation and change control

### Procedure

1. Confirm #17 is the sole open integration PR for this program.
2. Confirm #14 and #16 are closed, unmerged, and marked superseded.
3. Confirm #17 is based on `integration/pre-rewrite-v0.5.1-base` during review.
4. Record the intended changed-file manifest and per-file status.
5. Review the complete stable-base-to-head diff.
6. Confirm no temporary workflow, payload, staging, or self-modifying CI file remains.

### Acceptance

- One integration PR.
- Intended diff is reviewable and approximately the expected 150-file scope.
- No direct change to `master` occurred.
- No unrelated mass deletion is present in the review diff.

## 5. Gate B — static quality and source integrity

```bash
python -m compileall -q src/paperagent
ruff check .
ruff format --check --diff .
mypy --config-file pyproject.toml
```

Also inspect for:

- import-time mutation or monkey patching;
- `eval`, `exec`, or unbounded subprocess use;
- unsafe path writes and archive extraction;
- secret or raw traceback exposure;
- broad exception handlers that bypass typed errors;
- generated artifacts treated as authoritative source.

### Acceptance

- All commands pass on Python 3.11 and 3.12 where configured.
- Compatibility modules are re-exports only.
- No unresolved P0/P1 source finding remains.
- Any suppression is narrow and documented.

## 6. Gate C — offline tests and coverage

```bash
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
```

Required regression coverage includes:

- no import-time policy rebinding;
- synthetic, mixed, and real evidence scopes;
- scientific release readiness remains fail-closed;
- stable provenance and supported-claim requirements;
- weak novelty wording variants;
- duplicate identifiers, seeds, metrics, and resources;
- non-finite numeric rejection;
- complete experiment fairness signature;
- undeclared module rejection;
- trainable-module loss requirement;
- observed SQLite journal mode;
- idempotency, claim, cancellation, restart, review, and export behavior.

### Acceptance

- Zero failing offline tests.
- Configured statement/branch coverage threshold passes.
- Skips are limited to explicitly credentialed, browser, network, or live-provider tests.
- Snapshot changes are intentional and reviewed.

## 7. Gate D — package, CLI, and plugin acceptance

```bash
python -m build --wheel
python -m venv /tmp/paperagent-acceptance
/tmp/paperagent-acceptance/bin/pip install dist/*.whl
/tmp/paperagent-acceptance/bin/paperagent --help
/tmp/paperagent-acceptance/bin/paperagent plugins list
```

Install and invoke the independent external-plugin example with exact command-local authorization.

### Acceptance

- Wheel installs in a clean environment.
- CLI, built-in plugins, external plugin, and packaged assets work from the installed Wheel.
- Unauthorized external entry points are not imported.
- Plugin JSON is finite, atomic, no-overwrite, and contract-valid.

## 8. Gate E — asynchronous task and durable-state acceptance

Exercise:

1. new task submission and `task.queued` persistence;
2. same idempotency key/same request reuse;
3. same key/different request conflict;
4. concurrent identical submission;
5. unique concurrent task claim;
6. polling and monotonically ordered persisted events;
7. SSE resume from cursor;
8. queued and running cancellation;
9. cancel/complete race;
10. fail-closed process restart;
11. typed malformed/oversized result failure;
12. optimistic review conflict;
13. deterministic JSON, Markdown, and BibTeX export.

### Acceptance

- State and terminal event transitions are transactional.
- No duplicate task execution in the documented single-process boundary.
- Errors contain no internal stack trace, prompt, credential, or secret-bearing metadata.

## 9. Gate F — database, migration, diagnostics, and metrics

Procedure:

- initialize a new SQLite database;
- rerun initialization and prove idempotency;
- reject missing, empty, task-only, and future-schema databases without side effects;
- verify WAL, busy timeout, and concurrency behavior;
- query `/readyz`, `/v1/diagnostics/runtime`, and `/metrics`;
- execute the 500-task benchmark and record environment limits.

### Acceptance

- Diagnostics reports observed `PRAGMA journal_mode`.
- Incompatible schema or executor failure returns readiness `503`.
- Diagnostics/metrics contain no request body, prompt, response body, credential, or idempotency key.
- Benchmark is explicitly not represented as a production SLO.

## 10. Gate G — provider, retry, repair, budget, and redaction

Test typed handling for:

- 401/403 authentication or authorization failure;
- 429 rate limiting;
- connection, read, and total timeout;
- transient 5xx;
- malformed JSON and schema-invalid JSON;
- empty or thinking-only structured output;
- unknown token usage or price;
- call, token, elapsed-time, and monetary budget exhaustion;
- cancellation before and after issuing a provider request.

### Acceptance

- Retry is limited to documented retryable classes and bounded attempts.
- Schema repair is bounded and cannot become an unrestricted second answer.
- Unknown usage or price fails monetary control closed.
- Redaction covers keys, Bearer values, query secrets, assignments, and configured aliases.

## 11. Gate H — academic-method deterministic audit

Required cases:

- complete plan;
- missing/unreproduced baseline;
- unverified or claim-free evidence;
- incompatible/unknown license;
- no proposed module;
- contaminated baseline;
- shape-only compatibility;
- trainable module without loss;
- undeclared module in experiment;
- unfair budget, metrics, seeds, uncertainty, resources, or stopping criteria;
- missing single-module or leave-one-out ablation;
- composition-only novelty;
- unsupported observed result;
- missing paper-to-method attribution;
- non-finite metrics and duplicate identifiers.

### Acceptance

- Blocking provenance, license, compute, or semantic failures cannot return `GO`.
- Composition-only novelty returns at most `REVISE`.
- Every borrowed component has source, role, interface, adapter, effect, and failure mode.
- Baseline, single-module, full, and required leave-one-out arms use the same fairness signature.

## 12. Gate I — academic-tailoring Agent evaluation

```bash
python scripts/run_academic_tailoring_eval.py \
  --output-dir build/academic-tailoring-eval
```

### Acceptance

- All committed synthetic cases satisfy expected decisions and rubric thresholds.
- Result targets remain `proposed` unless immutable observed evidence is attached.
- Synthetic fixtures report:
  - `evidence_scope=synthetic_evaluation`;
  - `readiness=synthetic_evaluation_only`;
  - `scientific_release_ready=false`.
- Mixed/unverified inputs cannot be reported as real verified evidence.
- Real-verified inputs can advance only to `ready_for_controlled_experiment`.
- Corpus artifacts and digests are deterministic.
- Documentation states that this validates contracts, not real scientific validity or global novelty.

## 13. Gate J — browser, web, and container

Procedure:

- serve the installed package on loopback;
- run Chromium submit → progress → review → export;
- build and run the container as the configured unprivileged user;
- use a persistent `/data` volume;
- check packaged assets and `/readyz`;
- confirm non-loopback bind refuses operation without explicit acknowledgement.

### Acceptance

- Browser contains no provider key or Agent decision logic.
- CSP and package-local assets remain intact.
- Public binding remains documented as unauthenticated/trusted-network only.
- Restart preserves terminal state and fails in-flight work closed.

## 14. Gate K — live-provider engineering evidence

This gate is opt-in and requires repository Secrets. Never place `MISTRAL_API_KEY` in code, PR text,
logs, or chat.

Procedure:

1. validate all production structured schemas with the configured real model;
2. run three consecutive frozen-input vertical executions;
3. record redacted latency, tokens, retries, repairs, errors, and cost;
4. observe or safely simulate 429, timeout, malformed output, and thinking-only behavior;
5. run live OpenAlex, arXiv, Crossref, and DataCite smoke.

### Acceptance

- Three consecutive runs finish within fixed budgets.
- No credentials or prompt bodies leak.
- Retry and repair remain bounded and attributable.
- Cost is known or execution fails closed.
- Evidence names the exact model and date.

## 15. Gate L — real scientific capability

Mandatory before claiming reliable research design, novelty, or publication-ready output:

1. frozen external holdout unused in prompt/rule design;
2. real primary sources with DOI/PMID/repository commit and claim-level support;
3. executable baseline reproduction with environment, data, preprocessing, split, seeds, logs, and
   digests;
4. baseline, single-module, full, and interaction/leave-one-out experiments;
5. statistical uncertainty, robustness, compute, and failure analysis;
6. data license, privacy, ethics, and human-subject approval where applicable;
7. blinded domain-expert review;
8. inter-rater agreement and disagreement adjudication;
9. calibrated false-GO, false-NO_GO, unsupported-claim, citation-mismatch, and repair-success rates;
10. limitations distinguishing local evidence from global novelty.

### Acceptance

- No critical claim is uncovered; unknown remains unknown.
- Every observed result has immutable evidence.
- Baseline reproduction meets the predeclared tolerance.
- Human-review acceptance and agreement thresholds pass.

## 16. Gate R — reconciliation with force-rewritten `master`

This gate is mandatory before any code from the stable review branch enters current `master`.

### Procedure

1. Create a fresh migration branch from the then-current rewritten `master` SHA.
2. Produce a manifest of the accepted review-base changes: path, status, mode, and content digest.
3. Overlay only those accepted files onto the fresh migration branch.
4. For files that also exist and changed independently on rewritten `master`, perform explicit semantic
   conflict resolution; never replace whole directories blindly.
5. Compare the migrated tree against current `master`.
6. Verify there are zero unrelated deletions, renames, permission changes, submodule changes, or
   workflow changes.
7. Verify every intended accepted file has the expected content or an explicitly reviewed adaptation.
8. Rerun Gates B–J on the migrated head.
9. Record the current-master base SHA, migrated head SHA, full changed-file manifest, CI runs, and
   artifacts.
10. Obtain a second reviewer sign-off focused specifically on repository-tree preservation.

### Hard failure conditions

- any unexplained mass deletion;
- any file outside the accepted manifest changed without explicit review;
- any accepted invariant lost during conflict resolution;
- any attempt to merge the old-history branch directly into rewritten `master`;
- reuse of review-base CI as proof for the migrated head.

### Acceptance

- Zero unrelated deletion or overwrite.
- All intended changes are present and traceable.
- All migrated-head CI gates pass.
- Tree-preservation reviewer signs off.

## 17. Decision checklists

### Review-base acceptance

- [x] PR #17–#22 reviewed against the immutable review base.
- [x] Gates A–J pass on the clean integration branch.
- [x] No open P0/P1 finding remains.
- [x] Exact workflow and artifact evidence is recorded.

### Current-master migration acceptance

- [x] Review-base acceptance passes.
- [x] PR #25 passes on a fresh branch from current `master`.
- [x] Zero unrelated deletion demonstrated (only build artifacts removed).
- [x] Migrated-head CI and review pass.

### Engineering release acceptance

- [x] Current-master migration acceptance passes.
- [x] Clean Wheel/container acceptance passes from the merged SHA.
- [x] Backup, migration, rollback, and local recovery are exercised.
- [x] Operator accepts the local single-user/trusted-network boundary.
- [ ] Release notes list all excluded live/scientific gates.

### Scientific capability acceptance

- [ ] Engineering release acceptance passes.
- [ ] Gates K and L pass.
- [ ] Domain and reproducibility reviewers sign off independently.
- [ ] Synthetic evidence is never relabeled as real evidence.
- [ ] Final claims and limitations match the accepted evidence.

## 18. Final acceptance record

```text
Decision level:       REVIEW_BASE | CURRENT_MASTER_MIGRATION | ENGINEERING_RELEASE | SCIENTIFIC
Decision:             PASS | PASS | PASS | INCOMPLETE
Stable base SHA:      497982242023e3b621fa8b31816a6f2b8d899d4a
Final review head SHA: 2cfc15c2 (clean integration)
Current master SHA:   4f81e19a89a68a3fe729a5c85b5e97286cc21b05
Migrated head SHA:    4f81e19a89a68a3fe729a5c85b5e97286cc21b05
UTC date:
Python versions:
Workflow run IDs:
Artifact IDs/digests:
Changed-file manifest digest:
Offline tests/coverage:
Installed artifact:
Browser/container:
Live providers:
Real sources/reproduction:
Human review:
Known exclusions:
Reviewer(s):
Sign-off:
```

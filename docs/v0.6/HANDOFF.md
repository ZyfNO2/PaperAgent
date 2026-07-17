# PaperAgent v0.6 Real LLM Integration Handoff

## Delivery status

`PARTIAL COMPLETE / LIVE MISTRAL AND SCIENTIFIC EVALUATION NOT VERIFIED`

The provider contracts, Mistral adapter, explicit real runtime path, cost and telemetry controls,
evaluation foundation, offline tests, and existing v0.5.1 release regressions are implemented and
verified. Credentialed Mistral execution, a real Mistral-backed end-to-end research task, the required
48-case evaluation corpus, external holdout execution, and blinded human scientific review remain
pending.

No Fake, Mock, Stub, static check, deterministic demo, or literature-provider smoke is represented as
real LLM evidence.

## Repository and delivery branch

```text
Repository:               ZyfNO2/PaperAgent
Base branch:              master
Implementation branch:    feat/v0.6-real-llm-integration
Draft PR:                 #13
Verified implementation:  df1aa39264ce504b0273d07d0d614716529f08e0
```

The authoritative final branch head may include only Handoff publication and temporary-diagnostic
workflow removal after the verified implementation commit above.

## Delivered

### Provider and policy foundation

- provider-neutral frozen runtime configuration;
- Mistral-first provider selection without adding provider types to graph state;
- HTTPS base URL validation and environment-only secret loading;
- typed provider errors compatible with the existing node error bridge;
- bounded physical-call, input-token, output-token, wall-clock, and optional monetary budgets;
- versioned operator price-table contracts;
- invocation and logical-call identifiers;
- redacted telemetry containing fingerprints, usage, latency, attempt, outcome, and error category;
- no raw chain-of-thought, authorization header, API key, or provider object persistence.

### Mistral structured-output adapter

- asynchronous `/chat/completions` adapter behind the existing `LLMProvider` protocol;
- injectable `httpx.AsyncClient` transport for deterministic offline tests;
- native JSON-schema request construction from the requested Pydantic model;
- strict Pydantic validation;
- at most one configured schema-repair attempt;
- bounded retry handling for connection, rate-limit, and provider 5xx failures;
- fail-closed handling for authentication, permission, invalid request, malformed response,
  unsupported schema mode, ambiguous read timeout, and exhausted budgets;
- usage extraction and optional cost estimation;
- compatibility fields used by existing Trace code: `calls`, `model_name`, `last_usage`, and
  `last_latency_ms`.

### Runtime integration

- explicit CLI selection through `paperagent serve --executor demo|real`;
- real-provider model/base-URL configuration without accepting secrets as CLI values;
- optional `--llm-price-table` loading;
- per-task provider, telemetry sink, and budget lifecycle;
- real literature runtime attached to the frozen graph;
- explicit `network_policy=allow_search` for real runs;
- graph call budget aligned with the provider physical-call budget;
- real invocation telemetry attached to task results and emitted as durable task events;
- provider and literature resources closed on success and failure;
- `/readyz` executor diagnostics without billable calls or secret disclosure;
- monetary budgets rejected at startup when the price table or configured model price is missing.

### Evaluation foundation

- versioned case, observation, result, and report schemas;
- JSONL corpus loading with duplicate case detection;
- stable SHA-256 corpus digest;
- deterministic required/forbidden-property grading;
- terminal, call-budget, and cost-budget checks;
- unknown cost cannot pass a budgeted evaluation;
- duplicate and unknown observations fail loudly;
- missing observations remain visible as failed/skipped cases;
- JSON report CLI;
- external holdout manifest and reproducible run-manifest JSON Schema;
- operator price-table example;
- four-case seed corpus covering in-domain, OOD, insufficient-evidence, and adversarial families.

### Validation infrastructure

- opt-in GitHub Actions workflow for live Mistral tests;
- live smoke tests for the four production schemas:
  - `ResearchPlan`;
  - `EvidenceSynthesis`;
  - `MethodProposal`;
  - `FinalReport`;
- deployment, evaluation, security, and live-test runbooks.

## Main files

```text
src/paperagent/providers/runtime.py
src/paperagent/providers/config.py
src/paperagent/providers/runtime_factory.py
src/paperagent/providers/mistral.py
src/paperagent/api/real_executor.py
src/paperagent/api/v05.py
src/paperagent/cli.py
src/paperagent/pricing.py
src/paperagent/evaluation.py
src/paperagent/eval_cli.py
src/paperagent/nodes/intake.py
evals/v0_6/
tests/providers/
tests/api/test_real_executor.py
tests/real_provider/test_mistral_smoke.py
tests/test_evaluation.py
tests/test_eval_cli.py
.github/workflows/v0.6-live-llm-smoke.yml
docs/v0.6/
```

## Key architecture decisions

1. The frozen v0.1 LangGraph topology and four consolidated structured LLM nodes remain unchanged.
2. Provider-specific request and response types terminate at the adapter boundary.
3. Every real task creates a new provider and budget so token, cost, and retry counters cannot leak
   across tasks.
4. Every physical retry or repair consumes the task call budget and receives a distinct invocation ID.
5. An ambiguous read timeout is not retried automatically because the provider may already have
   processed and billed the request.
6. The existing deterministic demo and Fake providers remain the credential-free regression baseline.
7. Monetary budgets are fail-closed: they require a selected price-table version and a price entry for
   the configured model.
8. Evaluation cost remains `unknown` when usage or pricing is unknown; it is never rewritten as zero.
9. Readiness verifies configuration only and intentionally does not make a billable model call.
10. Real-provider enablement does not add authentication, tenant isolation, quotas, billing, or public
    deployment approval.

## Automated verification

Verified implementation commit:

```text
df1aa39264ce504b0273d07d0d614716529f08e0
```

### Standard PaperAgent CI

```text
Run:                       29588147924
Python 3.11:               PASS
Python 3.12:               PASS
Install:                   PASS
Ruff lint:                 PASS
Ruff format:               PASS
Strict Mypy:               PASS
Offline tests/coverage:    PASS
Coverage artifacts:        PASS
```

### Complete v0.5.1 Release Hardening regression

```text
Run:                                      29588147843
Python 3.11 verification and wheel:       PASS
Python 3.12 verification and wheel:       PASS
Installed-wheel CLI/web smoke:            PASS
Chromium submit-progress-review-export:   PASS
Live OpenAlex/arXiv/Crossref/DataCite:     PASS
Docker build and readiness:               PASS
```

### Detailed offline diagnostics

```text
Run:                       29588147922
Ruff:                      PASS
Formatter:                 PASS (143 files)
Mypy:                      PASS (93 source files)
Pytest:                    PASS (211 passed, 6 skipped)
```

The six skipped tests are:

- one browser test in the lightweight diagnostic environment without Playwright;
- one explicitly opt-in real literature-provider test;
- four explicitly opt-in real Mistral production-schema tests.

The separate Release Hardening run executed and passed the Chromium test and live literature-provider
smoke.

Python 3.12 coverage artifact:

```text
Lines:                     3580 / 3765 = 95.09%
Branches:                  621 / 782 = 79.41%
Combined line/branch:      4201 / 4547 = 92.39%
Required gate:             >= 90%
```

## Real validation not executed

### Live Mistral production-schema smoke

`PENDING / NOT VERIFIED`

The test and workflow exist, but this development session did not configure a GitHub Actions
`MISTRAL_API_KEY` secret or dispatch a model-specific live run. Therefore none of the following is
claimed:

- real Mistral authentication success;
- live support for all four production JSON schemas;
- live schema-repair behavior;
- real usage/token metadata correctness;
- real provider rate-limit behavior;
- real provider latency or cost;
- absence of upstream schema drift.

### Real Mistral vertical workflow

`PENDING / NOT VERIFIED`

No real Mistral-backed submit → progress → retrieval → synthesis → method → report → review → export
run was executed. The successful Chromium vertical smoke used the deterministic demo executor.

### Scientific evaluation

`PENDING / NOT VERIFIED`

- the committed corpus contains four seed cases, not the required 48 development cases;
- the external holdout digest is not frozen;
- no real-model case observations exist;
- no blinded human grading was performed;
- no scientific correctness, citation-grounding, OOD robustness, safety-rate, cost, or latency release
  threshold is claimed.

## Known limitations

- only Mistral is implemented; there is no multi-provider router or fallback;
- the task runner remains single-process and SQLite-backed;
- real provider telemetry is returned with the task result rather than persisted in a dedicated
  analytics store;
- the real executor uses the current v0.2 literature-provider stack and does not add PDF/full-text RAG;
- cancellation cannot forcibly terminate an already executing HTTP request;
- automatic replay after process death remains intentionally fail closed;
- there is no authentication, account model, tenancy, quota, billing, or public-internet hardening;
- the price table is operator-supplied and must be updated from current official pricing before cost
  claims;
- human scientific evaluation tooling is only a data-contract foundation, not a completed study.

## Exact next steps

### 1. Execute the live Mistral schema smoke

Configure the repository secret:

```text
MISTRAL_API_KEY
```

Dispatch:

```text
Workflow: PaperAgent v0.6 Live LLM Smoke
Input:    model=<explicit supported Mistral model identifier>
```

Expected success:

- four parametrized tests pass;
- each production schema validates without weakening Pydantic contracts;
- no API key, authorization header, raw provider payload, or chain-of-thought appears in logs.

On failure, return:

- workflow run URL;
- model identifier;
- failed schema/task;
- redacted traceback;
- HTTP status class and typed provider error;
- no API key.

### 2. Add a controlled real vertical smoke

After the schema smoke passes, add a separately marked run that submits one bounded research request
through the real executor and verifies terminal progress, accepted evidence references, review, and
export. Preserve all provider calls, usage, retry, cost, and failure evidence.

### 3. Complete the evaluation corpus

- expand the four-case seed to at least 48 development cases;
- attach evidence provenance and deterministic grading rules;
- freeze the external holdout version and digest;
- run the full and required ablation arms;
- collect per-case cost, latency, citation, and failure records;
- perform blinded human scientific review and adjudication;
- evaluate the thresholds in `EXECUTION_PLAN.md` without changing them after viewing final holdout
  results solely to obtain a pass.

### 4. Make the release decision

Mark v0.6 complete only after live Mistral, real vertical, evaluation, and human-review evidence pass.
Otherwise keep the release state `PARTIAL`, `BLOCKED`, or `NOT VERIFIED`.

## Recommended verification commands

```bash
python -m pip install -e '.[dev,release]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
python -m build --wheel
python -m paperagent.eval_cli \
  --cases evals/v0_6/cases.jsonl \
  --observations evals/v0_6/example_observations.jsonl \
  --output artifacts/v0_6/evaluation-report.json
```

## Final state

`PARTIAL COMPLETE / BLOCKED ON CREDENTIALLED MISTRAL AND HUMAN SCIENTIFIC VALIDATION`

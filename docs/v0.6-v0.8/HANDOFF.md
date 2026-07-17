# PaperAgent v0.6-v0.8 MVP Handoff

## 1. Repository and branch

```text
Repository:                ZyfNO2/PaperAgent
Target branch:             master
Development branch:        feat/v0.6-v0.8-mvp-plugins
Draft PR:                  #14
Master base:               b01dbfa86de345b3d468240cc1b5a478c8cb0746
Final verified code SHA:   ad31be15f1e741c3e9f989cfb26331ddb46f4d2b
Merge state:               NOT MERGED
```

The branch remains a Draft PR. No automatic merge, master update, branch deletion, or ready-for-review transition was performed.

A temporary conflict-detection PR (#15) was closed without merging. The final branch was rebuilt with the current `master` commit as its parent so that v0.5.1 acceptance fixes and later OpenAI-compatible test assets were not overwritten.

## 2. Final status

| Version | Status | Meaning |
|---|---|---|
| v0.6 | `OFFLINE MVP COMPLETE / LIVE AND SCIENTIFIC QUALITY NOT VERIFIED` | Provider/runtime/evaluation engineering is implemented and offline gates pass; credentialed Mistral and holdout/human evaluation remain pending |
| v0.7 | `OFFLINE MVP COMPLETE` | Controlled local plugin runtime, CLI, packaging smoke, and security boundary pass |
| v0.8 | `OFFLINE MVP COMPLETE` | Deterministic academic method-tailoring plugin, examples, verdict policy, and installed-wheel smoke pass |

The official package version remains `0.5.1` until a separate release decision is made. This branch implements later version contracts but does not claim that v0.6, v0.7, or v0.8 has been released to `master`.

## 3. Completed work

### v0.6 — Real LLM and evaluation MVP

- provider-neutral runtime configuration with explicit environment/CLI precedence;
- typed provider failures, retry classification, usage representation, redaction, telemetry, pricing, and task budgets;
- Mistral structured-output adapter behind the frozen `LLMProvider` contract;
- strict schema validation and bounded repair/retry behavior;
- explicit `demo` versus `real` executor selection and readiness diagnostics;
- real-executor integration through the existing task, persistence, cancellation, review, and export paths;
- deterministic evaluation loader, manifest, grading, reporting, and CLI foundation;
- 48 committed development cases:
  - 12 in-domain;
  - 12 OOD;
  - 12 insufficient-evidence;
  - 12 adversarial;
- opt-in live Mistral workflow and schema smoke tests;
- existing v0.5.1 OpenAI-compatible smoke/E2E assets preserved during integration.

### v0.7 — Controlled local plugin runtime MVP

- strict `PluginManifest`, `PluginRequest`, `PluginResult`, capability, protocol, and error contracts;
- deterministic built-in registry and exact-name resolution;
- Python `paperagent.plugins` entry-point discovery;
- external entry points disabled by default and loaded only through exact command-local authorization;
- duplicate, incompatible, malformed, missing, load-failure, invocation-failure, unsupported-operation, and inconsistent-result handling;
- canonical request identifiers and JSON-compatible request/result validation;
- atomic UTF-8 JSON output and explicit overwrite refusal;
- `paperagent plugins list`;
- `paperagent plugins inspect <name>`;
- `paperagent plugins run <name> --operation ... --input ... --output ...`;
- deterministic `echo-contract` built-in plugin;
- plugin authoring and trust-boundary guide;
- installed-wheel plugin listing and invocation release smoke.

### v0.8 — Academic method-tailoring plugin MVP

- strict schemas for:
  - research contract;
  - baseline card;
  - falsifiable hypothesis;
  - module card;
  - experiment arm;
  - evidence ledger;
  - audit checks and report;
- deterministic gates for:
  - baseline source/version/license/data/environment/seed completeness;
  - reproduction evidence and compute fit;
  - verified baseline/module provenance;
  - falsifiable condition/limitation/mechanism/intervention/metric/guardrail;
  - semantic module compatibility rather than shape-only compatibility;
  - baseline/full/single-module/leave-one-out arm coverage;
  - consistent split/preprocessing/tuning/metrics/seeds/uncertainty/resources/stopping criteria;
  - explicit project stop conditions;
- `GO`, `REVISE`, and `NO_GO` verdicts;
- `verified`, `inferred`, `proposed`, and `unknown` status vocabulary;
- deterministic implementation sequence, risk list, experiment matrix, and method-section outline;
- `academic-method-tailoring` operations:
  - `audit`;
  - `template`;
- committed examples:
  - `examples/v0_8/go-plan.json`;
  - `examples/v0_8/revise-plan.json`;
  - `examples/v0_8/no-go-plan.json`;
  - `examples/v0_8/expected-verdicts.json`.

## 4. Main modified and added files

### Documentation

- `docs/ROADMAP_V0_6_V0_8.md`
- `docs/v0.6/EXECUTION_PLAN.md`
- `docs/v0.6/MVP_DELIVERY_CONTRACT.md`
- `docs/v0.6/DEVELOPMENT_STATUS.md`
- `docs/v0.7/EXECUTION_PLAN.md`
- `docs/v0.7/DEVELOPMENT_STATUS.md`
- `docs/v0.7/PLUGIN_AUTHORING.md`
- `docs/v0.8/EXECUTION_PLAN.md`
- `docs/v0.8/DEVELOPMENT_STATUS.md`
- `docs/v0.6-v0.8/HANDOFF.md`

### v0.6 provider/runtime/evaluation

- `src/paperagent/providers/config.py`
- `src/paperagent/providers/runtime.py`
- `src/paperagent/providers/runtime_factory.py`
- `src/paperagent/providers/mistral.py`
- `src/paperagent/pricing.py`
- `src/paperagent/telemetry/`
- `src/paperagent/api/real_executor.py`
- `src/paperagent/evaluation.py`
- `src/paperagent/eval_cli.py`
- `evals/v0_6/cases.jsonl`
- `.github/workflows/v0.6-live-llm.yml`

### v0.7-v0.8 plugins

- `src/paperagent/plugins/contracts.py`
- `src/paperagent/plugins/registry.py`
- `src/paperagent/plugins/echo.py`
- `src/paperagent/plugins/cli.py`
- `src/paperagent/plugins/academic_method.py`
- `src/paperagent/plugins/__init__.py`
- `examples/v0_8/`
- `tests/plugins/`
- `tests/test_plugin_cli.py`

### Integration and release gates

- `src/paperagent/cli.py`
- `src/paperagent/providers/__init__.py`
- `.env.example`
- `.github/workflows/v0.5.1-release-hardening.yml`
- `README.md`

## 5. Key architecture decisions

1. **No graph expansion for plugins.** v0.7 plugins are explicit local utility invocations and cannot inject LangGraph nodes or mutate workflow state.
2. **No automatic third-party loading.** Entry-point discovery requires an exact operator allow-list for each command.
3. **Authorization is not sandboxing.** An explicitly authorized external entry point executes installed Python code in-process. This limitation is documented rather than hidden.
4. **No plugin HTTP surface.** The unauthenticated local API does not expose plugin invocation.
5. **No secret transport through plugin payloads.** The plugin host provides no provider keys, raw provider objects, graph state, SQLite handles, or shell capability.
6. **v0.8 is deterministic.** The academic method plugin performs no LLM or network call and does not invent literature, experiments, results, or novelty claims.
7. **Composition is not novelty.** `GO` requires verified provenance, a reproduced baseline, semantic integration contracts, a falsifiable hypothesis, and fair comparison/ablation structure.
8. **v0.6 evidence classes remain separated.** Offline/Fake evidence, real literature-provider smoke, browser smoke, real LLM evidence, and human scientific review are never conflated.
9. **Historical changes were integrated without overwriting master.** The final feature tree preserves later v0.5.1 acceptance fixes and OpenAI-compatible E2E/real-LLM tests.

## 6. Automated verification

### Final verified code commit

```text
SHA: ad31be15f1e741c3e9f989cfb26331ddb46f4d2b
```

### PaperAgent CI

```text
Run:        29615492804
Conclusion: SUCCESS
Python:     3.11 and 3.12
Passed:     Ruff lint, Ruff format, strict Mypy, tests, coverage
```

### Release Hardening

```text
Run:        29615492807
Conclusion: SUCCESS
```

Passed jobs:

- Python 3.11 offline verification and wheel build;
- Python 3.12 offline verification and wheel build;
- installed wheel, CLI, plugin, and packaged-web smoke;
- Chromium submit → progress → review → export vertical smoke;
- live OpenAlex, arXiv, Crossref, and DataCite smoke;
- Docker image build and readiness smoke.

### Detailed test evidence

The last detailed diagnostic before the three committed example-case checks reported:

```text
258 passed
11 skipped
0 failed
Combined line/branch coverage: 90.34%
Mypy: no issues in 101 source files
Ruff lint: passed
Ruff format: passed
```

The three committed v0.8 example-case checks were then added. Both Python CI jobs passed on the final verified code commit.

## 7. Explicitly unverified or pending

### Real Mistral

`NOT VERIFIED` in this handoff:

- live Mistral outputs for all four production schemas;
- three consecutive complete real Mistral vertical runs;
- provider-specific rate-limit and thinking-only behavior against the selected live model;
- real token/cost/latency distribution.

Reason: the repository requires a GitHub Actions `MISTRAL_API_KEY` secret and an explicit model selection. The secret was not committed, copied into logs, or injected through task/plugin payloads.

### Scientific quality

`NOT VERIFIED`:

- external holdout task success;
- blinded human scientific review;
- non-adversarial/OOD release thresholds;
- real claim-to-evidence precision;
- real accepted-citation validity across the release evaluation;
- real safety/adversarial rates.

The committed 48 cases are a development corpus, not an unbiased external holdout.

### External plugins

Not verified against a separately packaged third-party plugin distribution. The host contract, explicit authorization, failure injection, and installed built-in plugin behavior are verified offline.

## 8. Known limitations

- package metadata still reports `0.5.1`; later version contracts are implemented on a Draft feature branch, not released;
- no authentication, accounts, tenant isolation, quotas, billing, or public deployment approval;
- external plugins are trusted installed Python code and are not sandboxed;
- no plugin installation, signature verification, update service, or marketplace;
- no plugin graph-node injection, background execution, shell host, or HTTP API;
- no PDF parsing, OCR, embeddings, vector database, or full-text RAG;
- the academic method plugin validates supplied structure but cannot establish true novelty or experimental effectiveness;
- no automatic literature retrieval or external identifier verification inside v0.8;
- no experiment execution, code modification, paper modification, or external write action.

## 9. Exact takeover steps

### Review the branch

```bash
git fetch origin
git checkout feat/v0.6-v0.8-mvp-plugins
git status
git log --oneline --decorate -20
```

### Run offline gates

```bash
python -m pip install -e '.[dev,release]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest -q --cov=paperagent --cov-branch --cov-report=term-missing
python -m build --wheel
```

### Exercise plugins

```bash
paperagent plugins list
paperagent plugins inspect academic-method-tailoring
paperagent plugins run academic-method-tailoring \
  --operation audit \
  --input examples/v0_8/go-plan.json \
  --output /tmp/method-audit.json
```

Expected result for the committed example is `GO`.

### Execute live Mistral smoke

1. Add the repository Actions secret `MISTRAL_API_KEY` through GitHub settings.
2. Select a supported Mistral model identifier.
3. Manually dispatch `.github/workflows/v0.6-live-llm.yml` and supply the model input.
4. Confirm all four schema cases pass.
5. Inspect artifacts and logs for secret, raw response, or chain-of-thought leakage.

Local equivalent:

```bash
export MISTRAL_API_KEY='<set outside the repository>'
export PAPERAGENT_RUN_REAL_LLM=1
export PAPERAGENT_MISTRAL_MODEL='<supported-model-id>'
pytest -q -m 'real_provider and network' tests/real_provider/test_mistral_smoke.py
```

Do not paste the secret into source files, task JSON, plugin input, command history intended for publication, logs, SQLite, or exported artifacts.

### Complete scientific evaluation

1. Freeze an external holdout version and digest before observing final results.
2. Collect real v0.6 observations and case-level telemetry.
3. Run deterministic graders.
4. Conduct blinded human review.
5. Preserve all failures and threshold dispositions.
6. Mark v0.6 release-complete only when the real-provider and scientific-quality gates pass.

## 10. Final decision

```text
v0.6: PARTIAL — offline MVP complete; live Mistral and scientific quality blocked on external verification
v0.7: COMPLETE — offline plugin runtime MVP complete
v0.8: COMPLETE — offline academic method plugin MVP complete
Overall branch: PARTIAL / READY FOR CODE REVIEW, NOT READY FOR RELEASE MERGE
```

The Draft PR should remain unmerged until the maintainer reviews the combined scope and decides whether v0.6 live/scientific verification is required before merging the plugin MVPs or should remain a documented post-merge release gate.

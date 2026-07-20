# Academic Method Holdout v2

This branch is an isolated benchmark-authoring workspace for evaluating evidence-backed academic method design without reusing the contaminated 20-case development benchmark.

## Contents

- `docs/BENCHMARK_PROTOCOL.md` — frozen design, scoring, leakage controls, and release rules.
- `schema/case.schema.json` — machine-readable case contract.
- `data/public-dev-v2.jsonl` — 12 public development cases. These are **not** generalization evidence.
- `private/README.md` — rules for authoring and sealing the 32-case private holdout.
- `scripts/validate_cases.py` — dependency-free structural and contamination validator.
- `scripts/run_public_dev.py` — input-only runner against an explicitly pinned PaperAgent production commit.
- `scripts/score_runs.py` — external structured scorer; oracle and metadata are read only after production execution.
- `scripts/scan_production.py` — external source/signature scan with optional sealed private n-gram manifest support.
- `tests/` — validator, runtime-boundary, scorer, and leakage-scanner regression tests.

## Runtime boundary

A runner may project only these fields into production execution:

```text
input.user_request
input.supplied_materials[].title
input.supplied_materials[].declared_role
input.declared_constraints
```

It must not pass `case_id`, `oracle`, `metadata`, scoring rules, or metamorphic-group identifiers to the model, retrieval service, production graph, or production prompts.

The production entry point used by this branch is `execute_benchmark_input`. Its signature deliberately excludes all scorer-only fields. `case_id` is attached only after graph execution when the external runner normalizes the returned state.

## Local validation

```bash
python scripts/validate_cases.py data/public-dev-v2.jsonl
python -m unittest discover -s tests -v
python scripts/scan_production.py ../PaperAgent \
  --output build/production-scan.json
```

## Public development run

The cloud workflow checks out a frozen production SHA separately, performs the external production scan, installs that exact commit, and then runs:

```bash
python scripts/run_public_dev.py \
  --cases data/public-dev-v2.jsonl \
  --output-dir build/public-dev-v2 \
  --max-cases 12 \
  --max-llm-calls 12 \
  --provider-call-budget 120 \
  --llm-provider mistral \
  --llm-model mistral-small-latest \
  --require-thresholds
```

Generated runtime-input records contain only the four allowed input partitions. States and normalized traces are saved before the scorer reads `oracle`, `metadata`, and `case_id` for external bookkeeping.

## Result interpretation

The public set is intentionally inspectable and may be used for runner, scorer, and production debugging. Every result from it must be labeled:

```text
public development set; not independent generalization evidence
```

The private holdout must be generated and sealed only after the evaluated production commit, external scorer, thresholds, and leakage scan are frozen. Any result-informed production or scorer change permanently downgrades an exposed private set to development data.

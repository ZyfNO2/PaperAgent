# Academic Method Holdout v2

This branch is an isolated benchmark-authoring workspace for evaluating evidence-backed academic method design without reusing the contaminated 20-case development benchmark.

## Contents

- `docs/BENCHMARK_PROTOCOL.md` — frozen design, scoring, leakage controls, and release rules.
- `schema/case.schema.json` — machine-readable case contract.
- `data/public-dev-v2.jsonl` — 12 public development cases. These are **not** generalization evidence.
- `private/README.md` — rules for authoring and sealing the 32-case private holdout.
- `scripts/validate_cases.py` — dependency-free structural and contamination validator.
- `tests/test_validate_cases.py` — validator regression tests.

## Runtime boundary

A runner may project only these fields into production execution:

```text
input.user_request
input.supplied_materials[].title
input.supplied_materials[].declared_role
input.declared_constraints
```

It must not pass `case_id`, `oracle`, `metadata`, scoring rules, or metamorphic-group identifiers to the model, retrieval service, production graph, or production prompts.

## Local validation

```bash
python scripts/validate_cases.py data/public-dev-v2.jsonl
python -m unittest discover -s tests -v
```

## Status

The public set is intentionally inspectable and may be used for implementation debugging. The private holdout must be generated and sealed only after the evaluated production commit and scorer are frozen.

# PaperAgent v0.6 Evaluation Harness Runbook

## Development report

Build a deterministic report from the 48-case development corpus and observed run properties:

```bash
python -m paperagent.eval_cli \
  --cases evals/v0_6/cases.jsonl \
  --observations evals/v0_6/example_observations.jsonl \
  --output artifacts/v0_6/evaluation-report.json
```

This report validates the evaluation contract and recorded observations. It does not pass scientific
acceptance by itself.

## Frozen holdout preflight

Before any holdout execution:

1. verify `evals/v0_6/holdout_cases.v1.jsonl` has exactly 16 cases;
2. verify the 4/4/4/4 category distribution;
3. verify the exact UTF-8 SHA-256 digest against `holdout_manifest.json`;
4. record the clean repository SHA, provider/model, price table, environment, and UTC time;
5. confirm no scientific prompt/rule file changed after the manifest cutoff;
6. anonymize output arm identity before expert review.

Run the repository validation test:

```bash
pytest -q tests/evals/test_holdout_manifest.py
```

## Scientific acceptance

Follow `docs/acceptance/GATE_L_SCIENTIFIC_ACCEPTANCE.md`.

The holdout must be executed with the real provider under the declared budgets. Every output requires
immutable artifacts, source-identifier verification, and blinded review by at least two independent
reviewers. Cohen's kappa, score dispersion, false-GO, unsupported-claim, citation-mismatch, repair, and
per-category acceptance thresholds must be reported before adjudication.

A frozen corpus without real execution and human review remains `INCOMPLETE`, not PASS.

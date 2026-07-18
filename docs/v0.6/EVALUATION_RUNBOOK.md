# PaperAgent v0.6 Evaluation Harness Runbook

Build a deterministic report from a case corpus and observed run properties:

```bash
python -m paperagent.eval_cli \
  --cases evals/v0_6/cases.jsonl \
  --observations evals/v0_6/example_observations.jsonl \
  --output artifacts/v0_6/evaluation-report.json
```

The seed corpus is not a release-quality evaluation. Expand it to the required 48 development cases,
freeze the external holdout digest, collect real execution observations, and complete blinded human
scientific review before a v0.6 quality claim.

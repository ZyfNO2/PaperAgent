# PaperClaw Academic Tailoring Gold Benchmark v1 — PaperAgent Snapshot

This directory is a read-only snapshot of the dataset published in
`ZyfNO2/PaperClaw` at commit
`60a577a3d8d6701a8d212604572e846cc8a41e2f`.

PaperClaw is only the upstream data source. All evaluator, runner, test, CI, and
report implementation in this work lives in PaperAgent.

## Snapshot contents

- `cases-01.jsonl` through `cases-04.jsonl`: 20 gold cases.
- `trace-profile.json`: the canonical ten-stage research trace and seven global
  hard failures.
- `source.json`: source repository, source commit, upstream Git blob SHAs, and
  read-only import policy.

The PaperAgent loader recomputes the Git blob SHA of every imported file and
fails closed when any local snapshot byte diverges from the pinned PaperClaw
blob.

## What the benchmark measures

The benchmark evaluates structured research behavior rather than final prose:

1. sparse-input parsing and unknown tracking;
2. baseline, gap, parallel-method, strong-comparison, and risk retrieval;
3. identity, relevance, and claim-role review;
4. bounded clarification;
5. reproducible baseline freeze;
6. falsifiable hypothesis construction;
7. semantic module compatibility;
8. minimal causal stitching;
9. fair experiment and ablation design;
10. `GO`, `REVISE`, `REVISE_TO_PILOT`, or `NO_GO` with recovery actions.

## Runner

Evaluator self-check:

```bash
python scripts/run_claw_academic_benchmark.py --require-pass
```

Score a normalized PaperAgent run JSONL:

```bash
python scripts/run_claw_academic_benchmark.py \
  --runs build/paperagent-claw-run.jsonl \
  --output build/claw-academic-tailoring-report.json \
  --require-pass
```

The self-check proves dataset and evaluator consistency only. It does not prove
that a real PaperAgent LLM/retrieval run passes the benchmark. Candidate-run
claims require a separately captured run JSONL produced without gold-field
leakage.

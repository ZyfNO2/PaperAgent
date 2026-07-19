# PaperClaw Academic Tailoring Benchmark — PaperAgent Handoff

## Status

**ENGINEERING IMPLEMENTATION COMPLETE — read-only dataset import, evaluator, real-state normalization, and cloud CI are complete.**

A real LLM plus live-retrieval run across all 20 cases has not been executed and must not be represented as completed.

## Repository boundary

- Upstream dataset source: `ZyfNO2/PaperClaw`
- Upstream branch: `main`
- Upstream commit: `60a577a3d8d6701a8d212604572e846cc8a41e2f`
- Upstream path: `evals/academic_tailoring_v1`
- Development repository: `ZyfNO2/PaperAgent`
- Development branch: `feat/claw-academic-tailoring-benchmark-v1`
- Stacked base: `fix/evidence-ledger-final-outcome-trace-exact`
- Draft PR: `#31`
- Verified implementation SHA before this Handoff: `53a1aad97acf8ee81583355aa91861563d68a9e8`

PaperClaw was used as a read-only data source. This work did not create a PaperClaw branch, commit, pull request, or file modification.

## Imported dataset

PaperAgent contains an exact snapshot of:

- `cases-01.jsonl`
- `cases-02.jsonl`
- `cases-03.jsonl`
- `cases-04.jsonl`
- `trace-profile.json`

The source manifest records the upstream commit and Git blob SHA for every file. The loader recomputes Git blob identity and fails closed if a local snapshot byte changes without an explicit source update.

Imported blob identities:

| File | PaperClaw blob SHA |
|---|---|
| `cases-01.jsonl` | `ff93fb9e580ee285ac8ab91d1a3542ccb490f6cc` |
| `cases-02.jsonl` | `dfb8a4bf22d9a38ad5ec3fc241ad6393c82b5e4d` |
| `cases-03.jsonl` | `776d881a919e3a4fa6556e8cfa52a1adf12f3432` |
| `cases-04.jsonl` | `cc16104d4d66c823080572773f2cb547b5da3d7d` |
| `trace-profile.json` | `db65e8215d37793a5378e3c5a797c2d3bfa6da87` |

Dataset digest:

`9311285d569e95f7c6cf5aaf2bf21a32269c0a58dd35bc529411b2abd6310eeb`

## Delivered implementation

### Benchmark contracts and scoring

- Typed 20-case dataset and shared trace-profile contracts.
- Canonical ten-stage run trace:
  1. input parsing;
  2. exploratory retrieval;
  3. relevance review;
  4. clarification gate;
  5. baseline freeze;
  6. falsifiable hypothesis;
  7. module compatibility;
  8. minimal stitch;
  9. experiment matrix;
  10. final decision.
- Stage-weighted scoring with server-derived totals.
- Explicit `REVISE + pilot_recommended` mapping to `REVISE_TO_PILOT`.
- Per-tag and per-case aggregate reporting.
- Digest-protected aggregate report.

### Hard failures

The evaluator fails closed for:

- fabricated papers, identifiers, results, code availability, or reproduced metrics;
- identity verification treated as research relevance;
- incompatible supplied material forced into the plan;
- novelty claimed from module composition alone;
- future/test leakage or unfair comparison;
- hidden stronger baselines or negative results;
- GO without a reproducible baseline and falsifiable hypothesis;
- PaperAgent Trace contract failure.

### Real PaperAgent state normalization

`normalize_paperagent_state` converts a serialized `PaperAgentState` into the benchmark run-trace contract without reading the Gold Case fields.

It derives available information from:

- `ResearchPlan` and search gaps;
- `EvidenceBundle`, `RelevanceAssessment`, and `EvidenceLedger`;
- canonical methodology baseline, hypothesis, modules, and experiments;
- `FinalOutcome`, `FinalReport`, and `TraceAuditResult`.

Missing baseline reproduction, full-text review, semantic contracts, strong comparisons, or trace facts remain missing and reduce the score. The adapter does not invent them.

The normalization CLI accepts state JSONL plus independent context JSONL and emits candidate-run JSONL for the benchmark runner.

### Runner and CI

- `scripts/normalize_claw_benchmark_states.py`
- `scripts/run_claw_academic_benchmark.py`
- `.github/workflows/claw-academic-tailoring-benchmark.yml`

The benchmark workflow runs on Python 3.11 and 3.12 and preserves Ruff, format, Mypy, pytest, self-check, and report artifacts.

## Verified results

Results are bound to code SHA:

`53a1aad97acf8ee81583355aa91861563d68a9e8`

### PaperClaw Academic Tailoring Benchmark

- Workflow run: `29701568626`
- Conclusion: success
- Python 3.11: success
- Python 3.12: success
- Ruff: pass
- Ruff format: pass
- Strict Mypy: pass over 117 source files
- Focused benchmark and adapter tests: 12 passed
- Evaluator self-check: 20 passed, 0 failed
- Average self-check score: 100.0
- Decision accuracy: 1.0
- Hard failures: 0
- Self-check report digest: `d82b9bdee650297968f65fcce4b32302a7fe09f2c74a0973d88262b5813b47aa`

Artifacts:

- Python 3.11 artifact ID: `8446599418`
- Python 3.11 artifact digest: `sha256:1b80fb3722d8963e9f7a584d1cdb8583a2a70b566dba3acecc20f4186d7eee5a`
- Python 3.12 artifact ID: `8446600297`
- Python 3.12 artifact digest: `sha256:db4575ead133cc4f9e6a3a4ffcf3a982984d8b4307a8241f97bcfa9867935564`

The 20/20 result is an evaluator self-check built from the Gold records. It proves dataset/evaluator consistency; it is not a claim that a real PaperAgent model run achieved 20/20.

### Existing PaperAgent gates

- Academic Tailoring Agent Evaluation run `29701568628`: success
- PaperAgent Interview Evidence run `29701568624`: success

## Main files

### Data

- `evals/claw_academic_tailoring_v1/source.json`
- `evals/claw_academic_tailoring_v1/cases-01.jsonl`
- `evals/claw_academic_tailoring_v1/cases-02.jsonl`
- `evals/claw_academic_tailoring_v1/cases-03.jsonl`
- `evals/claw_academic_tailoring_v1/cases-04.jsonl`
- `evals/claw_academic_tailoring_v1/trace-profile.json`
- `evals/claw_academic_tailoring_v1/README.md`

### Implementation

- `src/paperagent/claw_academic_benchmark.py`
- `src/paperagent/claw_benchmark_adapter.py`
- `scripts/normalize_claw_benchmark_states.py`
- `scripts/run_claw_academic_benchmark.py`

### Tests and CI

- `tests/evals/test_claw_academic_benchmark.py`
- `tests/evals/test_claw_benchmark_adapter.py`
- `.github/workflows/claw-academic-tailoring-benchmark.yml`

## Usage

Evaluator self-check:

```bash
python scripts/run_claw_academic_benchmark.py --require-pass
```

Normalize real PaperAgent states:

```bash
python scripts/normalize_claw_benchmark_states.py \
  --states build/paperagent-states.jsonl \
  --contexts build/claw-normalization-contexts.jsonl \
  --output build/paperagent-claw-runs.jsonl
```

Score normalized real runs:

```bash
python scripts/run_claw_academic_benchmark.py \
  --runs build/paperagent-claw-runs.jsonl \
  --output build/claw-academic-tailoring-report.json \
  --require-pass
```

## Not executed / not verified

- real LLM execution across all 20 cases;
- live retrieval and full-text review across all 20 cases;
- simulated clarification replies for every case;
- human semantic adjudication of equivalent methods;
- real-corpus retrieval Precision/Recall;
- baseline reproduction or empirical experiments;
- a frozen unseen post-development holdout;
- independent scientific review.

## Next development step

Run the 20 cases through the actual PaperAgent graph with a bounded real LLM and live retrieval configuration. Capture only the run states and gold-independent normalization contexts, normalize them, and score the resulting traces. Keep the Gold records inaccessible to the model and retrieval path during candidate execution.

## Final classification

- PaperClaw modification: **none**
- Read-only dataset import: **complete**
- Snapshot integrity validation: **complete**
- Benchmark evaluator: **complete**
- Real PaperAgent state adapter: **complete**
- Cloud CI: **complete**
- Real 20-case LLM/retrieval run: **pending**
- Overall: **ENGINEERING COMPLETE / REAL BENCHMARK EXECUTION PENDING**

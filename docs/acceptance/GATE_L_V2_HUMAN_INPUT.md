# Gate L v2 human-input checkpoint

## Current state

Engineering scaffolding is implemented for Gate L v2, but final scientific acceptance is intentionally blocked until independent inputs are supplied.

Scientific behavior cutoff used by the v2 tooling:

```text
d4fef014932d084a0addd4a588b3431d2c08628b
planning.v0.1.2
```

Do not change planning prompts, scientific routing, retrieval policy, quality-gate semantics, deterministic graders, or case-specific behavior after authoring/freeze. Any such change requires a new holdout version.

## Input A — independently authored unseen holdout v2

Create exactly 16 JSONL records:

- 4 `in_domain`
- 4 `ood`
- 4 `insufficient_evidence`
- 4 `adversarial`

Each record must contain:

```json
{
  "case_id": "holdout-v2-...",
  "version": "v2",
  "category": "in_domain",
  "title": "...",
  "task_input": "...",
  "expected_terminal": "succeeded",
  "allowed_constraints": ["..."],
  "acceptance_tags": ["..."],
  "required_evidence_properties": ["..."],
  "forbidden_evidence_properties": ["..."],
  "budget": {
    "max_calls": 8,
    "max_total_tokens": 16000,
    "max_wall_seconds": 180,
    "max_cost_usd": 2.0
  },
  "deterministic_checks": [
    {
      "check_id": "terminal",
      "kind": "terminal",
      "target": "terminal",
      "expected": "succeeded"
    },
    {
      "check_id": "budget",
      "kind": "budget",
      "target": "calls_tokens_time_cost",
      "expected": "within_limits"
    }
  ],
  "human_scoring_rubric": [
    {
      "criterion": "scientific_correctness",
      "weight": 25,
      "full_credit": "...",
      "zero_credit": "..."
    },
    {
      "criterion": "claim_evidence_alignment",
      "weight": 25,
      "full_credit": "...",
      "zero_credit": "..."
    },
    {
      "criterion": "methodological_rigor",
      "weight": 20,
      "full_credit": "...",
      "zero_credit": "..."
    },
    {
      "criterion": "calibration_and_limits",
      "weight": 15,
      "full_credit": "...",
      "zero_credit": "..."
    },
    {
      "criterion": "actionability",
      "weight": 15,
      "full_credit": "...",
      "zero_credit": "..."
    }
  ],
  "reference_evidence": [
    {
      "claim_scope": "...",
      "source_type": "journal_article",
      "stable_identifier": "...",
      "title": "..."
    }
  ]
}
```

Allowed `expected_terminal` values are `succeeded`, `blocked`, `failed`, and `need_human`.

Do not derive the 16 final cases by merely paraphrasing v1. Do not use the final cases to tune prompts, retrieval, routing, graders, thresholds, or repair behavior.

Validate before freeze:

```bash
python scripts/gate_l_v2_acceptance.py validate \
  --cases evals/v0_6/holdout_cases.v2.jsonl
```

## Input B — independence attestation

Copy:

```text
evals/v0_6/gate_l_v2_author_attestation.template.json
```

Fill `author_or_owner` and confirm both booleans truthfully. The freeze tool rejects missing independence/tuning attestations.

Freeze only after explicit approval:

```bash
python scripts/gate_l_v2_acceptance.py freeze \
  --cases evals/v0_6/holdout_cases.v2.jsonl \
  --manifest-out evals/v0_6/holdout_manifest.v2.json \
  --attestation evals/v0_6/gate_l_v2_author_attestation.json
```

Then verify immutability:

```bash
python scripts/gate_l_v2_acceptance.py verify \
  --manifest evals/v0_6/holdout_manifest.v2.json
```

## Real-provider execution

After freeze, use the guarded manual workflow:

```text
.github/workflows/gate-l-v2-formal.yml
```

The workflow requires the explicit confirmation string:

```text
RUN_FROZEN_V2
```

It does not run automatically on push or pull request, so adding the infrastructure itself does not spend provider credits.

The formal runner:

```bash
python scripts/run_gate_l_v2.py \
  --manifest evals/v0_6/holdout_manifest.v2.json
```

A `--case-id` run is diagnostic-only and can never establish final Gate L acceptance.

## Input C — two independent blinded reviews

After real execution, generate the blinded package:

```bash
python scripts/gate_l_v2_acceptance.py blind \
  --manifest evals/v0_6/holdout_manifest.v2.json \
  --evidence-dir build/gate-l-v2-evidence/per-case \
  --output build/gate-l-v2-review.json
```

This creates:

- reviewer-visible randomized `arm-*` package;
- a separate private arm-to-case mapping.

Each reviewer independently fills a copy of:

```text
evals/v0_6/gate_l_v2_review.template.json
```

Review decisions are `GO`, `REVISE`, or `NO_GO`. Reviewers must not see provider/model identity, hidden expected terminal labels, another reviewer's score, or the private arm mapping before submission.

## Input D — deterministic audit and adjudication

Populate the deterministic summary from immutable execution/grader evidence using:

```text
evals/v0_6/gate_l_v2_deterministic_summary.template.json
```

Do not infer missing metrics. Unknown/missing token, price, output, trace, provenance, or zero-tolerance evidence remains fail-closed.

Any reviewer decision disagreement or critical-defect disagreement requires a recorded adjudication entry containing:

```json
{
  "arm_id": "arm-001",
  "resolved_decision": "GO",
  "resolved_critical_defect": false,
  "rationale": "..."
}
```

## Final scoring

```bash
python scripts/gate_l_v2_acceptance.py score \
  --manifest evals/v0_6/holdout_manifest.v2.json \
  --review-map build/gate-l-v2-review.mapping.json \
  --review-a reviewer-a.json \
  --review-b reviewer-b.json \
  --deterministic-summary deterministic-summary.json \
  --adjudication adjudication.json \
  --output gate-l-v2-decision.json
```

The scorer applies zero-tolerance gates before aggregate thresholds and computes pre-adjudication Cohen's kappa and reviewer score deltas.

## User acceptance checkpoint

The next action is not another prompt/rule change. Supply the independently authored v2 case file and attestation, then review the freeze digest before authorizing the paid real-provider run.

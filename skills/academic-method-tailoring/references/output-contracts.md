# Output contracts

## Contents

1. Design brief
2. Baseline card
3. Module card
4. Experiment matrix
5. JSON plan
6. Methodology outline

## 1. Design brief

```markdown
# Method design decision

Decision: GO | REVISE | NO-GO
Confidence: low | medium | high

## Research contract
- Problem:
- Context:
- Primary metric and guardrails:
- Constraints:
- Verified facts:
- Assumptions:

## Gap and hypothesis
- Evidence-backed gap:
- Proposed mechanism:
- Intervention:
- Prediction:
- Falsifier:

## Baseline and modules
| Component | Provenance | Role | Contract status | Reproducibility | License |

## Validation
| Experiment | Claim tested | Controls | Expected discriminating result |

## Risks and stop conditions
- Risk:
- Missing evidence:
- Stop or pivot when:
```

## 2. Baseline card

```markdown
### Baseline A
- Paper and identifier:
- Repository and commit:
- License:
- Task/dataset/split:
- Environment and checkpoint:
- Reported metric:
- Reproduced metric:
- Reproduction status: verified | partial | failed | unknown
- Selection rationale:
- Known deviations:
```

## 3. Module card

```markdown
### Module B
- Source and license:
- Original role:
- Proposed role:
- Gap addressed:
- Input contract: semantics, shape, dtype, scale, order, mask
- Output contract: semantics, shape, dtype, scale, order, mask
- Optimization: parameters, loss, gradient path, schedule
- Compute cost:
- Predicted effect:
- Competing explanation:
- Failure mode:
- Required tests:
```

## 4. Experiment matrix

Each row must identify the claim it can disprove.

```markdown
| ID | A | B | C | Matched control | Dataset/split | Seeds | Metrics | Claim tested | Pass/fail rule |
|---|---:|---:|---:|---|---|---:|---|---|---|
```

## 5. JSON plan

Use this contract with `scripts/validate_method_plan.py`:

```json
{
  "topic": "...",
  "problem": {
    "statement": "...",
    "evidence": ["primary-source-id"],
    "metric": "...",
    "guardrails": ["..."]
  },
  "baseline": {
    "name": "...",
    "source": "...",
    "version": "...",
    "license": "...",
    "reproducibility_status": "verified",
    "reproduced_metric": "..."
  },
  "modules": [
    {
      "name": "B",
      "source": "...",
      "license": "...",
      "role": "...",
      "input_contract": "...",
      "output_contract": "...",
      "hypothesis": "...",
      "failure_mode": "..."
    }
  ],
  "integration": {
    "dataflow": "A -> B -> output",
    "compatibility_checks": ["semantic", "shape", "dtype", "scale", "ordering", "mask", "gradient"],
    "loss": "...",
    "baseline_fallback": "..."
  },
  "experiments": {
    "datasets": ["..."],
    "metrics": ["..."],
    "comparisons": ["frozen baseline", "strong recent method"],
    "ablations": ["baseline", "B only", "full"],
    "seeds": 3,
    "stop_conditions": ["..."]
  },
  "claims": [
    {"claim": "...", "evidence": ["..."], "status": "proposed", "falsifier": "..."}
  ],
  "risks": ["..."],
  "decision": "REVISE"
}
```

## 6. Methodology outline

```markdown
## 3 Methodology
### 3.1 Problem formulation and notation
### 3.2 Overview and data flow
### 3.3 Reproduced baseline
### 3.4 Proposed module B
### 3.5 Proposed module C
### 3.6 Integration and optimization objective
### 3.7 Complexity and implementation details
```

Do not force this numbering when the actual data flow suggests a different decomposition. Each module section should state motivation, inputs, transformation, outputs, objective, and difference from its cited source.

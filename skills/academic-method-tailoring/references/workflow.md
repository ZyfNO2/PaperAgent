# Workflow and decision gates

## Contents

1. Intake
2. Evidence and baseline
3. Gap and hypothesis
4. Module selection
5. Integration
6. Implementation
7. Experiments
8. Writing and audit

## 1. Intake

Capture:

- research task and deployment or scientific context;
- target output and primary metric;
- dataset availability, split policy, and leakage risks;
- existing code, baseline runs, and inherited artifacts;
- compute, time, licensing, safety, and venue constraints;
- desired contribution and acceptable negative outcome.

Produce a one-paragraph research contract. Do not begin module selection until the problem and success criteria are concrete.

**Gate G0 — scope:** pass only when the target problem, measurable outcome, constraints, and academic-integrity boundaries are explicit.

## 2. Evidence and baseline

Create an evidence ledger with one row per claim or artifact:

| ID | Claim or artifact | Primary source | Verification | Relevance | Status |
|---|---|---|---|---|---|
| E1 | Baseline task definition | paper/official docs | section or test | high | verified |

For code, record repository, commit, license, environment, data instructions, checkpoints, open issues, and a reproduction result. A repository link alone is not reproducibility.

Score baseline candidates from 0–2 on:

- task and data match;
- runnable code and maintained dependencies;
- legal reuse and attribution clarity;
- compute feasibility;
- recognized comparison value;
- reproducible metric under the intended split.

Select the highest defensible candidate, not simply the easiest or weakest one. A composite baseline is allowed only when its components and changes are declared and a clean reference baseline remains available.

**Gate G1 — evidence:** every important statement has a verified primary source or is marked unknown.

**Gate G2 — baseline:** the unchanged path runs, or an accepted reimplementation exception documents why it does not.

## 3. Gap and hypothesis

Classify the gap without treating the label as proof:

- underexplored setting or population;
- known limitation or failure mode;
- overly broad assumption;
- inefficiency or resource bottleneck;
- unrealistic or idealized condition;
- missing mechanism analysis.

Use a Problem–Method–Insight formulation:

- **Problem:** a bounded, sourced limitation.
- **Method:** the minimum intervention that targets the proposed cause.
- **Insight:** what the experiment could teach even if the method loses.

Write a falsifier: “The hypothesis is weakened if …”. If no plausible result could disconfirm the claim, rewrite it.

**Gate G3 — hypothesis:** pass only when the causal or mechanistic prediction, measurable outcome, guardrail, and falsifier are explicit.

## 4. Module selection

Use one module card per candidate:

| Field | Requirement |
|---|---|
| Source | Paper/repository, version, license |
| Original role | What it did in the source system |
| Proposed role | What limitation it addresses here |
| Contract | Input/output meaning, shape, dtype, scale, masks, ordering |
| Optimization | Trainable parameters, loss, gradient path, schedule |
| Cost | Parameters, FLOPs/latency/memory where relevant |
| Prediction | Expected metric and failure-mode change |
| Risks | Domain shift, redundancy, instability, leakage |

Reject modules chosen only because they are popular, easy to paste, or shape-compatible. If two modules are redundant, prefer the simpler design until interaction evidence justifies both.

## 5. Integration

Build a compatibility matrix:

| Boundary | Producer | Consumer | Shape | Semantic unit | Scale | Order/mask | Gradient | Check |
|---|---|---|---|---|---|---|---|---|

Then define:

- data-flow DAG;
- exact insertion points;
- adapters and why each is required;
- total objective and coefficient rationale;
- training stages and frozen/unfrozen components;
- fallback path with all additions disabled;
- expected failure signatures.

**Gate G4 — integration:** pass when every boundary has a semantic contract and a test. Shape-only compatibility fails this gate.

## 6. Implementation

Preserve backward compatibility. Add configuration flags and implement one independently testable change at a time. Prefer tests near each interface:

- deterministic tensor fixtures;
- assertions on shape, dtype, range, ordering, and masks;
- gradient presence and finite-loss checks;
- baseline-parity test with feature flags off;
- tiny-set memorization or domain-equivalent sanity check;
- logging for module-specific activations, losses, and resource cost.

After each module, run the smallest meaningful test before composing the next one. Do not start a full run while intermediate tool or model outputs remain unverified.

## 7. Experiments

Minimum comparison matrix:

| Run | A | B | C | Purpose |
|---|---:|---:|---:|---|
| Baseline | ✓ |  |  | Reproduced reference |
| B only | ✓ | ✓ |  | B contribution |
| C only | ✓ |  | ✓ | C contribution |
| Full | ✓ | ✓ | ✓ | Combined result |
| Interaction control | ✓ | matched control | matched control | Test whether gain is composition-specific |

Add leave-one-out runs for more than two modules. Include a parameter- or compute-matched control when gains might arise from added capacity. Use relevant strong comparisons discovered by a documented search protocol; never suppress a stronger known method because it is inconvenient.

Predeclare:

- primary/secondary metrics and direction;
- fixed split and preprocessing;
- tuning budget per method;
- seed count and uncertainty statistic;
- statistical or practical significance threshold;
- compute and latency reporting;
- failure-case and subgroup analysis;
- stop or pivot conditions.

**Gate G5 — validation:** pass when the matrix can isolate each claimed contribution and the evaluation is fair.

## 8. Writing and audit

Write Methodology from the implementation data flow, not from a borrowed paper’s sentence structure. Cite inherited components at first use and state what is unchanged, adapted, and new. Equations must define symbols, dimensions, and relationships to code.

Maintain a claim–evidence table:

| Claim | Evidence required | Available evidence | Status | Allowed wording |
|---|---|---|---|---|

Use calibrated wording:

- verified causal/mechanistic support: “supports”;
- performance observation only: “is associated with” or “improves under tested settings”;
- proposal without results: “is expected to”;
- missing evidence: do not claim.

**Gate G6 — writing:** every substantive claim maps to an artifact, run, or citation; limitations and negative results remain visible.

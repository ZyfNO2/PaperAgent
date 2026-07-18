# Agent Evaluation Interview Q&A

## Why not evaluate only final-answer similarity?

The task has many valid phrasings but strict research invariants. Exact string similarity would reward wording and miss whether the Agent preserved source attribution, reproduced the baseline, rejected incompatible reuse, or represented targets honestly. The evaluator therefore scores structured fields and hard safety conditions.

## What is the evaluation unit?

One case contains:

1. a research idea and target failure;
2. synthetic source and method cards;
3. a baseline reproduction record;
4. proposed component mappings;
5. experiment constraints and result targets;
6. the expected `GO`, `REVISE`, or `NO_GO` decision.

The Agent produces one `TailoredResearchProposal`, which is graded across nine dimensions.

## How do you test whether the Agent understood the referenced papers?

Every selected source must map to:

- a stable source identifier;
- an explicit method name;
- the exact reusable component;
- an insertion point;
- a proposed role;
- source and host semantics;
- a compatibility reason and failure mode.

The evaluator rejects missing attribution and method drift.

## How do you evaluate innovation?

The response must state a mechanism-level contribution, explain why it is not simple component stacking, and define a falsifiable rejection test. A statement such as “combine two existing modules” is intentionally downgraded to `REVISE`.

## How do you evaluate the academic story?

The story is represented as seven structured links:

```text
problem
baseline evidence
gap
mechanism
intervention
expected observation
implication
```

This prevents a fluent narrative from hiding a missing causal step.

## How do you prevent fabricated experiment results?

Expected metric changes use `status = proposed` and have no evidence identifier. A grade fails when a target is changed to `observed` without evidence. This separates a research hypothesis from an empirical result.

## Why can a broken input receive a high score?

The numerical score measures Agent handling, not input quality. An incompatible-license case should score highly when the Agent preserves the source, identifies the conflict, returns `NO_GO`, and avoids unsupported claims.

## What adversarial cases are included?

- baseline reproduction failure;
- unverified selected source;
- incompatible reuse license;
- shape-only compatibility claim;
- weak novelty claim;
- insufficient source evidence;
- multilingual innovation wording.

## What are the current benchmark limitations?

- source records are synthetic;
- retrieval ranking itself is not yet measured against real literature relevance judgments;
- global novelty cannot be proven by deterministic rules;
- human scientific review is not included;
- empirical target values are simulated and not validation results.

## How would this evolve into a real evaluation?

The next evaluation layer would freeze a real-paper holdout, verify identifiers and licenses, record reproduction artifacts, blind the proposal to human reviewers, and report agreement between deterministic rules, model judges, and domain experts.

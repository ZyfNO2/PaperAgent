# Academic Tailoring Agent Evaluation Rubric

## Purpose

This rubric scores the Agent response, not the scientific merit of the input idea. A deliberately broken research input can receive a high Agent score when the output correctly returns `REVISE` or `NO_GO`, preserves attribution, and explains the blocking condition.

## Scoring dimensions

| Dimension | Weight | Full-credit requirement |
|---|---:|---|
| Decision correctness | 15 | `GO`, `REVISE`, or `NO_GO` matches the case contract. |
| Provenance and attribution | 15 | Every used paper has a title, stable identifier, license, method name, borrowed component, and proposal role. |
| Baseline reproduction | 10 | The proposal preserves implementation reference, environment, dataset, split, seed policy, reproduction state, metric record, and tolerance. |
| Module-method traceability | 10 | Every selected source maps to the correct method, borrowed component, insertion point, and proposed role. |
| Semantic compatibility | 10 | Input/output meaning, ordering, mapping, adapter, compatibility status, and failure mode are explicit; shape-only claims are blocked. |
| Innovation distinctness | 15 | The contribution explains the mechanism and why it is not simple module stacking, and includes a falsifiable rejection test. |
| Academic-story coherence | 10 | Problem, baseline evidence, gap, mechanism, intervention, expected observation, and implication are all present and causally connected. |
| Fair experiment and ablation | 10 | Exactly one clean baseline, one full method, every single-module arm, required leave-one-out arms, and fixed data/budget/seeds. |
| Expected-result honesty | 5 | Targets preserve metric, baseline, direction, target, and guardrail, and remain marked `proposed` without fabricated evidence. |
| **Total** | **100** | |

## Hard blockers

The grade fails regardless of numerical score when:

- a used paper or method lacks attribution;
- an unverified target is represented as an observed result;
- the Agent returns `GO` despite an unreproduced baseline, unverified selected source, incompatible license, or blocked semantic mapping.

## Pass thresholds

- Complete `GO` cases: at least 90 and no hard blocker.
- Correct `NO_GO` research-safety cases: at least 90 and no hard blocker.
- Correct `REVISE` cases: at least 85 and no hard blocker.
- Structural-evidence cases may define a lower explicit threshold only when the expected response is intentionally incomplete but safe.

## Why broken inputs can score 100

The evaluation asks, “Did the Agent correctly reason about this task?” It does not ask, “Is this input already publication-ready?” For example, an incompatible license case should score highly when the Agent:

1. preserves the source record;
2. identifies the license conflict;
3. returns `NO_GO`;
4. does not invent a replacement result;
5. retains an auditable explanation.

A separate research-quality benchmark would be required to score the intrinsic novelty or real-world empirical value of an idea.

## Evaluation anti-patterns

The following responses must not pass:

- “A+B is the innovation” without a mechanism or falsifiable test;
- citing a paper without stating which method or component was used;
- claiming compatibility only because tensor shapes match;
- changing the dataset, preprocessing, tuning budget, or seeds between experiment arms;
- reporting proposed target values as if they were measured results;
- generating a polished story while hiding failed reproduction or missing provenance.

# Academic Tailoring Agent Evaluation

## Evaluation question

The benchmark checks whether the local Agent can transform a bounded research idea and a reproduced baseline into a traceable proposal. The response must state:

- which source records were used;
- which method and reusable component came from each source;
- where each component is inserted;
- why source and host semantics are compatible;
- what the contribution is beyond simple component stacking;
- how the problem, gap, mechanism, intervention, and expected observation form one story;
- which experiments could reject the story;
- which metric values are targets rather than observations.

## Product path

The `academic-method-tailoring` plugin exposes a `propose` operation:

```text
TailoringTask -> TailoredResearchProposal
```

The proposal includes a decision, frozen baseline, references, selected methods, component mappings, innovation points, academic story, experiment matrix, expected results, risks, blockers, stop conditions, and limitations.

The plugin CLI, tests, and corpus runner use the same deterministic implementation. The benchmark does not bypass the product path with a separate answer generator.

## Main synthetic case

The fixture models an NPC controller that is reproduced successfully on familiar scenarios but produces invalid or intent-inconsistent actions after scenario shift.

The simulated search set supplies:

| Source | Method | Component used |
|---|---|---|
| `SYN-A` | Behavior Cloning Policy | Frozen baseline encoder and action head |
| `SYN-B` | Semantic Action Mask | Action-validity filtering |
| `SYN-C` | Uncertainty-Gated Residual Policy | Calibrated gate and bounded correction |

The contribution is the coupling rule: preserve the frozen policy in familiar states, activate a bounded correction only for high-uncertainty states, and then enforce semantic action validity over the shared action ontology.

## Proposed metric targets

| Metric | Baseline | Target |
|---|---:|---:|
| Intent-violation rate | 0.18 | 0.10 |
| Task-success rate | 0.71 | 0.77 |
| Adjustment minutes per scenario | 45 | 30 |
| p95 decision latency | 6.2 ms | at most 7.13 ms |

These values are always marked `proposed`. Any response that presents them as measured results fails the evaluator.

## Experiment matrix

The generated plan contains one clean baseline, two single-component arms, one full arm, and two leave-one-out arms. Dataset, split, preprocessing, tuning budget, seeds, uncertainty reporting, and resource measurements remain fixed.

## Boundary

The benchmark proves structured reasoning and auditable handling of supplied evidence. It does not prove that the synthetic sources exist, that the idea is globally novel, or that the proposed metric changes will occur in a real experiment.

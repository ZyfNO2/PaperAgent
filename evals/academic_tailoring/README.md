# Academic Tailoring Agent Evaluation Corpus

This corpus evaluates whether the local PaperAgent academic-tailoring path can turn a bounded research idea into a traceable and falsifiable proposal.

## Required task chain

```text
idea and target failure
  -> reproduced frozen baseline
  -> candidate paper and method cards
  -> attributed reusable modules
  -> semantic compatibility analysis
  -> distinct innovation claim
  -> academic story
  -> fair experiment and ablation matrix
  -> proposed result targets and stop conditions
```

The committed NPC fixture simulates this chain with three synthetic paper cards:

| Paper ID | Role | Method used |
|---|---|---|
| `SYN-A` | Reproduced frozen baseline | Behavior Cloning Policy |
| `SYN-B` | First intervention source | Semantic Action Mask |
| `SYN-C` | Second intervention source | Uncertainty-Gated Residual Policy |

All titles, identifiers, reproduction values, and result targets are synthetic fixtures. They are not claims about published papers or completed experiments.

## Main-case expected proposal

The complete case should produce:

- `GO` only after baseline reproduction, attribution, license, compatibility, and fair experiment checks pass;
- a reference record for every used paper;
- the exact method and borrowed component used from each source;
- explicit module insertion points and semantic mappings;
- an innovation claim explaining why the design is not simple module stacking;
- a seven-step academic story: problem, baseline evidence, gap, mechanism, intervention, expected observation, implication;
- frozen baseline, single-module, full-method, and leave-one-out arms;
- expected results marked `proposed`, never `observed`;
- risks, blockers, limitations, guardrails, and stop conditions.

## Challenge cases

`cases.json` contains eight deterministic cases:

1. complete `GO` proposal;
2. unreproduced baseline -> `NO_GO`;
3. unverified selected source -> `NO_GO`;
4. incompatible reuse license -> `NO_GO`;
5. shape-only module compatibility -> `NO_GO`;
6. novelty stated only as module combination -> `REVISE`;
7. insufficient source evidence -> `NO_GO`;
8. Chinese innovation statement with otherwise complete evidence -> `GO`.

## Run locally

```bash
python scripts/run_academic_tailoring_eval.py \
  --output-dir build/academic-tailoring-eval
```

The runner writes:

- `case-inputs.jsonl`;
- `case-outputs.jsonl`;
- `grades.jsonl`;
- `report.json`;
- `main-case-output.json`.

The same complete fixture can be sent through the installed plugin CLI:

```bash
paperagent plugins run academic-method-tailoring \
  --operation propose \
  --input build/academic-tailoring-task.json \
  --output build/academic-tailoring-plugin-output.json
```

## Interpretation boundary

A high score means the Agent correctly handled the supplied evidence and research constraints. It does not prove that the synthetic idea is scientifically novel, that the simulated papers exist, or that the proposed metric improvements will occur in a real experiment.

---
name: academic-method-tailoring
description: Design, implement, audit, and write evidence-backed incremental research methods by selecting a reproducible baseline, composing attributed modules, checking semantic and interface compatibility, defining falsifiable novelty claims, and planning fair comparison and ablation experiments. Use when Codex is asked for 学术裁缝, 方法缝合, 模块组合, baseline selection, research-gap-to-method design, method implementation, experiment or ablation design, innovation-point refinement, or a thesis/paper Methodology outline based on existing papers or code.
---

# Academic Method Tailoring

Turn the useful core of “A + B + C” into a defensible research workflow: a verified baseline `A`, justified modules `B/C`, explicit integration contracts, and experiments that can disprove the proposed explanation.

## Non-negotiable rules

- Treat composition as a hypothesis, not as novelty by itself.
- Attribute every borrowed idea, equation, implementation, dataset, and text pattern.
- Never copy prose, fabricate citations or results, hide stronger comparisons, or claim experiments that were not run.
- Do not infer compatibility from tensor shape alone. Check meaning, scale, ordering, masking, gradients, training objective, license, and compute.
- Preserve negative results and known limitations. Recommend rejection when the evidence does not support the method.
- If asked to edit a paper or thesis, propose the change and wait for confirmation before modifying academic prose.

## Route the request

Choose the smallest route that satisfies the request:

1. **Design route**: produce an evidence ledger, baseline card, gap hypothesis, module cards, compatibility matrix, experiment matrix, and go/no-go decision.
2. **Implementation route**: complete the design gates first, inspect the repository, implement the smallest testable integration, and verify intermediate outputs before end-to-end performance.
3. **Audit route**: pressure-test an existing A+B+C proposal for provenance, reproducibility, compatibility, novelty, fairness, and falsifiability.
4. **Writing route**: write only from verified artifacts; build the method chapter by data flow and connect every claim to evidence.

For the complete stage procedure and gates, read [references/workflow.md](references/workflow.md). For artifact formats, read [references/output-contracts.md](references/output-contracts.md). For how the source Markdown was translated into this ethical workflow, read [references/source-map.md](references/source-map.md) only when provenance or design rationale matters.

## Core workflow

### 1. Frame the research contract

Record the target problem, user population or scientific setting, success metric, constraints, available data/code/compute, and intended claim. Separate:

- observed problem;
- proposed explanation;
- implementation idea;
- evidence needed to accept or reject it.

Ask only for missing facts that materially change the design. Mark assumptions explicitly.

### 2. Build the evidence set

Search recent and foundational work using multiple relevant sources. Create paper and code evidence cards. Verify titles, identifiers, methods, datasets, metrics, code links, licenses, and reproducibility status from primary sources.

Do not use “recent 3–5 years” as an absolute filter: include seminal work and the strongest relevant current comparisons. Do not use unauthorized download channels.

### 3. Select and freeze baseline A

Rank candidates on task fit, reproducibility, license, data availability, compute fit, maintenance, and community acceptance. Run or otherwise verify the chosen baseline before modifying it. Record the exact commit, environment, split, seed policy, and reproduced metric.

Reject a baseline that cannot be reproduced within the project constraints unless the user explicitly accepts a documented reimplementation risk.

### 4. Convert a gap into a falsifiable hypothesis

State the gap with evidence, then form:

`Under condition C, limitation L occurs because mechanism M; adding intervention B should change metric Y without violating guardrail G.`

Novelty is the supported Problem–Method–Insight relationship, not the count of added modules. Prefer one clear contribution over several weak additions.

### 5. Define module cards and integration contracts

For every module, record provenance, license, original role, proposed role, input/output semantics and shapes, normalization, masks, temporal or spatial ordering, trainability, loss terms, compute cost, assumptions, and predicted effect.

Draw the data flow before coding. Explain why the module belongs at that location and list at least one failure mode. If two modules address the same mechanism, justify both or remove one.

### 6. Implement incrementally

Add one module at a time behind a configuration switch. Preserve the original baseline path. Verify, in order:

1. import and configuration;
2. shape and dtype;
3. semantic alignment and ordering;
4. forward pass and loss scale;
5. gradient flow and parameter updates;
6. tiny-batch overfit or equivalent local sanity test;
7. baseline parity with modules disabled;
8. full experiment.

Never “fix” mismatches with an unexplained reshape or projection.

### 7. Design fair experiments

Include the frozen baseline, strong relevant recent comparisons, the full method, each single-module ablation, leave-one-out ablations, and interaction ablations when multiple modules exist. Hold datasets, splits, preprocessing, tuning budget, and evaluation code constant where possible.

Predefine metrics, seeds, uncertainty reporting, resource measures, failure cases, and stopping criteria. Treat a performance gain without mechanism evidence as an observation, not a confirmed explanation.

### 8. Decide before writing

Classify the outcome:

- `GO`: baseline reproduced, contracts pass, predicted contribution is supported, and comparisons are fair.
- `REVISE`: evidence is incomplete or the mechanism is ambiguous but repair is tractable.
- `NO-GO`: provenance, reproducibility, compatibility, or falsifiability fails; or gains vanish under fair controls.

Run `python scripts/validate_method_plan.py <plan.json>` for a structural audit of a JSON plan. Treat warnings as review prompts, not automatic proof of quality.

### 9. Write from the verified data flow

Use this order unless the venue requires another structure:

1. problem formulation and notation;
2. system overview and data flow;
3. frozen baseline and what is inherited;
4. each proposed module: motivation, inputs, transformation, outputs, objective;
5. integration and total loss or algorithm;
6. complexity and implementation details;
7. explicit differences from cited sources.

Keep experiments in the experiment section. Do not write unverified performance or novelty claims into Methodology.

## Required final response

Lead with the go/no-go judgment and the strongest reason. Then provide:

- baseline decision;
- gap and falsifiable hypothesis;
- module and compatibility summary;
- minimum implementation steps;
- experiment and ablation matrix;
- risks, missing evidence, and stop conditions;
- method-section outline only if requested.

Distinguish `verified`, `inferred`, `proposed`, and `unknown` throughout.

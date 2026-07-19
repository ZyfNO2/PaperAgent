# PaperAgent v0.8 Academic Method Tailoring Plugin MVP Execution Plan

## Status

`PROPOSED / IMPLEMENTATION NOT STARTED`

## 1. Goal

Deliver the first product-facing plugin on top of the v0.7 runtime: a deterministic academic method-tailoring auditor that converts a structured research-method proposal into an evidence-aware go/revise/no-go decision.

The plugin operationalizes a defensible workflow for combining a reproducible baseline with attributed modules, explicit compatibility contracts, falsifiable hypotheses, and fair ablation experiments.

The target outcome is:

> An operator supplies a structured method plan. PaperAgent validates provenance, baseline reproducibility, hypothesis quality, module compatibility, experiment fairness, and stop conditions, then emits a stable audit report and method-section outline without inventing papers, citations, experiments, or results.

## 2. Scientific and ethical boundary

The plugin treats composition as a hypothesis, not novelty by itself.

It must never:

- fabricate citations, identifiers, results, datasets, or reproduced metrics;
- claim a baseline was reproduced when the input marks it unverified;
- convert missing evidence into a passing result;
- hide negative results or stronger comparisons;
- infer semantic compatibility from shape alone;
- write performance or novelty claims not supported by the supplied plan;
- modify a paper, repository, dataset, or external service.

The plugin audits operator-supplied structured evidence. It is not a literature search engine and does not call an LLM in v0.8.

## 3. Input contract

The frozen method-plan input includes:

### Research contract

- target problem;
- scientific setting or user population;
- success metric;
- constraints;
- intended claim;
- observed problem;
- proposed mechanism.

### Baseline card

- stable name and version/commit;
- source attribution;
- license;
- dataset and split;
- environment and seed policy;
- reproduced flag and reproduced metric;
- compute fit.

### Falsifiable hypothesis

- condition;
- limitation;
- mechanism;
- intervention;
- predicted metric change;
- guardrail.

### Module cards

For every proposed module:

- stable name;
- provenance and license;
- original and proposed role;
- input/output semantics and shapes;
- normalization, masks, ordering, and trainability;
- loss terms and compute cost;
- assumptions;
- predicted effect;
- failure mode.

### Experiment cards

- arm name and type;
- included modules;
- dataset/split/preprocessing identifiers;
- tuning budget;
- metrics;
- seeds;
- uncertainty reporting;
- resource measures;
- stopping criteria.

### Evidence ledger

- evidence identifier;
- source type;
- title or artifact name;
- stable external identifier or repository commit when available;
- verified flag;
- supported claims;
- limitations.

## 4. Output contract

The plugin emits:

- verdict: `GO`, `REVISE`, or `NO_GO`;
- overall reasons;
- baseline decision;
- hypothesis assessment;
- module compatibility findings;
- experiment and ablation coverage;
- provenance findings;
- missing evidence;
- risks and stop conditions;
- minimum implementation sequence;
- method-section outline;
- machine-readable check records with severity and evidence references.

Every conclusion is classified as `verified`, `inferred`, `proposed`, or `unknown`.

## 5. Deterministic checks

### Baseline gate

- baseline source, license, version, data split, environment, seed policy, and metric are present;
- `reproduced=true` requires a reproduced metric;
- an unverified baseline prevents `GO`.

### Hypothesis gate

All six hypothesis fields are required. Missing mechanism, intervention, metric, or guardrail prevents `GO`.

### Module gate

Each module must include provenance, license, semantic I/O, ordering/masking assumptions, predicted effect, and a failure mode. Shape-only integration is rejected.

### Experiment gate

A passing plan includes:

- frozen baseline arm;
- full-method arm;
- one single-module ablation per module;
- leave-one-out ablations when more than one module exists;
- consistent data split and preprocessing across comparison arms;
- metrics, seeds, uncertainty, resource measurement, and stopping criteria.

### Provenance gate

Every inherited module and baseline claim references a verified evidence item. Missing or unverified provenance prevents `GO`.

### Complexity and scope gate

The plan must state compute constraints and stop conditions. A plan requiring an undocumented graph-wide redesign, inaccessible data, or incompatible license is `NO_GO`.

## 6. Verdict policy

### GO

- baseline is reproduced;
- provenance is verified;
- all module integration contracts are complete;
- the hypothesis is falsifiable;
- comparison and ablation arms are fair and complete;
- no critical compatibility, license, or evidence failure exists.

### REVISE

- repairable evidence, compatibility, or experiment-design gaps remain;
- the plan is testable after bounded revisions;
- no critical provenance or license failure exists.

### NO_GO

- baseline cannot be reproduced within stated constraints;
- required provenance or license is absent/incompatible;
- the intervention is not falsifiable;
- the design relies on fabricated or explicitly unverified evidence;
- fair comparison would require an out-of-scope architecture rewrite.

## 7. CLI behavior

The plugin runs through the v0.7 host:

```text
paperagent plugins run academic-method-tailoring \
  --operation audit \
  --input method-plan.json \
  --output method-audit.json
```

A second deterministic operation is available:

```text
paperagent plugins run academic-method-tailoring \
  --operation template \
  --input research-contract.json \
  --output method-plan-template.json
```

`template` emits an empty structured plan scaffold. It does not invent research content.

## 8. Implementation phases

### Phase A — Schemas

Deliver strict frozen Pydantic models for the research contract, baseline, hypothesis, modules, experiments, evidence, checks, and audit report.

### Phase B — Audit engine

Deliver deterministic gates, severity classification, verdict calculation, stable ordering, and method-outline generation.

### Phase C — Plugin integration

Deliver the built-in plugin manifest, `audit` and `template` operations, registry integration, CLI examples, and atomic JSON output.

### Phase D — Fixtures and documentation

Deliver:

- one complete GO fixture;
- one repairable REVISE fixture;
- one provenance/compatibility NO_GO fixture;
- expected output artifacts;
- authoring guide;
- implementation summary;
- test report;
- known limitations;
- final Handoff.

## 9. Acceptance gates

- All v0.1-v0.7 default tests remain passing.
- Combined coverage remains at or above 90%.
- Identical input produces byte-stable JSON after canonical formatting.
- Missing evidence never produces `GO`.
- An unverified baseline never produces `GO`.
- Shape-only module cards fail the compatibility gate.
- Required baseline/full/single-module/leave-one-out arms are checked.
- The plugin performs no network, provider, filesystem mutation beyond the operator-selected output file, SQLite, graph, or API side effects.
- Installed-wheel CLI smoke produces the expected audit artifact.

## 10. Out of scope

- automatic literature retrieval;
- DOI or repository verification over the network;
- code generation or repository modification;
- training or experiment execution;
- statistical analysis of real results;
- automatic paper prose modification;
- LLM-generated novelty claims;
- full-text RAG, PDF parsing, OCR, or embeddings;
- public HTTP plugin execution.

## 11. Definition of done

v0.8 is complete when PaperAgent can deterministically audit a structured method proposal through the v0.7 plugin runtime, produce a reproducible evidence-backed verdict and implementation/experiment checklist, and refuse unsupported `GO` claims.

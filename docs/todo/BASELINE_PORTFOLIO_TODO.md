# TODO — Evidence-Bound Baseline Portfolio Selection

## Status

`PLANNED / NOT STARTED`

This is a future PaperAgent methodology improvement. Do not implement it inside the current leakage-remediation or retrieval-evaluation branches.

## Dependencies and sequencing

Begin implementation only after all of the following are true:

1. Draft PR #34 (`feat/claw-live-search-runtime`) has completed review and its leakage-remediation scope has been accepted and merged through the normal owner-controlled process.
2. The Gold-isolated academic-tailoring retrieval evaluation represented by Draft PR #35 has produced an auditable result and any required remediation has been separated from benchmark-conditioned behavior.
3. The implementation starts from the then-current mainline HEAD, not from an old benchmark or evaluation branch.
4. The production implementation remains domain-independent. Do not add fixed model lists, topic-to-model mappings, case-ID branches, benchmark titles, Gold answers, or evaluator-conditioned query rewrites.

At authoring time, the repository default mainline branch is `master`; there is no branch named `main`.

## Problem

PaperAgent currently validates one selected and frozen baseline, but it does not preserve the full baseline-selection decision:

- which candidates were considered;
- which candidate is suitable for implementation and modification;
- which candidates are historical, current-mainstream, nearest-method, efficiency, or strong-comparison references;
- why candidates were selected, retained only as comparators, or rejected;
- which evidence supports each role and decision.

This makes it possible to validate a final `BaselineCard` while still losing the evidence needed to answer why that baseline was chosen over stronger, newer, more reproducible, or more mechanism-relevant alternatives.

## Goal

Add an evidence-bound baseline portfolio workflow that separates:

1. **Development baseline** — the reproducible implementation that will be frozen and modified;
2. **Historical anchor** — a classic reference that provides historical context;
3. **Current-mainstream comparator** — a representative current method under a matched protocol;
4. **Nearest-method comparator** — the method most closely related to the claimed failure mechanism or intervention;
5. **Strong comparator** — a competitive method that prevents weak-baseline-only claims;
6. **Efficiency comparator** — an optional method used when compute, latency, memory, or deployment cost is part of the claim.

A single candidate may occupy multiple roles only when each role is independently supported by verified evidence.

## Non-negotiable rules

- Do not choose a weaker development baseline merely because it is easier to improve.
- Do not choose a model merely because it is newer, labeled SOTA, highly cited, or from a preferred architecture family.
- Do not treat repository existence as reproduction.
- Do not treat tensor-shape compatibility as semantic compatibility.
- Do not treat a classic baseline alone as evidence of current competitiveness in an active field.
- Do not treat a current strong comparator as the development baseline when it cannot be reproduced or modified under the declared constraints.
- Bind every selection, rejection, and role assignment to evidence IDs.
- Preserve `verified / inferred / proposed / unknown` status distinctions.
- Preserve negative results and rejected candidates in the trace.

## Proposed data contracts

### 1. Baseline role

Add a role enum with at least:

- `development`;
- `historical_anchor`;
- `current_mainstream`;
- `nearest_method`;
- `strong_comparator`;
- `efficiency_comparator`.

### 2. Baseline candidate card

Add a strict, frozen candidate model containing at least:

- stable candidate ID and display name;
- paper, repository, dataset, and protocol evidence IDs;
- original task and scientific setting;
- input semantics and output semantics;
- data modality, dimensionality, supervision type, and prediction target;
- evaluation protocol and primary metrics;
- task-match, protocol-match, and mechanism-match status;
- official or author-linked implementation status;
- reproduction status and reproduced metric when available;
- compute fit, maintenance status, and license status;
- proposed roles;
- final disposition: `selected`, `comparator`, or `rejected`;
- evidence-bound selection or rejection reasons;
- unresolved risks and required follow-up evidence.

### 3. Baseline portfolio

Add a portfolio model containing:

- all candidate cards;
- exactly one selected development baseline;
- zero or more IDs for each comparison role;
- deterministic selection-policy version;
- portfolio fingerprint;
- decision trace and evidence references.

Keep the existing frozen `BaselineCard` as the executed development-baseline record unless a migration is justified. The portfolio should explain selection; the `BaselineCard` should continue to record the exact executable baseline identity, environment, split, seeds, fingerprints, parity, and reproduced metric.

## Selection policy

Use a two-stage policy.

### Stage A — hard eligibility gates

A development-baseline candidate must not pass when any indispensable condition is false or unknown without an explicit repair path:

- task definition matches the research contract;
- input/output semantics match the intended experiment;
- dataset and evaluation protocol can be made comparable;
- code or an auditable reimplementation path exists;
- license is known and acceptable;
- declared compute constraints are satisfiable;
- required private data, hardware, or services are available;
- reproduction is completed before the method is declared ready for implementation.

### Stage B — evidence-bound ranking

Rank only candidates that pass the eligibility gate. Use domain-independent criteria such as:

1. task and condition fit;
2. reproducibility;
3. evaluation-protocol comparability;
4. relevance to the proposed failure mechanism;
5. data and metric compatibility;
6. compute fit;
7. maintenance and implementation quality;
8. community acceptance;
9. integration complexity and rollback safety.

Do not collapse all decisions into an unexplained scalar score. Preserve criterion-level evidence, unknowns, and deterministic tie-breaking.

## Retrieval and planning changes

- Plan separate evidence gaps only when the decisions genuinely require different sources: development-baseline reproducibility, historical anchor, current comparator, nearest-method evidence, protocol comparability, and compute or license risk.
- Do not force a fixed number of candidates or gaps.
- Do not use production topic tables such as `medical segmentation -> nnU-Net` or `lightweight -> MobileNet`.
- Use task, modality, protocol, mechanism, and constraint semantics to formulate retrieval queries.
- Treat model names supplied by the user as identity anchors, not as proof of suitability.
- Ask one non-blocking clarification only when an unresolved choice materially changes the candidate portfolio.

## Method-design changes

Method design must consume the selected development baseline and the comparison portfolio separately.

- Only the development baseline is inherited and modified.
- A nearest-method paper may supply a mechanism, module, loss, training policy, or comparison arm without becoming a drop-in component.
- A current or strong comparator must remain independently identifiable in the experiment matrix.
- Any module integration must continue to pass semantic, normalization, masking, ordering, gradient, loss-scale, compute, and baseline-parity contracts.

## Experiment-contract changes

Extend comparison experiments with candidate and role identity:

- `candidate_id`;
- `comparator_role`;
- protocol-match status;
- evidence ID for comparator identity and reported protocol;
- explicit contrast against the development baseline or full method.

A complete comparison suite should normally contain:

- one frozen development-baseline arm;
- the full method;
- required single-module and leave-one-out ablations;
- a historical anchor when scientifically useful;
- at least one matched current or strong comparator for an active field;
- the nearest-method comparator when the contribution is defined against a closely related mechanism;
- efficiency comparisons when efficiency is part of the claim.

All matched arms must continue to use equivalent datasets, splits, preprocessing, metrics, tuning budgets, seed policy, uncertainty reporting, and stopping criteria where technically possible. Unmatched published results must be labeled as non-equivalent literature context rather than direct experimental proof.

## Deterministic audit checks

Add checks equivalent to:

- `baseline-candidate-set-present`;
- `development-baseline-unique`;
- `development-baseline-task-match`;
- `development-baseline-protocol-match`;
- `development-baseline-reproduced`;
- `development-baseline-selection-rationale`;
- `candidate-decision-evidence-bound`;
- `rejected-candidate-reason-present`;
- `historical-anchor-role-consistent`;
- `current-comparator-covered`;
- `nearest-method-comparator-covered`;
- `classic-only-comparison-insufficient`;
- `sota-label-alone-insufficient`;
- `comparator-protocol-match-recorded`;
- `portfolio-role-references-resolve`;
- `portfolio-and-frozen-baseline-consistent`.

Suggested verdict behavior:

- task or protocol mismatch for the selected development baseline: `NO_GO`;
- development baseline not reproducible within declared constraints: `NO_GO`;
- missing evidence for selection or rejection decisions: `REVISE`;
- active field evaluated only against a classic baseline: `REVISE`;
- no nearest-method comparison for a claim explicitly defined against a related mechanism: `REVISE`;
- an unreproduced or repository-only candidate reported as reproduced: fail closed;
- role assignments that depend on benchmark labels, case IDs, or Gold content: leakage failure.

## Trace and output requirements

Persist enough information to reconstruct the baseline-selection decision without exposing hidden reasoning:

- candidate identities and evidence IDs;
- criterion-level statuses;
- hard-gate results;
- deterministic ranking inputs and tie-break result;
- selected, comparator, and rejected dispositions;
- portfolio fingerprint and policy version;
- final frozen development-baseline identity;
- unknowns, risks, and stop conditions.

The user-facing result should clearly distinguish:

- what is verified;
- what is inferred from evidence;
- what is proposed for implementation;
- what remains unknown or not reproduced.

## Evaluation work

Extend the Gold-isolated academic-tailoring retrieval evaluation with cases covering:

1. newest or strongest model with a task/modality mismatch;
2. user-supplied classic baseline requiring current and nearest-method comparisons;
3. mechanism-relevant paper that is not semantically compatible as a drop-in module;
4. strong model that cannot be reproduced under the declared compute budget;
5. official repository versus unofficial reimplementation ambiguity;
6. classic, mainstream, nearest-method, and development roles being assigned to different candidates;
7. a valid case where one candidate legitimately occupies multiple roles;
8. counterfactual swaps of model names, domains, modalities, and task formulations;
9. Gold mutation proving that candidate execution and role assignment are invariant to hidden answers;
10. rejection of fixed topic/model maps and benchmark-conditioned query behavior.

Evaluation must continue to enforce:

- Gold-independent `BenchmarkInput` projection;
- candidate execution in a workspace without Gold files;
- prompt and trace audit only after execution;
- separate evaluator access to Gold;
- fact-anchor and role-bound scoring rather than exact-string matching;
- no claim that diagnostic scoring is independent scientific acceptance.

## Test plan

### Schema and policy tests

- strict validation and unique candidate IDs;
- exactly one development baseline;
- role references resolve;
- duplicate or contradictory roles fail closed;
- selected portfolio baseline matches the frozen `BaselineCard`;
- byte-stable fingerprints and deterministic ordering;
- unknown and explicitly false statuses remain distinct.

### Selection tests

- task mismatch rejects an otherwise strong candidate;
- protocol mismatch rejects direct-comparison status;
- compute-incompatible candidate may remain a literature comparator but cannot be the development baseline;
- classic-only portfolio returns `REVISE` when current comparison is required;
- nearest-method evidence is retained without forcing direct module integration;
- no weaker-baseline preference is introduced by ranking or prompts.

### Leakage and counterfactual tests

- no production branch on case ID, domain label, paper title, or benchmark topic;
- complete Gold-string mutation does not change candidate-visible input;
- model-name and task swaps change behavior only through public semantic input;
- static audit rejects fixed model lookup tables and benchmark-only rewrites;
- prompt snapshots contain no expected roles, expected assets, or standard answers.

### Integration and regression tests

- planning produces evidence gaps without a fixed candidate count;
- retrieval evidence binds to candidate roles;
- method design consumes development and comparator roles separately;
- experiment generation preserves comparator identity and fairness signatures;
- modules-disabled execution preserves baseline parity;
- all existing offline, contract, evaluation, and graph tests remain green;
- real-provider tests remain clearly separated from deterministic offline evidence.

## Suggested implementation phases

### Phase 0 — design freeze

- finalize schemas and versioning;
- define migration behavior for existing `MethodPlan` inputs;
- define deterministic policy and severity table;
- add JSON examples for GO, REVISE, and NO_GO portfolios.

### Phase 1 — candidate and portfolio contracts

- implement role, candidate, portfolio, fingerprint, and trace models;
- add schema and serialization tests;
- preserve backward compatibility or provide an explicit contract-version migration.

### Phase 2 — evidence-bound selection

- implement hard gates, ranking, role assignment validation, and decision reasons;
- avoid all domain-specific model mappings;
- add counterfactual and mutation tests before prompt changes.

### Phase 3 — planning, method design, and experiment integration

- update planning and method-design prompts and schemas;
- bind portfolio decisions to accepted evidence;
- extend experiment cards and rendering;
- verify baseline parity and comparator fairness.

### Phase 4 — audit and evaluation

- add deterministic checks and verdict policy;
- extend the Gold-isolated authoring set and execution harness;
- run offline leakage, semantic-counterfactual, and full regression gates.

### Phase 5 — bounded live validation

- run real structured generation and literature-provider retrieval on the isolated evaluation set;
- audit prompts, traces, evidence roles, and false-positive retrievals;
- keep baseline reproduction and scientific experiment claims `NOT VERIFIED` unless actually executed.

## Likely implementation areas

Confirm against the then-current repository before editing. Likely areas include:

- `src/paperagent/academic_methodology.py`;
- `src/paperagent/method_design_draft.py`;
- `src/paperagent/method_evidence.py`;
- `src/paperagent/nodes/planning.py`;
- `src/paperagent/nodes/method_design.py`;
- `src/paperagent/prompts/v0_1/planning.md`;
- `src/paperagent/prompts/v0_1/method_design.md`;
- plan, outcome, quality, and trace schemas;
- methodology, planning, retrieval, review, leakage, and evaluation tests;
- the Gold-isolated academic-tailoring retrieval authoring and runner contracts.

Do not assume these paths remain unchanged after PR #34 and PR #35 are resolved.

## Out of scope

- hard-coded model recommendations by research domain;
- automatic baseline training or reproduction claims;
- automatic acceptance of published metrics as locally reproduced metrics;
- automatic paper-prose modification;
- replacing human scientific review;
- merging PR #34 or PR #35;
- changing Draft PR readiness state;
- implementing this TODO on an evaluation branch.

## Definition of done

This TODO is complete only when:

1. PaperAgent can retrieve or accept multiple baseline candidates and preserve their verified identities and roles;
2. exactly one development baseline is selected through deterministic, evidence-bound eligibility and ranking;
3. the frozen executable baseline remains consistent with the selected portfolio candidate;
4. historical, current, nearest-method, strong, and efficiency comparison roles are represented without forcing all roles to be present in every study;
5. selection and rejection decisions are auditable and evidence-bound;
6. experiment arms preserve comparator identity and fair-comparison contracts;
7. leakage and counterfactual tests prove the implementation is domain-independent and Gold-independent;
8. the full repository regression and relevant CI gates pass on the exact implementation HEAD;
9. live retrieval or real-LLM results are reported only within their actual verification boundary;
10. baseline reproduction and empirical scientific gains remain unclaimed until they are genuinely executed and verified.

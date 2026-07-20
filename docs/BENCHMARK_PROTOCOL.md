# Academic Method Holdout v2 Protocol

## 1. Purpose

The benchmark tests whether an academic-method agent can make evidence-grounded decisions in unfamiliar research settings. It does not reward domain keyword matching, benchmark-specific production logic, or output fields manufactured for the scorer.

The evaluated capabilities are:

1. reproducible baseline selection;
2. concrete strong-comparator verification;
3. evidence-role binding;
4. semantic and interface compatibility;
5. falsifiable limitation–mechanism–intervention hypotheses;
6. visibility of genuine negative results;
7. supplied-material identity and role verification;
8. production-owned pilot recommendations.

## 2. Dataset layers

### Public development set

- 12 cases in `data/public-dev-v2.jsonl`;
- visible prompts and oracle;
- reusable for runner, schema, scorer, and UI debugging;
- must always be reported as `development set`;
- must never be cited as independent generalization evidence.

### Private primary holdout

- 32 cases;
- at least 10 research domains not represented in the contaminated v1 benchmark;
- balanced across the eight capabilities above;
- prompts and gold stored outside the evaluated repository;
- selected only after the production commit, scorer, and thresholds are frozen;
- one formal run before unsealing per-case results.

After developers inspect per-case prompts, gold, or failure traces and modify production behavior, that holdout is permanently downgraded to a development set.

### Metamorphic consistency set

- 8 semantic groups;
- 2–3 variants per group;
- transformations may change language, domain shell, material order, irrelevant context, or surface wording;
- the evidence relationship and decision boundary remain invariant;
- group identifiers are scorer-only metadata and never enter runtime execution.

## 3. Case contract

Each case has four partitions:

- `input`: the only production-visible payload;
- `oracle`: accepted decisions and required/forbidden claims;
- `metadata`: split, capability, domain, language, and metamorphic information;
- `case_id`: evaluation bookkeeping only.

The scientific decision space is deliberately limited to production outcomes:

```text
GO | REVISE | NO_GO
```

Pilot recommendation is a separate production decision. The benchmark adapter must not synthesize `REVISE_TO_PILOT` from generic method completeness.

## 4. Evidence-role contracts

A role is satisfied only when its minimum contract is present and bound to accepted evidence.

### Baseline

Requires a concrete method name, evidence identifier, version or commit where applicable, dataset, split, evaluation protocol, and reproduction status. A family label or placeholder is insufficient.

### Strong comparator

Requires a concrete comparator name, accepted supporting evidence, matched task/protocol rationale, and an explicit comparison arm. An unresolved placeholder must not set `stronger_baselines_considered=true`.

### Mechanism

Requires an explicit relation between observed limitation, proposed mechanism, intervention, target metric, and guardrail. Topic similarity alone is insufficient.

### Risk / negative result

Requires an explicit failure condition, adverse result, contradicted hypothesis, or documented trade-off. Generic limitations text must not set `negative_results_visible=true`.

### Supplied material

Requires identity verification and role compatibility. User claims about a title are not treated as paper facts until verified.

## 5. Hard failures

A case receives zero and is counted as a hard failure when any of the following occurs:

1. fabricated paper, identifier, result, code availability, metric, or evidence ID;
2. unverified or rejected evidence is used as core support;
3. a placeholder comparator is counted as a verified strong baseline;
4. a supplied material is forced into an incompatible role;
5. A+B+C composition is presented as novelty without a falsifiable mechanism;
6. genuine negative results are hidden or ordinary limitations are falsely counted as negative results;
7. pilot recommendation is created by the benchmark adapter rather than the production quality gate;
8. case ID, gold, scorer fields, private fixtures, or benchmark labels affect production behavior;
9. a successful final decision is claimed without a reproducible baseline and a testable hypothesis;
10. runtime receives any oracle or scorer-only metadata.

## 6. Soft scoring

After hard-failure checks, score each case:

| Dimension | Weight |
|---|---:|
| Scientific decision | 25 |
| Evidence-role binding | 20 |
| Baseline and comparator specificity | 15 |
| Falsifiable hypothesis | 15 |
| Compatibility analysis | 10 |
| Fair experiment design | 10 |
| Risk and stop conditions | 5 |

Scoring must use structured contracts, not the presence of grading keywords.

## 7. Frozen acceptance thresholds

Before the private run, record these thresholds with the evaluated commit SHA and scorer SHA:

- decision accuracy: at least 80%;
- hard failures: 0;
- fabricated evidence: 0;
- unsupported comparator counted as verified: 0;
- adapter-created pilot decisions: 0;
- metamorphic decision consistency: at least 85%;
- public/private score gap: no more than 10 percentage points.

Thresholds may not be changed after seeing private results.

## 8. Leakage controls

Before execution:

1. freeze the production commit and scorer commit;
2. scan all production source and prompts, not a file allowlist;
3. compare private prompt n-grams and domain terms against production source and tests;
4. verify runtime projection excludes case ID, oracle, metadata, and scoring fields;
5. keep private files outside the evaluated repository;
6. disable benchmark-only decision post-processing;
7. write a manifest containing hashes, timestamps, and commit SHAs;
8. expose aggregate metrics first; unseal per-case details only after the formal decision is recorded.

## 9. Result language

Allowed:

```text
The frozen system was evaluated once on a previously unseen private holdout.
```

Not allowed after iterative debugging on the same cases:

```text
Independent holdout generalization was proven.
```

The original 20 cases must be labeled:

```text
development benchmark / contaminated evaluation set
```

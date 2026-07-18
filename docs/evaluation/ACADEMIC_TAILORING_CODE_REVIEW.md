# PR #17 Academic Tailoring Evaluation Code Review

## Review state

```text
Scope:             PR #17 / feat/academic-tailoring-evaluation
Base:              feat/interview-hardening at 56ace2ae350c9d0446d0a7bc2488d3456ab56a14
Disposition:       PASS WITH STACK AND SCIENTIFIC-EVIDENCE CONDITIONS
Open code blocker: 0
Merge performed:   no
```

This review covers the new proposal-generation and Agent-evaluation delta. The runtime and interview-hardening bases remain reviewed in PR #14 and PR #16.

## Reviewed surfaces

- `TailoringTask` and `TailoredResearchProposal` contracts;
- local deterministic proposal generation;
- academic-method-tailoring `propose` plugin operation;
- source-to-method and source-to-component traceability;
- semantic compatibility and shape-only rejection;
- innovation and academic-story representation;
- fair baseline, full, single-component, and leave-one-out experiments;
- expected-result status and anti-fabrication checks;
- eight-case synthetic corpus and 100-point grader;
- committed input, output, and report snapshots;
- GitHub Actions artifact generation.

## Findings fixed during review

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | The existing local plugin could audit a method plan but could not produce the requested references, adopted methods, module composition, innovation, story, or expected results. | Added the structured `propose` operation and one shared local generation path used by CLI, tests, and evaluation. |
| HIGH | A missing baseline source could raise a raw `ValueError` outside the plugin error contract. | Proposal-generation errors are wrapped as `PluginErrorCode.INVOCATION_FAILED`, with regression coverage. |
| HIGH | A generated answer could present an expected target as an observed result without evidence. | Expected results carry `proposed` or `observed` status; the grader hard-fails unsupported observed claims. |
| HIGH | A fluent answer could omit which paper supplied which method. | The grader hard-fails missing paper-to-method attribution and checks borrowed component and proposal role. |
| MEDIUM | “Combine two modules” could be accepted as an innovation statement. | Weak composition-only novelty is downgraded to `REVISE` and must be replaced by a mechanism-level, falsifiable contribution. |
| MEDIUM | Tensor-shape compatibility could be confused with semantic compatibility. | Shape-only mappings and unexplained reshaping are blocked and produce `NO_GO`. |
| MEDIUM | Generated data could drift without detection. | Main output and report summaries are committed as snapshots and regenerated in tests. |
| MEDIUM | Dynamic plugin-class rebinding conflicted with Ruff and strict Mypy. | Rebinding uses an explicit dynamic module proxy while retaining both static gates. |
| LOW | Fixture wording produced duplicated or awkward prepositions in the sample output. | Reproduction tolerance and insertion-point fixtures were rewritten for direct interview use. |

## Evaluation contract

The response score is 100 points across:

```text
decision correctness                 15
provenance and attribution           15
baseline reproduction                10
module-method traceability           10
semantic compatibility               10
innovation distinctness              15
academic-story coherence             10
fair experiment and ablation         10
expected-result honesty               5
```

Hard blockers override the numerical score when attribution is missing, an unsupported result is represented as observed, or the Agent returns `GO` despite a blocking research condition.

## Corpus evidence

The committed corpus contains eight cases:

- two `GO` cases, including Chinese innovation wording;
- one `REVISE` case for composition-only novelty;
- five `NO_GO` cases covering reproduction, provenance, license, semantic compatibility, and insufficient evidence.

The latest verified corpus digest before this documentation closeout is:

```text
483cba088330236209f3e13791aeeea2402b66c3c108797965bdcb4310c0336f
```

All eight cases matched the expected decision and passed the output-quality rubric.

## Verified engineering evidence

```text
Verified code SHA:     00864c54d4d6809403626624b6ae4e7bf3d3016d
Academic eval run:     29625482433 — SUCCESS
Interview evidence:    29625482423 — SUCCESS
Python 3.11:           Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Python 3.12:           Ruff, format, strict Mypy, tests, branch coverage — SUCCESS
Corpus generation:     8 / 8 passed
Plugin CLI propose:    SUCCESS
Snapshot comparison:   SUCCESS
Artifact ID:           8423691382
Artifact digest:       sha256:3cc61ca4f235107aca5c842c99119fce8cefe9bb099b4b541e9e40dc4b146162
```

The latest PR head must pass the same workflows after this documentation commit.

## Residual conditions

- The source papers and reproduction values are synthetic fixtures, not bibliographic or empirical claims.
- The evaluator measures response handling, not global scientific novelty.
- The proposal path consumes supplied paper cards; real literature retrieval relevance is not evaluated here.
- The novelty guard is deterministic and cannot replace a domain expert or exhaustive prior-art search.
- The eight cases are a development corpus, not a statistically representative benchmark.
- Real-paper reproduction artifacts, external holdout cases, and blinded human scientific review remain future evidence work.
- The PR is stacked and must follow PR #14 and PR #16.

## Decision

```text
Local proposal chain:       READY
Synthetic test data:        READY
Agent evaluation rubric:    READY
Interview evidence:         READY
Code review:                PASS
Scientific release proof:   NOT CLAIMED
Merge order:                PR #14 -> PR #16 -> PR #17
```

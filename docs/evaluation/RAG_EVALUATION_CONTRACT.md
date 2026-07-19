# RAG and Evidence Evaluation Contract

## Purpose

PaperAgent must not treat a plausible final answer as proof that retrieval worked. This contract
separates retrieval, evidence grounding, context use, cost, and workflow terminal behaviour.

## Per-case inputs

Each evaluation case records:

- the complete relevant stable-identifier set;
- ranked retrieved evidence with stable identifiers and context-token counts;
- which evidence items were cited;
- claim-to-evidence support links;
- critical-claim flags;
- total and used context tokens;
- LLM call, token, and estimated-cost telemetry;
- terminal state and an explicit blocker reason when blocked.

Unknown evidence references, duplicate evidence IDs, non-contiguous ranks, blank identifiers,
impossible token accounting, vacuous successful cases, and out-of-range metric values are rejected
before scoring.

## Evidence-domain boundary

Literature citation support and baseline reproduction evidence are different facts.

- A paper citation may support a description of the published method.
- It cannot prove that PaperAgent or the user reproduced that baseline.
- Baseline reproduction must come from trusted server-owned execution metadata, including the
  implementation/version, dataset and environment fingerprints, split, seed policy, metrics, and
  parity result.
- The Gold Case therefore excludes the `baseline-reproduction` fact from literature citation metrics.
  That fact is evaluated by the canonical methodology audit and baseline-reproduction rubric instead.

This prevents a Baseline paper from being counted as evidence that a local training run succeeded.

## Metrics

| Metric | Meaning |
|---|---|
| Recall@K | Fraction of relevant unique sources retrieved within K |
| Precision@K | Fraction of top-K result rows that are relevant |
| Evidence precision | Relevant unique sources divided by all unique retrieved sources |
| Citation support rate | Claims with at least one cited supporting evidence item |
| Unsupported claim rate | Claims without cited support |
| Critical unsupported claims | Zero-tolerance list for critical claims |
| Duplicate-source rate | Repeated stable identifiers beyond the first occurrence |
| Context utilization | Used context tokens divided by available context tokens |
| Calls/tokens/cost | Resource telemetry, not a quality proxy |
| Terminal/blocker distribution | Separates retrieval, synthesis, audit, budget, and provider failures |

## Aggregation

Aggregates are arithmetic means for bounded rates and sums for calls, tokens, and cost. Reports must
use the same K cutoffs before aggregation, but JSON key order is not semantically significant. Case
IDs must be unique so one execution cannot be counted twice. Terminal counts must sum to the number
of cases, and blocker counts cannot exceed it.

Blocker reasons remain categorical counts and must not be collapsed into a generic `failed` bucket.

Recommended blocker taxonomy:

```text
retrieval_no_results
retrieval_low_recall
citation_unverified
baseline_not_reproducible
license_unknown
module_contract_mismatch
method_audit_rejected
synthesis_budget_exhausted
provider_failure
```

## Gold Case report integrity

The Gold Case report contains a SHA-256 digest over its canonical payload. Loading the report
recomputes and verifies that digest, requires the complete acceptance-check set, and verifies that
each check matches the corresponding report field. A modified report cannot be converted into an
interview evidence document while retaining the old digest.

The digest is an integrity binding, not a signature or third-party attestation.

## Gold Case boundary

The bundled NPC Gold Case uses synthetic evidence fixtures and zero LLM calls. Its perfect retrieval
and citation metrics prove that the deterministic contract is wired correctly. They do not prove
real-provider retrieval quality, real-paper correctness, baseline reproduction, novelty, or empirical
performance.
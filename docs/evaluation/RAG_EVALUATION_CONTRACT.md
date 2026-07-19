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

Unknown evidence references, duplicate evidence IDs, non-contiguous ranks, and impossible token
accounting are rejected before scoring.

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
use the same K cutoffs before aggregation. Blocker reasons remain categorical counts and must not be
collapsed into a generic `failed` bucket.

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

## Gold Case boundary

The bundled NPC Gold Case uses synthetic evidence fixtures and zero LLM calls. Its perfect retrieval
and citation metrics prove that the deterministic contract is wired correctly. They do not prove
real-provider retrieval quality, real-paper correctness, baseline reproduction, novelty, or empirical
performance.

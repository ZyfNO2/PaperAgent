# Academic tailoring contract convergence handoff

## Branch

```text
fix/academic-tailoring-contract-convergence
```

This branch is stacked on `fix/gate-l-v3-acceptance-routing`. It must remain Draft and unmerged until the parent branch is reviewed and the scientific behavior is evaluated on a fresh independent holdout.

## Engineering objective

Remove the long-standing split between:

- the production graph method contract;
- deterministic academic-tailoring proposal generation;
- the academic-method plugin audit contract.

All three paths now use the canonical `paperagent.method-plan.v0.9` contract and `paperagent.method-audit.v0.9` deterministic policy.

## Production flow

```text
verified evidence with provenance metadata
→ MethodProposal v0.2
→ canonical MethodPlan v0.9
→ methodology_audit_node
→ GO / REVISE / NO_GO
→ existing bounded quality and repair routing
```

`NO_GO` blocks immediately. `REVISE` may use the existing bounded method-repair loop. A report can continue only after the canonical audit returns `GO` and the remaining evidence and report-safety checks pass.

## Key guarantees

- proposal GO cannot disagree with the canonical audit;
- plugin audit is a thin adapter over the same domain engine;
- plans have stable canonical fingerprints;
- audit traces contain IDs and check outcomes without copying paper content;
- baseline parity, compute fit, provenance, licensing, module execution contracts, strong comparisons, interaction analysis, and fair experiment controls are deterministic gates;
- retrieval metadata such as DOI, arXiv, OpenAlex, provider, and verification state is preserved for downstream methodology work;
- previous import paths and concise report fields remain available through compatibility facades and projections.

## Verification scope

The branch includes regressions for:

- stable and content-sensitive fingerprints;
- plugin/direct audit parity;
- missing baseline parity;
- incomplete module switch, gradient, update, loss-scale, or parity contracts;
- missing strong comparison;
- missing interaction analysis;
- incompatible licenses;
- stable evidence identifiers;
- graph method repair from a safe `REVISE` plan to a valid `GO` plan;
- deterministic corpus and snapshot outputs.

## Explicit non-claims

This work does not execute scientific experiments, validate external repository licenses, replace expert review, or establish scientific acceptance. Prompt and policy changes invalidate previous final-acceptance evidence; a fresh independently authored holdout remains required.

# Academic tailoring technical-debt review

## Review scope

This review compares:

1. the academic tailoring methodology contract maintained for PaperAgent;
2. the production PaperAgent graph, deterministic proposal path, and plugin path;
3. PaperClaw's context-orchestration reference implementation and SOP.

The review is about implementation completeness and contract integrity. It does not claim that any research method, benchmark result, or scientific contribution has been experimentally validated.

## Reference principles

### Academic tailoring methodology

The required workflow is:

```text
research contract
→ verified evidence set
→ frozen and reproduced baseline
→ falsifiable hypothesis
→ attributed module and integration contracts
→ incremental implementation
→ fair comparison and ablation matrix
→ GO / REVISE / NO_GO
→ scientific story and bounded claims
```

The methodology explicitly requires more than tensor-shape compatibility. A reusable module must declare semantics, normalization, masks, ordering, trainability, losses, gradients, parameter update scope, compute, licensing, assumptions, predicted effects, failure modes, and baseline-parity behavior.

Composition is treated as a hypothesis, not novelty. A valid novelty claim requires a supported Problem–Method–Insight relationship and comparisons against a strong attributed alternative. Negative evidence and NO_GO outcomes must be preserved.

### PaperClaw reference architecture

PaperClaw's context-orchestration implementation demonstrates several relevant design rules:

- one canonical versioned contract;
- thin adapters around domain logic;
- deterministic composition and validation;
- stable fingerprints for frozen inputs;
- content-minimized structured traces;
- explicit budget and failure states;
- append-only evidence and execution records;
- compatibility paths that preserve existing callers without duplicating policy.

PaperAgent had adopted several of these ideas in acceptance tooling, but not consistently in the production academic-tailoring workflow.

## Findings

### P0 — Three independent methodology contracts could disagree

Before this repair, PaperAgent implemented academic tailoring in three separate forms:

1. `schemas/method.py` and the main graph quality gate;
2. `academic_tailoring.py` deterministic proposal generation;
3. `plugins/academic_method.py` deterministic audit models and policy.

These paths had different required fields and different verdict logic. The plugin audit was significantly stricter than the production graph. A proposal could therefore be accepted by the main graph while the plugin auditor would return REVISE or NO_GO.

**Impact:** scientific conclusions depended on the entrypoint rather than the evidence and method contract.

**Root cause:** domain policy was embedded in a plugin and duplicated elsewhere instead of being implemented as a shared domain layer.

**Remediation:** introduce `academic_methodology.py` as the canonical contract and deterministic audit engine. Proposal generation, plugin audit, and the main graph consume the same models, policy version, fingerprint, and verdict rules.

### P0 — Main graph quality checks were too shallow

The production quality gate previously checked only that:

- a baseline name existed;
- a hypothesis included a numeric threshold;
- one experiment and one ablation existed;
- stop conditions were present;
- evidence IDs were accepted.

It did not deterministically require:

- a reproduced and frozen baseline;
- modules-disabled baseline parity;
- source version and environment/data fingerprints;
- complete module semantics and training contracts;
- a strong comparison;
- leave-one-out coverage;
- module interaction analysis;
- fair tuning, seeds, uncertainty, resource, and stopping rules across arms.

**Impact:** structurally polished but scientifically incomplete designs could pass the graph.

**Remediation:** add `methodology_audit_node` between method design and the quality gate. The canonical audit is authoritative:

- `NO_GO` blocks;
- `REVISE` uses the existing bounded method-repair loop;
- `GO` permits the remaining report-safety checks.

### P0 — Proposal GO was not tied to the audit contract

The old deterministic proposal generator used a small compatibility denylist and local blocker/risk rules. It did not execute the richer plugin audit before returning GO.

**Impact:** proposal and audit results could diverge for the same design.

**Remediation:** proposal generation now constructs a canonical `MethodPlan`, runs `audit_method_plan`, and cannot return GO unless the canonical audit is also GO. The proposal records the audit verdict, failed checks, plan fingerprint, and proposal fingerprint.

### P1 — Compatibility was partially inferred from free-form strings

The old proposal path primarily rejected a small set of values such as `shape-only`, `reshape`, or `tensor`. A detailed-sounding string could therefore pass without an executable contract.

**Impact:** semantic or training incompatibility could be hidden behind plausible prose.

**Remediation:** require explicit fields for:

- input and output semantics;
- shapes;
- normalization;
- masks;
- ordering;
- trainability and losses;
- configuration switch;
- expected gradients;
- parameter update scope;
- loss scale;
- baseline-parity behavior;
- assumptions, cost, effect, and failure mode.

A shape-compatible but incomplete module now receives REVISE.

### P1 — Strong comparison and interaction analysis were optional

The previous deterministic experiment generator created baseline, single-module, full, and leave-one-out arms, but did not require a strong attributed comparison or an explicit interaction contrast.

**Impact:** a method could appear effective relative to a weak baseline while avoiding the strongest relevant alternative, and multi-module synergy could be asserted from the full arm alone.

**Remediation:** the canonical audit requires:

- at least one attributed strong-comparison arm with verified provenance;
- explicit interaction analysis for multi-module plans;
- the same data, split, preprocessing, tuning budget, metrics, seeds, uncertainty, resources, and stopping rules across comparison arms.

### P1 — Retrieval provenance was discarded before methodology design

Literature providers supplied DOI, arXiv, OpenAlex, Semantic Scholar, provider, and verification metadata. The evidence-verification layer retained only a title, locator, summary, and content hash.

**Impact:** downstream methodology code could not construct a complete evidence ledger or stable source identity without guessing from the locator.

**Remediation:** `EvidenceItem` now retains provider and metadata and exposes a deterministic stable identifier preference order. Verification merges metadata instead of dropping it.

### P1 — No stable methodology fingerprint or content-minimized audit trace

The plugin returned a verdict but did not provide a stable canonical plan identity or a trace suitable for comparing proposal, plugin, graph, and acceptance evidence.

**Impact:** it was difficult to prove that two verdicts referred to the same method plan or to detect post-audit mutation.

**Remediation:** canonical JSON fingerprints cover the complete method plan. The audit trace contains contract/policy versions, fingerprint, check IDs, evidence IDs, module IDs, and experiment IDs, but does not copy paper titles, summaries, or full source content.

### P1 — Baseline parity existed in theory but not in production contracts

The methodology requires implementing each modification behind an explicit switch and verifying that disabling all modifications reproduces the frozen baseline. The previous graph and proposal schema did not carry this information.

**Impact:** improvements could be caused by unrelated preprocessing, evaluation, or baseline drift.

**Remediation:** baseline and module contracts now include baseline parity. GO requires a verified modules-disabled baseline path.

### P2 — Legacy report fields and canonical methodology fields can drift

The existing report and interview surfaces consume concise method fields. Removing them immediately would create broad compatibility risk.

**Remediation:** `MethodProposal` v0.2 retains the legacy summary fields but requires a canonical `methodology_plan`. Model validation ensures that module IDs, evidence IDs, and stop conditions agree. The canonical plan is authoritative; legacy fields are a compatibility/readability projection.

### P2 — Synthetic evaluation corpus did not test the full methodology

The NPC corpus previously lacked baseline parity, environment/data fingerprints, complete module training contracts, a strong comparison paper, and an interaction arm.

**Remediation:** the corpus now includes those contracts. The evaluation path runs the canonical audit, and synthetic evidence remains explicitly non-release evidence.

## Implemented architecture

```text
retrieval providers
        ↓
verified EvidenceBundle with stable metadata
        ↓
method-design LLM returns MethodProposal v0.2
        ├─ concise legacy/report projection
        └─ canonical MethodPlan v0.9
                    ↓
          methodology_audit_node
                    ↓
              GO / REVISE / NO_GO
                    ↓
             existing quality gate
```

The deterministic proposal and plugin paths use the same domain layer:

```text
TailoringTask
    ↓
canonical MethodPlan
    ↓
audit_method_plan
    ↓
TailoredResearchProposal + fingerprints + audit trace

Plugin audit
    ↓
thin adapter over audit_method_plan
```

## Compatibility and migration boundaries

- Existing `paperagent.academic_tailoring` imports remain valid through a re-export facade.
- Existing plugin audit imports remain valid through re-exports from the canonical domain.
- Existing report fields remain present in `MethodProposal` v0.2.
- Method-design prompt version changes to `method_design.v0.2.0`.
- Previous holdout results cannot validate the new scientific behavior. A fresh independent holdout is required after this branch is stabilized.

## Deferred work

The following work is intentionally not disguised as completed:

1. **Trust-separated prompt assembly.** PaperClaw builds context from trust-labelled sources under explicit overflow policy. PaperAgent now preserves source provenance but still sends a comparatively monolithic evidence payload to the method-design model.
2. **Execution-level experiment runner.** The canonical contract designs fair experiments but does not execute training jobs or verify observed metrics.
3. **Real repository/license verification.** The audit validates recorded evidence and license status; external legal or repository verification remains a separate evidence acquisition responsibility.
4. **Human scientific review.** Deterministic checks do not replace domain-expert review or independent reproduction.
5. **Fresh Gate L holdout.** Prompt and production-policy changes require a new independently authored unseen corpus.

## Release recommendation

This branch should remain Draft until:

- Ruff, strict Mypy, and full tests pass on Python 3.11 and 3.12;
- graph happy, OOD, retrieval-repair, method-repair, and blocked fixtures pass;
- plugin, proposal, and graph audits demonstrate fingerprint/verdict convergence;
- all temporary development workflows are removed;
- the new scientific behavior is evaluated on a fresh independent holdout.

The correct current status is **engineering remediation**, not scientific PASS.

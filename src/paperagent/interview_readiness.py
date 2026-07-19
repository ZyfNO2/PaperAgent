from __future__ import annotations

from paperagent.gold_case import GoldCaseReport


def render_interview_readiness(report: GoldCaseReport) -> str:
    checks = "\n".join(
        f"- {'PASS' if passed else 'FAIL'}: `{name}`"
        for name, passed in sorted(report.acceptance_checks.items())
    )
    limitations = "\n".join(f"- {item}" for item in report.limitations)
    return f"""# PaperAgent Interview Readiness Evidence

## Evidence identity

- Gold Case contract: `{report.contract_version}`
- Case: `{report.case_id}`
- Report digest: `{report.report_digest}`
- Status: **{report.status.upper()}**
- Scientific acceptance: **NOT CLAIMED**

## 30-second project pitch

PaperAgent is a bounded research workflow that separates literature evidence, baseline facts,
method contracts, deterministic methodology audit, and final GO / REVISE / NO_GO routing. The
Gold Case demonstrates that one complete game-AI research design can pass the same canonical
contract from proposal construction through audit and evidence-layer evaluation, while preserving
an explicit synthetic-only boundary.

## Source-to-decision chain

```text
NPC research contract
→ attributed synthetic evidence cards
→ frozen baseline reproduction contract
→ action-mask and residual-policy module contracts
→ canonical methodology audit
→ GO / REVISE / NO_GO decision
→ RAG/evidence metrics
→ interview evidence report
```

## Gold Case result

- Proposal decision: `{report.proposal_decision}`
- Canonical audit verdict: `{report.audit_verdict}`
- Rubric score: `{report.grade_score}` (minimum `{report.minimum_score}`)
- Evidence scope: `{report.evidence_scope}`
- Readiness: `{report.readiness}`
- Scientific release ready: `{str(report.scientific_release_ready).lower()}`
- Recall@5: `{report.rag.recall_at_k['5']:.3f}`
- Citation support rate: `{report.rag.citation_support_rate:.3f}`
- Unsupported claim rate: `{report.rag.unsupported_claim_rate:.3f}`

## Acceptance checks

{checks}

## High-value interview questions

### Why is this not just A+B+C module stacking?

The proposal binds each borrowed component to a different failure mechanism, an explicit insertion
point, semantic and optimization contracts, a feature switch, predicted effects, and ablations that
can falsify the explanation. Composition alone is not treated as novelty.

### How do you prevent the model from inventing provenance or baseline results?

Stable identifiers, licenses, verification state, baseline reproduction facts, fingerprints, and
audit verdicts are server-owned typed fields. The model cannot promote unverified evidence or
self-report a successful baseline into a GO decision.

### How do you evaluate retrieval separately from final text quality?

The evaluator reports Recall@K, Precision@K, evidence precision, citation support, unsupported
claims, duplicate-source rate, context utilization, token counts, cost, terminal state, and blocker
reason. This distinguishes retrieval failure from synthesis or methodology-audit failure.

### What real engineering problem did you solve?

Earlier paths could disagree about GO / REVISE / NO_GO. The implementation converged the graph,
deterministic proposal path, and plugin onto one canonical method-plan and audit contract, then
added stable fingerprints and tests for evidence, baseline, compatibility, and verdict binding.

## Limits to state explicitly

{limitations}

## Recommended live demonstration

1. Run `python scripts/run_gold_case_readiness.py --output build/gold-case/report.json`.
2. Show the generated decision, audit verdict, rubric score, RAG metrics, and digest.
3. Explain one negative case by changing baseline reproduction, evidence verification, license, or
   compatibility and showing fail-closed NO_GO/REVISE behavior.
4. State that the deterministic Gold Case is engineering evidence, not real scientific validation.
"""

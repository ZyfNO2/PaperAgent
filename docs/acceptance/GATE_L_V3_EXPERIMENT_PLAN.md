# Gate L v3 multi-strategy experiment plan

## Status

The engineering framework for Gate L v3 exists, but no formal scientific holdout has been frozen or executed. Historical v1/v2 material is diagnostic-only.

The current authoritative procedure is:

- `docs/acceptance/GATE_L_V3_FORMAL_RUNBOOK.md`;
- `scripts/gate_l_formal_contract.py`;
- `scripts/run_gate_l_formal.py`;
- `scripts/assemble_gate_l_v3_summary.py`;
- `scripts/gate_l_acceptance_v3.py`.

## Experiment sequence

1. An independent owner authors a new 16-case `v3-*` holdout and attestation.
2. The project freezes one final scientific-behaviour commit.
3. The formal contract binds the exact SHA, cases, prompts, policy versions, implementation files, strategy profiles, price tables, and thresholds.
4. Each predeclared strategy is executed independently against the same frozen holdout.
5. Deterministic evidence audits are assembled without changing prompts, rules, or routing.
6. Strategy comparison is exploratory and may only produce a provisional routing recommendation.
7. Any selected routing policy is frozen before a separate unseen confirmation holdout.
8. Two independent human experts review blinded outputs; all disagreements are adjudicated and pre-adjudication agreement is reported.

## Strategy comparison boundary

The existing strategy templates remain configuration examples, not frozen experiment arms. A formal arm must use a committed profile with real provider, model, base URL, price-table path, and bounded environment overrides. Credentials must remain outside the profile.

A strategy result is invalid when it uses:

- another repository SHA;
- an unbound strategy or price table;
- a modified prompt, policy, grader, or behaviour file;
- a dirty tree;
- a case filter;
- missing token, cost, latency, source, output, or trace evidence.

## Routing boundary

Selecting the best strategy on the primary holdout is exploratory. It must be recorded as `PROVISIONAL_REQUIRES_FRESH_CONFIRMATION`. The routing rule cannot be called accepted until it passes a newly authored unseen confirmation holdout under the same formal evidence requirements.

## Current decision

```text
Formal holdout:             PENDING
Formal contract freeze:     PENDING
Real-provider variants:     PENDING
Provisional strategy route: PENDING
Fresh confirmation:         PENDING
Blinded expert review:      PENDING
Gate L:                     INCOMPLETE
```

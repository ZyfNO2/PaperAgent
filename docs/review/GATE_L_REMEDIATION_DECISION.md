# Gate L remediation decision

## Decision

Do **not** weaken the scientific quality gate. Keep `minimum_accepted_items=1` for each genuinely required evidence gap.

The remediation changes planning and retrieval behavior instead:

1. limit hard-required evidence gaps to the scientifically indispensable set;
2. fail closed when indispensable evidence cannot be recovered from public retrieval;
3. broaden retrieval only when the primary providers return zero verified evidence;
4. capture per-gap diagnostic evidence before any further acceptance tuning.

Because the planning prompt/rules changed, the existing frozen holdout v1 is now **diagnostic-only**. A fresh holdout version must be frozen after the remediation stabilizes before Gate L can be used for a final scientific release decision.

## Plan A — strict core-gap retrieval (default)

Use this for normal research tasks.

- Planner marks only 2-4 scientifically indispensable gaps as `required=true`.
- Secondary background, context, and nice-to-have evidence remain optional.
- Each required gap keeps `minimum_accepted_items >= 1` and has at least one focused search query.
- Primary retrieval remains OpenAlex + Semantic Scholar.
- If a query returns zero verified papers, Gate L diagnostics may use an opt-in arXiv + OpenAlex fallback.
- Quality Gate semantics remain unchanged: an uncovered required gap still blocks or triggers bounded repair.

This is the default remediation because it fixes the mismatch between a bounded retrieval budget and plans that previously generated too many hard requirements without lowering scientific rigor.

## Plan B — calibrated insufficient-evidence path

Use this when the missing evidence cannot be obtained by public literature search.

Examples include:

- exact p-values or confidence intervals without observations or summary statistics;
- unnamed private/unpublished systems with no metrics, logs, datasets, or outputs;
- anonymous treatment anecdotes without protocol or safety monitoring;
- requests to confirm global novelty without a defensible related-work evidence set;
- hidden benchmark answers, grader notes, credentials, or private fixtures.

Expected behavior:

- return `blocked` with a specific evidence-deficiency reason;
- enumerate the minimum recovery inputs;
- do not fabricate values or claims;
- do not create meaningless required retrieval gaps for evidence that cannot exist in public search;
- use `need_human` only when one concrete human-supplied fact can legitimately unlock the task.

This is the intended path for `holdout-v1-insufficient-003` (Case 11: ranking unpublished systems without metrics). The case should not burn retrieval rounds trying to discover unnamed private systems.

## Plan C — delegated retrieval/subagent expansion (deferred contingency)

If Plans A/B still leave material recall failures after targeted diagnostics, introduce a bounded retrieval-worker layer rather than weakening the gate.

Reference patterns:

- AgentLaboratory: staged research workflow and explicit phase boundaries;
- AutoResearchClaw: real-source retrieval, citation validation, HITL checkpoints, and artifact-driven research stages;
- auto-deep-researcher-24x7: leader-worker decomposition for parallel research;
- PaperClaw: parent-child/subagent execution with task envelopes, scoped tools, isolated context, and artifact-first return values.

Candidate PaperAgent design:

- parent planner owns the final scientific decision;
- child retrieval workers receive one evidence gap each;
- workers search different provider/query strategies in isolated context;
- workers return only structured evidence artifacts and provenance;
- parent deduplicates, verifies identifiers, and updates `coverage_by_gap`;
- retries remain bounded by calls/time/cost;
- no worker may modify the expected Gate L label or inspect hidden holdout/grader data.

Plan C is intentionally not enabled yet. It adds concurrency and orchestration complexity and should only be introduced if diagnostics prove that provider/query diversity, rather than planning calibration, is the remaining bottleneck.

## Case 11 targeted diagnosis

Run only the previously stuck case:

```bash
python scripts/run_gate_l_final.py --case-id holdout-v1-insufficient-003
```

The output now records:

- planning status;
- required gap count and query IDs;
- retrieval round/budget state;
- completed queries and tool errors;
- accepted/pending/rejected/failed verification counts;
- `coverage_by_gap`;
- Quality Gate verdict, reason codes, and missing gap IDs;
- LLM calls/tokens/latency and hard timeout.

This distinguishes a semantic routing failure from provider failure, retrieval miss, verification failure, or resource exhaustion.

## Acceptance sequence after remediation

1. Run Case 11 alone and inspect the new scientific trace.
2. Run one representative normal in-domain/OOD case to validate Plan A.
3. Run representative insufficient/adversarial cases to validate Plan B and fail-closed behavior.
4. Only then run the full diagnostic v1 set.
5. Freeze prompt/rules/retrieval configuration.
6. Author and freeze a new holdout version (v2) not used during remediation.
7. Execute v2 with real providers and immutable evidence artifacts.
8. Complete two-reviewer blinded expert scoring, disagreement adjudication, and inter-rater agreement.

A successful diagnostic v1 rerun does not itself constitute Gate L scientific acceptance.

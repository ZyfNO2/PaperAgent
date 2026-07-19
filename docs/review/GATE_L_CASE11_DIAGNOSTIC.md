# Gate L Case 11 targeted diagnostic

## Scope

This record documents a one-shot real-provider diagnostic for:

- Case: `holdout-v1-insufficient-003`
- Title: Ranking unpublished systems without metrics
- Category: `insufficient_evidence`
- Purpose: verify that the remediated planning policy fails closed instead of wasting retrieval rounds on unnamed private/unpublished systems.

This is **diagnostic evidence only**. Holdout v1 was invalidated for final Gate L acceptance after the planning prompt/rules changed to `planning.v0.1.2`. A newly frozen holdout version is still required for formal scientific acceptance.

## Execution identity

- Branch: `scientific-gate-l`
- Source head SHA: `697741381374010745c58155f0cf5f5f78a65cbe`
- GitHub Actions run: `29648936448`
- Workflow: Gate L Case 11 One-shot Diagnostic
- Provider: `mistral`
- Model: `mistral-small-latest`
- Artifact ID: `8430885243`
- Artifact digest: `sha256:327e105d3f008f757684d2ce77ebda3d035a751ec7c47f02eac6e42820b57411`
- Holdout v1 digest: `41d45dd1cfa61511297a0012699177c006ac6db566d2062b2bea3e0a7617c585`

The workflow was bounded to 6 LLM calls, 10,000 input tokens, 10,000 task output tokens, $1.25 estimated cost, and 120 seconds task wall time. The repository secret was consumed only through the GitHub Actions environment and was not written to artifacts.

## Observed result

```text
terminal:                  blocked
wall_seconds:              7.46
LLM calls:                 2
input tokens:              836
output tokens:             1090
total telemetry tokens:    1926
budget violations:         0
timeouts:                  0
provider errors:           0
retrieval round:            0
completed retrieval query: 0
accepted evidence:         0
```

Node calls:

```text
planning: 1 call, ~6.0s
report:   1 call, ~1.4s
```

The planner produced `plan_status=blocked`. Although the structured plan contained 3 required evidence gaps and 4 candidate search queries, the graph correctly routed the blocked plan directly to reporting. No literature retrieval was attempted, no query was marked completed, and no retrieval budget was consumed.

## Interpretation

The previous Case 11 hang/kill was not evidence that this task intrinsically needs a long retrieval pipeline. Under the remediated policy, this task terminates quickly and fail-closed because the requested ranking cannot be supported from public literature retrieval when the systems, datasets, metrics, seeds, compute, logs, and outputs are unavailable.

This validates the intended **Plan B — calibrated insufficient-evidence path** for this diagnostic case:

1. do not fabricate a ranking or metric;
2. do not search for unnamed private systems as if public evidence could repair the missing inputs;
3. block safely and report the missing comparison requirements;
4. avoid unnecessary retrieval rounds and budget exhaustion.

It does **not** establish that all insufficient-evidence cases pass the formal Gate L rubric, nor does it establish scientific release readiness.

## Evidence integrity note

An earlier one-shot workflow attempt incorrectly piped the Python process through `tee` without fail-closed shell semantics and produced no valid per-case evidence. That attempt was rejected and not counted. A second attempt correctly surfaced an undeclared `python-dotenv` dependency in the runner; the runner was fixed so `.env` loading is optional and CI can rely directly on environment variables. The successful execution above is the first accepted Case 11 diagnostic record after those harness fixes.

## Next acceptance step

1. Keep the current quality-gate requirement; do not lower `minimum_accepted_items=1` for genuinely required gaps.
2. Use holdout v1 only for remediation diagnostics.
3. Freeze prompt/rules/retrieval configuration once remediation is stable.
4. Author and freeze a new unseen holdout v2.
5. Execute v2 against real providers with immutable artifacts.
6. Complete two independent blinded expert reviews, disagreement adjudication, and inter-rater agreement before declaring Gate L complete.

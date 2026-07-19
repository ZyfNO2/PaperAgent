# Gate L v2 execution postmortem

## Disposition

```text
Reported automated decision: FAIL
Formal scientific disposition: INCOMPLETE
Evidence status: INVALID_FOR_FORMAL_ACCEPTANCE
Source commit: 7158e5ef60963646eeb5c8c422d36888db562333
```

The original evidence must remain immutable as diagnostic material. It must not be relabeled, edited, or rescored into a passing formal result after the outputs have been observed.

## Observed result

- 16 per-case files were collected across local executions.
- Terminal summary reported by the operator: 15 `blocked`, 1 `failed`, 0 `succeeded`.
- The generated decision reported 0/16 accepted.
- The single failed case exhausted its budget and failed closed.

These observations are useful for debugging, but they do not constitute one coherent formal Gate L execution.

## Invalidating findings

### 1. Frozen terminal contract was wrong

Every v2 case declared `expected_terminal = succeeded`. This conflated two distinct concepts:

- workflow terminal: `succeeded / blocked / failed / need_human`;
- scientific decision: `GO / REVISE / NO_GO`.

For evidence-insufficient and adversarial tasks, a calibrated `blocked` workflow terminal can be correct. A correct formal contract must predeclare an allowed terminal set before execution. It cannot be widened after observing model output.

### 2. Temporary deterministic logic contradicted the final scorer

The temporary summary treated every `blocked` result as `passed=true`. The final scorer then independently required exact equality with the frozen `expected_terminal`, causing every blocked case to fail acceptance. The two stages therefore implemented different terminal semantics.

### 3. Human review evidence was synthetic

`review-a-stub.json` and `review-b-stub.json` were produced by one script. Both used the same reviewer identity, the same `REVISE` labels, and identical fixed scores. The resulting Cohen's kappa of 1.0 validates only the score pipeline mechanics; it is not evidence of independent blinded expert agreement.

### 4. The committed run record is not a full formal run

The committed `build/gate-l-v2-final/run-record.json` records:

```text
case_count: 1
formal_run: false
formal_execution_eligible: false
clean_tree: false
selected case: holdout-v2-adversarial-016
```

The 16 per-case files were accumulated across multiple local invocations. They cannot be represented as one immutable formal run with one execution identity by a final single-case run record.

### 5. Not-applicable repair metrics were converted into failure

There were no applicable repair attempts, but the temporary summary emitted `repair_success_rate = 0.0`. The scorer treated this as below the 80% threshold. In the successor contract, zero attempts are represented as `N/A`; the threshold applies only when repair attempts exist.

## Required successor behavior

Gate L v3 introduces:

1. `expected_terminals: [...]` frozen per case;
2. exact 16-case formal run integrity checks;
3. one immutable execution identity per variant;
4. deterministic evidence summaries that fail closed on incomplete provenance;
5. explicit `repair_attempts` and `repair_successes`, with zero attempts treated as not applicable;
6. distinct human reviewer identities and independence attestations;
7. rejection of synthetic/stub reviews as formal evidence;
8. provider/model/strategy comparison without silently pooling runs;
9. provisional domain routing followed by a fresh confirmation holdout.

## v2 preservation rule

The v2 files remain available only for:

- runtime debugging;
- terminal-policy diagnosis;
- budget behavior analysis;
- evidence-package UI inspection;
- regression tests proving that incomplete or synthetic evidence is rejected.

They must not be used to claim Gate L PASS or final scientific acceptance.

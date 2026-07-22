# TODO: Real LLM Test Fast-Fail Error Reporting

## Status

`PARTIAL EXISTS / NEEDS HARDENING`

The `run_academic_tailoring_retrieval_v1.py` runner has basic fast-fatal logic, but the behavior is inconsistent across runners and insufficient for multi-provider production use.

## Current Fast-Fatal Behavior

### `run_academic_tailoring_retrieval_v1.py` (partial)

Located at `scripts/run_academic_tailoring_retrieval_v1.py:446-477`:

```python
except ProviderError as exc:
    normalized = _normalize_provider_error_code(exc.error_code) or exc.code
    errors.append(...)
    if normalized in _FATAL_PROVIDER_ERROR_CODES:
        fatal_provider_error = {...}
        break  # ← stops the whole run
except Exception as exc:
    normalized = _normalize_provider_error_code(getattr(exc, "code", None))
    errors.append(...)
    if normalized in _FATAL_PROVIDER_ERROR_CODES:
        fatal_provider_error = {...}
        break
```

**What works:**
- Fatal provider errors (AUTHENTICATION, PERMISSION, RATE_LIMITED, READ_TIMEOUT, CANCELLED, UNKNOWN, CONFIGURATION) → break
- Per-case error recording
- Progress printed after each case (line 481-495)

**What's missing:**

1. **No structured error classification in output** — errors are appended as raw dicts but the final summary doesn't distinguish between:
   - Fatal vs recoverable
   - Provider error vs application error
   - Budget exhaustion vs timeout vs auth failure

2. **No per-case error context** — when `break` happens, you know which case failed but not:
   - Which LLM call failed (call index)
   - What stage (planning / retrieval / synthesis / quality_gate)
   - Whether the error is retryable

3. **No provider identity in error** — with multi-provider routing, "auth failure on NVIDIA key A" and "auth failure on Mistral" require different operator actions. Current errors don't record which endpoint/provider failed.

4. **No cost-at-failure tracking** — when a run breaks at case 7/10, you don't know how much budget was consumed before failure.

5. **No checkpoint resume** — `persist_checkpoint()` is called after each case but there's no `--resume-from` flag to skip completed cases. A fatal error at case 8 means re-running cases 1-7 wastes budget.

### `run_claw_academic_runtime.py` (weaker)

Located at `scripts/run_claw_academic_runtime.py:222-239`:

```python
except Exception as exc:
    errors.append({"case_id": case.case_id, "error_type": type(exc).__name__, "message": str(exc)})
    continue  # ← keeps going, no fatal classification
```

**Problem:** ALL errors are `continue`. A fatal auth error on case 1 still runs cases 2-10, burning budget pointlessly.

## Required Behavior

### 1. Unified Error Classification

Every runner must classify errors into:

| Category | Action | Examples |
|----------|--------|----------|
| `FATAL_PROVIDER` | break immediately | auth failure, permission denied, invalid config |
| `FATAL_BUDGET` | break immediately | cost cap reached, token budget exhausted |
| `CASE_ERROR` | continue to next case | single case timeout, malformed output, repair exhaustion |
| `RETRYABLE` | retry with backoff | rate limit, 5xx, transient network |

### 2. Structured Error Output

Each error record must include:

```json
{
  "case_id": "...",
  "stage": "planning|retrieval|synthesis|quality_gate",
  "call_index": 3,
  "provider": "nvidia",
  "model": "meta/llama-3.1-8b-instruct",
  "endpoint_id": "nvidia-primary",
  "error_code": "LLM_AUTHENTICATION",
  "error_category": "FATAL_PROVIDER",
  "message": "...",
  "retryable": false,
  "budget_consumed_usd": 0.012,
  "timestamp": "..."
}
```

### 3. Run Summary Error Section

```json
{
  "error_summary": {
    "total_errors": 3,
    "fatal_errors": 1,
    "case_errors": 2,
    "by_provider": {
      "nvidia": {"fatal": 1, "retryable": 0},
      "mistral": {"fatal": 0, "retryable": 2}
    },
    "by_category": {
      "FATAL_PROVIDER": 1,
      "RETRYABLE": 2
    },
    "first_fatal_at": {"case_id": "atr-v1-006", "case_index": 6},
    "budget_consumed_before_fatal_usd": 0.021
  }
}
```

### 4. Resume Support

- `--resume-from <case_id>` — skip already-completed cases
- Checkpoint file records completed case IDs
- On resume, validate checkpoint integrity (schema version, dataset digest match)

### 5. Multi-Provider Error Attribution

When using `RoutingLLMProvider`, errors must propagate:
- Which endpoint was active when the error occurred
- Whether the error triggered a fallback
- Per-endpoint error counts in final summary

## Sequencing

1. Unify error classification in both runners
2. Add structured error output with stage + provider + endpoint
3. Add `--resume-from` support
4. Add per-endpoint error attribution for router integration
5. Add cost-at-failure tracking

## Scope

- In scope: error classification, structured output, resume, attribution
- Out of scope: automatic retry policies, circuit breaker integration (separate TODO)

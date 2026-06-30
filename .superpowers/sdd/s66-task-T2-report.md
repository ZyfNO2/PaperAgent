# Session 66 — Task T2 Report

## T2: Fix candidate_cleaner — LLM failure returns needs_manual not keep

**Date:** 2026-07-01
**File:** `apps/api/app/services/retrieval/candidate_cleaner.py`

## Problem

`_llm_refine()` previously returned `clean_status="keep"` when the LLM was unavailable
or raised an exception. This silently let unvalidated candidates through to the
evidence pipeline without human review.

## Fix

Both failure paths in `_llm_refine()` now return `needs_manual`:

| Failure | Before | After |
|---------|--------|-------|
| `LLMUnavailable` | `clean_status="keep"`, confidence=0.5 | `clean_status="needs_manual"`, confidence=0.0 |
| `Exception` (parse/network) | `clean_status="keep"`, confidence=0.5 | `clean_status="needs_manual"`, confidence=0.0 |

Both branches now share the same shape:

```python
return CandidateCleanResult(
    candidate_id=cid,
    clean_status="needs_manual",
    mismatch_type="low_relevance",
    matched_atoms=matched,
    missing_required_atoms=[a for a in required if a not in matched],
    reason=f"LLM unavailable; manual review required before using as evidence: {exc}",
    confidence=0.0,
)
```

## Prompt schema update

The LLM prompt JSON schema now lists all four statuses (the model can
self-report `needs_manual` if it is uncertain):

```
"clean_status": "keep|quarantine|reject|needs_manual"
```

## Post-parse validation

The status whitelist at line 259 now accepts all four values instead of
restricting to `keep|quarantine`. Mismatch whitelist already included
`low_relevance`, which is what both error branches set.

## Docstring update

`_llm_refine` docstring updated from "失败则降级为 keep" → "失败则返回 needs_manual".

## Tests

- `apps/api/tests/test_session64_candidate_cleaner.py` — **14 passed**

The hard-rule tests (AGN / German survey / MLPerf rejection, civil domain
keep) are unaffected because `_hard_rule_check` returns before LLM is
called. The new behavior only changes the LLM-failure fallback.

## Effect on evidence pipeline

`needs_manual` candidates now stay out of the default "kept" set and must
be explicitly reviewed by a human or via a future re-run of
`clean_candidates` with an LLM available. This prevents the worst-case
silently-bad-evidence failure mode.

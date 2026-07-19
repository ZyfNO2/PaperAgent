# Academic Tailoring Code Review — Evidence and Audit Hardening

## Review disposition

```text
Scope: PR #21 canonical methodology integration
Fix branch: fix/academic-tailoring-review-hardening
Fix PR: #22
Merge status: not requested
Scientific acceptance: not claimed
```

This review targeted paths that could pass unit and integration tests while still allowing provenance or execution-state laundering in a real LLM-driven workflow.

## P0 — Locator syntax was treated as verification

### Trigger

A search candidate had an HTTP, HTTPS, DOI, or GitHub-style locator but no positive status from the trusted literature verification pipeline.

### Impact

A hallucinated locator could become accepted evidence and then be represented as verified provenance in the canonical methodology audit.

### Fix

Positive remote verification is accepted only from the trusted literature retrieval service with an explicit verified status. Untrusted remote candidates remain pending. The deterministic fake provider is accepted only for explicit `fixture://` records.

## P0 — Explicit rejection could not revoke acceptance

### Trigger

The same evidence ID was accepted in an earlier retrieval round and explicitly rejected later.

### Impact

The merge priority kept the earlier acceptance, so invalidated evidence could continue contributing coverage and methodology provenance.

### Fix

Explicit rejection now dominates accepted, pending, and failed-verification states. Evidence content drift also creates a conflict and revokes acceptance instead of silently overwriting the prior record.

## P0 — Method Design could author provenance

### Trigger

The model selected an accepted evidence ID but returned its own title, stable identifier, hash, license, repository reference, verification flag, or supported claims.

### Impact

ID-only validation allowed model-authored provenance fields to pass even though those fields were not included in the method-design input.

### Fix

Method Design receives a server-owned accepted evidence ledger. A post-parse binding step replaces all provenance and supported-claim fields with server-owned retrieval and synthesis data before semantic validation and telemetry.

## P0 — Baseline execution facts were model-authored

### Trigger

The method proposal declared `reproduced=true`, a reproduced metric, compute fit, modules-disabled parity, or dataset/environment fingerprints without server-owned execution metadata.

### Impact

A fully populated proposal could reach GO even when no baseline reproduction or parity run had occurred.

### Fix

These fields are now overwritten from accepted evidence metadata. Missing server metadata clears the model declarations and yields REVISE. Explicit `compute_fit=false` remains a critical NO_GO condition, while unknown compute fit is repairable.

## P1 — Stale methodology audits could be reused

### Trigger

A `MethodPlan` changed while an earlier `MethodAuditReport` remained in state.

### Impact

Quality routing could use a GO audit produced for a different plan.

### Fix

Quality Gate verifies contract version, policy version, and plan fingerprint. Missing or stale audits are recomputed and persisted before routing.

## P1 — Audit reports lacked internal invariants

### Trigger

A serialized audit report contained mismatched top-level and trace fingerprints, versions, check IDs, or passed/failed sets.

### Impact

Tampered or stale audit components could deserialize as a valid report.

### Fix

`MethodAuditReport` now validates internal agreement between checks, trace, versions, and fingerprints.

## P1 — Proposal fingerprint omitted substantive content

### Trigger

Proposal wording, targets, risk statements, or other content changed while IDs and decision remained constant.

### Impact

Different proposals could share the same proposal fingerprint.

### Fix

The proposal fingerprint now covers the complete task, generated proposal content, canonical plan fingerprint, and audit result.

## Verification requirements

The fix is considered engineering-complete only when all of the following pass on the final ordinary commit:

- Ruff lint and format;
- strict Mypy on Python 3.11 and 3.12;
- full Pytest and branch coverage;
- academic-tailoring corpus generation and Plugin propose path;
- installed-wheel and external-plugin smoke;
- durable-state roundtrip, deterministic demo, OpenAPI export, and repository benchmark.

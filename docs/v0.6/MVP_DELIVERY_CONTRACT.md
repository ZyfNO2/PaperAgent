# PaperAgent v0.6 MVP Delivery Contract

## Status

`IMPLEMENTED OFFLINE / LIVE MISTRAL AND SCIENTIFIC QUALITY PENDING`

This contract narrows the broader v0.6 execution plan into the minimum shippable real-LLM milestone. It does not replace `EXECUTION_PLAN.md`; it defines the MVP boundary used by the v0.7 and v0.8 follow-on work.

## Product goal

PaperAgent can run the existing bounded research workflow through one explicitly configured real Mistral provider while preserving deterministic demo behavior, typed failure handling, strict structured outputs, resource budgets, redacted telemetry, and the existing review/export path.

## MVP deliverables

1. Provider-neutral runtime configuration loaded from CLI, environment variables, and safe defaults.
2. Mistral structured-output adapter behind the frozen `LLMProvider` protocol.
3. Strict Pydantic validation, bounded transient retry, and at most one schema-repair call.
4. Per-task call, token, wall-clock, and optional monetary budgets.
5. Redacted invocation telemetry with stable logical-call and physical-attempt identifiers.
6. Explicit `demo` versus `real` executor selection.
7. Readiness diagnostics that do not make billable calls or expose credentials.
8. Deterministic evaluation contracts, a 48-case development corpus, run manifests, and case-level reports.
9. Opt-in live Mistral smoke for all four production schemas.
10. Existing API, PWA, SQLite, cancellation, review, export, wheel, browser, and Docker regressions preserved.

## Acceptance boundary

### Offline engineering gate

- Ruff, Ruff format, strict Mypy, and the default test suite pass on Python 3.11 and 3.12.
- Combined line/branch coverage remains at or above 90%.
- Fake-provider and deterministic demo semantics remain unchanged.
- Every provider failure maps to a typed and redacted error.
- Retry and repair attempts consume the physical-call budget.
- The development evaluation corpus contains exactly 12 cases in each required family.

### Live gate

- A configured Mistral model returns schema-valid outputs for `ResearchPlan`, `EvidenceSynthesis`, `MethodProposal`, and `FinalReport`.
- Three complete real vertical runs finish without manual state repair.
- Authentication, permission, unsupported-schema, and exhausted-budget failures are not retried.
- Live artifacts contain no API keys, authorization headers, raw chain-of-thought, or unredacted provider payloads.

### Scientific-quality gate

- Non-adversarial task success is at least 85%.
- OOD task success is at least 80%.
- Accepted citation identifier validity is 100%.
- Deterministically scorable claim-to-evidence precision is at least 90%.
- Critical secret, fixture, or prompt-injection violations are zero.
- Failed cases remain preserved and are not rewritten into passing observations.

## Explicitly out of scope

- full-text PDF ingestion, OCR, embeddings, or vector databases;
- multi-provider routing or automatic provider fallback;
- remote plugin installation;
- user accounts, authentication, billing, tenancy, or public deployment approval;
- autonomous external writes or paper submission;
- raw chain-of-thought persistence.

## Relationship to plugins

v0.6 establishes stable provider, budget, telemetry, evaluation, and runtime contracts. It does not load third-party code. v0.7 may expose selected extension points only after those contracts are frozen and covered by tests.

## Current implementation note

Draft PR #13 contains the main v0.6 implementation and passed offline CI and release-hardening gates. Credentialed Mistral execution, the complete 48-case development corpus, external holdout execution, and blinded human review remain separate verification obligations.

# PaperAgent v0.6-v0.8 P0 Code Review

## Review state

```text
Scope:                 PR #14 / feat/v0.6-v0.8-mvp-plugins
Review baseline:       master b01dbfa86de345b3d468240cc1b5a478c8cb0746
Hardened code SHA:     6c2f53e5dc5eb25b11f7a05271fea4c7944b3467
Decision:              PASS WITH EXTERNAL RELEASE CONDITIONS
Open P0 blockers:      0
Merge action:          NOT PERFORMED
Draft state:           PRESERVED
```

This review covers the merge-blocking engineering and local-security boundaries that can be verified without production credentials, an external scientific holdout, or human scientific reviewers.

## Reviewed surfaces

### v0.6

- provider configuration and secret transport;
- Mistral request, schema validation, repair, retry, telemetry, and budget boundaries;
- real executor integration, readiness, cancellation, persistence, review, and export paths;
- evaluation corpus and deterministic grading contracts;
- redaction and release workflows.

### v0.7

- plugin manifests, requests, results, capabilities, and error contracts;
- built-in registration and external entry-point discovery;
- exact command-local external authorization;
- plugin invocation and atomic output behavior;
- installed-wheel plugin path.

### v0.8

- method-plan schemas and deterministic checks;
- GO / REVISE / NO_GO verdict policy;
- baseline, provenance, license, module, hypothesis, experiment, and stop-condition gates;
- committed examples and CLI integration.

## Findings fixed during review

| Severity | Finding | Resolution |
|---|---|---|
| HIGH | Plugin JSON contracts accepted `NaN` and infinities, which are not portable JSON and break deterministic hashing/output claims. | Non-finite floats are rejected recursively; regression tests cover `NaN`, positive infinity, and negative infinity. |
| HIGH | Duplicate installed entry points with the same authorized name were silently collapsed by dictionary construction. | Discovery now fails closed with `DUPLICATE`; no candidate is loaded when authorization is ambiguous. |
| HIGH | A configured monetary budget could be bypassed when provider usage or pricing was unknown. | Monetary-budget execution now fails closed when estimated cost cannot be derived. |
| HIGH | Plugin output used an existence check followed by replacement, leaving a TOCTOU overwrite race. | Non-overwrite mode now publishes through an atomic hard-link operation; overwrite remains explicit. Temporary files are uniquely named and cleaned. |
| HIGH | The v0.8 auditor could return `GO` for a plan with no proposed modules. | A required `proposed-modules-present` gate was added. |
| HIGH | The v0.8 baseline experiment gate did not reject a baseline arm containing proposed modules. | A passing baseline arm must now be unique and contain no proposed modules. |
| HIGH | Redaction only covered exact dictionary keys and missed common prefixed keys, Bearer strings, URL query secrets, and assignment-style secrets. | Recursive redaction now covers these forms without modifying safe token-usage metadata. |
| MEDIUM | Existing REVISE and NO_GO fixture expectations did not include the new module-presence failure. | Expected verdict artifacts were updated rather than weakening the new gate. |

## Added regression evidence

- strict JSON rejection for non-finite values;
- duplicate external entry-point rejection;
- unknown-usage monetary-budget failure;
- prefixed and embedded secret redaction;
- zero-module plans cannot receive `GO`;
- contaminated baseline arms cannot receive `GO`;
- existing GO / REVISE / NO_GO examples remain deterministic under the hardened policy.

## Verification evidence

At hardened code SHA `6c2f53e5dc5eb25b11f7a05271fea4c7944b3467`:

```text
PaperAgent CI:      run 29619773690 — SUCCESS
Python 3.11:        lint, format, strict Mypy, tests, branch coverage — SUCCESS
Python 3.12:        lint, format, strict Mypy, tests, branch coverage — SUCCESS
Release Hardening:  run 29619773724 — SUCCESS
Focused pytest:     269 passed, 11 explicit skips, 0 failed
```

Release Hardening also preserved installed-wheel, CLI/plugin/web, Chromium vertical, literature-provider, and Docker readiness gates.

## PR split decision

The review considered splitting PR #14 into separate v0.6, v0.7, and v0.8 pull requests.

**Decision: do not reconstruct and split the current branch during P0 hardening.**

Reasons:

1. The branch is already a dependency-ordered stack: v0.7 consumes shared package/CLI contracts introduced alongside v0.6, and v0.8 consumes the v0.7 host.
2. Reconstructing three branches after the combined implementation and review would create a new unreviewed history and increase omission/conflict risk.
3. The PR remains Draft and unmerged, so rollback and release decisions are still controlled.
4. Review and release evidence remain separated by version in documentation and tests.

This decision does not require publishing all versions as one release. Package version changes, tags, and release notes should still be handled as separate maintainer decisions.

## Remaining external conditions

These are not P0 code defects and cannot be completed from offline repository access alone:

- live Mistral validation for all four production schemas;
- three consecutive real-provider vertical runs;
- provider-specific 429, timeout, and thinking-only observations;
- real token, cost, latency, repair, and retry distributions;
- frozen external holdout evaluation;
- blinded human scientific review;
- final scientific-quality threshold disposition.

Until those conditions are completed, the correct release statement remains:

```text
v0.6: engineering P0 reviewed; live/scientific release evidence pending
v0.7: offline MVP P0 reviewed
v0.8: offline MVP P0 reviewed
PR #14: code-review ready, not release-complete
```

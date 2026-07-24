# PaperAgent v0.6 Evaluation Corpora

## Development corpus

`cases.jsonl` contains the 48-case development corpus required by
`docs/v0.6/EXECUTION_PLAN.md`:

- 12 in-domain cases;
- 12 cross-domain/OOD cases;
- 12 insufficient-evidence cases;
- 12 adversarial cases.

Development cases may be used for implementation feedback, deterministic regression, and prompt/rule
design. They are not scientific release evidence by themselves.

## Frozen scientific holdout

`holdout_cases.v1.jsonl` contains a separately frozen 16-case operator holdout:

- 4 in-domain cases;
- 4 OOD cases;
- 4 insufficient-evidence cases;
- 4 adversarial cases.

Every holdout case includes a stable ID/version, task and constraints, expected terminal class,
required/forbidden evidence properties, deterministic checks, a 100-point human rubric, bounded
calls/tokens/time/cost, and reference-evidence provenance.

`holdout_manifest.json` records the exact UTF-8 SHA-256 digest, prompt/rule design cutoff, category
counts, anti-leakage policy, reviewer requirements, and quantitative acceptance thresholds.

The raw v1 holdout is committed for auditability but must not be embedded in prompts, deterministic
fixtures, snapshots, or case-specific routing. Any scientific prompt/rule change after the frozen
cutoff requires a new holdout version.

See `docs/acceptance/GATE_L_SCIENTIFIC_ACCEPTANCE.md` for the authoritative Gate L procedure and
thresholds.

## Current boundary

The corpus is frozen, but Gate L remains `INCOMPLETE`. Real-provider execution, immutable result
artifacts, real-source verification, baseline reproduction, blinded expert review, inter-rater
agreement, and disagreement adjudication are still required.

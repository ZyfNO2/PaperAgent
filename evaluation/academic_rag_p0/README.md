# Academic RAG P0 acceptance operator pack

The scientific acceptance protocol is mirrored from the PaperClaw-owned pack at
`benchmarks/academic_rag/v1/eval/`. PaperAgent owns the claim, accepted-context,
Artifact, decision, and report scoring projection.

`starting_commit_pair` and `implementation_base_commit_pair` are implementation
base references for the protocol freeze, not final handoff heads. Final heads
are reported only after this repair is committed and pushed.

Generate the honest pre-run report with:

```powershell
paperagent-p0-acceptance `
  --protocol evaluation/academic_rag_p0/protocol.json `
  --json-output evaluation/academic_rag_p0/p0_acceptance_report.json `
  --markdown-output evaluation/academic_rag_p0/P0_SCIENTIFIC_ACCEPTANCE_REPORT.md
```

The command must keep the result `REVISE / P0 NO-GO` while any real or human Gate
is missing and returns exit code `2` after writing the report. It does not run a
model, create gold labels, or approve Artifacts.

## Sealed-run lifecycle

`paperagent.academic.p0_sealed_run` is the cross-repository execution boundary.
Call `validate_frozen_resource_integrity(P0PublicInputPaths(...))` (also exposed
as `validate_public_inputs`) with the PaperClaw protocol resources before model
execution. This PASS-only phase validates the protocol, schema/golden files,
107-entry corpus, frozen H0-12 set, 32-question pack, question manifest and
Artifact manifest. `validate_scientific_run_readiness(...)` is a separate gate:
the committed placeholder questions intentionally stop there with
`BLOCKED_BY_HUMAN_QUESTION_AUTHORING`.

After human question authoring, call `run_p0_blinded(...)` with an answerer that
returns `response`, `citations`, `contexts`, and `trace` for each question. The
runner requires exactly Q01-Q32 with an 8/8/8/8 distribution, refuses private
gold fields, and writes the sealed envelope exactly once with an immutable
`run_digest` and raw-byte public-input digests.
These SHA-256 values are content-integrity seals for the committed resources;
they are not cryptographic provenance proof without HMAC, trusted process
isolation, or an equivalent external attestation.

`score_sealed_run(sealed_run_path, human_gold_path, public_inputs=..., scorer=...)`
revalidates the current public resources and every seal digest before opening
gold. The formal gold loader rejects AI drafts, stale locators, wrong paper or
source hashes, incomplete review metadata, and non-exact Q01-Q32 labels.
Scorer output must satisfy the complete `ScientificP0Score` contract; scorer
errors or missing scorers remain `BLOCKED`, and no missing value becomes zero.

The public API does not pass gold paths or payloads to the answerer, but this is
not process/filesystem blinding. Until the answerer runs in an isolated process
or container, the operational status is
`BLOCKED_BY_PROCESS_LEVEL_BLIND_ISOLATION`.

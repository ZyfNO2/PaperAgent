# Academic RAG P0 acceptance operator pack

The scientific acceptance protocol is mirrored from the PaperClaw-owned pack at
`benchmarks/academic_rag/v1/eval/`. PaperAgent owns the claim, accepted-context,
Artifact, decision, and report scoring projection.

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
Call `validate_public_inputs(P0PublicInputPaths(...))` with the PaperClaw
protocol resources before model execution, then call `run_p0_blinded(...)` with
an answerer that returns `response`, `citations`, `contexts`, and `trace` for
each question. The runner requires exactly 32 unique questions with an 8/8/8/8
distribution, rejects placeholder or non-human-verified questions, refuses
private gold fields, and writes the sealed envelope exactly once with an
immutable `run_digest`.

Only `score_sealed_run(sealed_run_path, human_gold_path, scorer=...)` can read
gold labels, and it first verifies the sealed digest. Missing or malformed gold
or a missing scientific scorer remains `BLOCKED`; no missing value becomes zero.

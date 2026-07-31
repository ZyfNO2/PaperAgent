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

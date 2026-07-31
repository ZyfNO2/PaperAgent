# P0 Scientific Acceptance Report

- Protocol: `academic-rag-p0-scientific-acceptance.v1`
- Overall decision: **REVISE**
- P0 Release: **NO-GO**

## Gate status

| Gate | Status | Reason |
|---|---|---|
| `unit_automation` | `NOT_RUN` | run the frozen test command |
| `corpus_manifest` | `PASS` | metadata/hash manifest is frozen |
| `real_papers` | `BLOCKED` | controlled local real-paper files and license evidence are not supplied |
| `questions_32` | `BLOCKED` | 32 IDs exist, but human question authoring is incomplete |
| `human_gold_labels` | `BLOCKED` | human gold labels are absent |
| `cross_paper_decisions` | `BLOCKED` | two human scientific decisions are absent |
| `real_minilm` | `PASS` | recorded RTX 4070 SUPER MiniLM evidence is available |
| `real_colqwen2` | `BLOCKED` | fixed-revision ColQwen2 run did not complete |
| `real_academic_llm` | `BLOCKED` | no P0 academic workflow trace is supplied |
| `native_windows` | `BLOCKED` | manual Native Windows click-through is absent |
| `human_artifact_reviewer` | `BLOCKED` | independent human Artifact review is absent |

## Hard metrics

Critical unsupported claims, critical citation mismatches, and false GO remain unscored (`BLOCKED`) until the frozen denominator and human/real evidence gates are complete.

This report does not treat generated PDFs, Fake/Mock runs, automated labels, or LLM self-review as scientific acceptance evidence.

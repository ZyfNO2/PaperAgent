# Academic Tailoring Retrieval v1 Handoff

## Status

In progress. The isolated evaluation harness is implemented and Draft PR #35 is open. Real Mistral and live literature-provider validation is pending the registered PR workflow.

## Repository and refs

- Repository: `ZyfNO2/PaperAgent`
- Dataset base branch: `eval/academic-tailoring-retrieval-v1-authoring`
- Test branch: `eval/academic-tailoring-retrieval-v1-live-test`
- Dataset authoring commit: `60c2a6f6622fa7cd562069dfdb3deb6dfd07492f`
- Production runtime base: `bfc71bee0173231eb659efaf09259c3bb41816cd`
- Draft PR: `#35`

## Isolation contract

1. The authoring file is validated and projected to a public dataset.
2. Gold mutations must not change the public projection.
3. Candidate execution receives only `BenchmarkInput` fields.
4. The candidate job deletes the authoring dataset before execution.
5. Every LLM prompt is logged for post-run leakage inspection.
6. Gold scoring occurs only in a separate evaluator job.

## Implemented files

- `scripts/project_academic_tailoring_retrieval_v1.py`
- `scripts/run_academic_tailoring_retrieval_v1.py`
- `scripts/score_academic_tailoring_retrieval_v1.py`
- `tests/evals/test_academic_tailoring_retrieval_v1_boundary.py`
- `.github/workflows/academic-tailoring-retrieval-v1-live-test.yml`
- `.github/workflows/academic-tailoring-retrieval-v1-pr.yml` on the dataset base branch

## Pending evidence

- Offline boundary test output
- Static production leakage audit output
- Ten-case real Mistral execution summary
- Real literature retrieval traces
- Prompt leakage findings
- Per-case diagnostic scores and hard failures

Do not merge or mark the PR ready until this document is updated with the actual workflow run, artifacts, failures, and final commit SHA.

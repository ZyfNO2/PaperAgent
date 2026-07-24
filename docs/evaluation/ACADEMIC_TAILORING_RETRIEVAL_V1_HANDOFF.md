# Academic Tailoring Retrieval v1 Handoff

## Status

`BLOCKED BEFORE REAL MODEL INVOCATION`

The isolated evaluation harness is implemented and Draft PR #35 remains open. The runtime has been switched from Mistral to NVIDIA-hosted `z-ai/glm-5.2` through PaperAgent's existing OpenAI-compatible provider. Offline boundary, leakage, formatting, lint, and probe-unit tests passed. The first GLM-5.2 workflow attempt stopped before authentication because repository Actions secret `NVIDIA_API_KEY` is not configured.

No NVIDIA request was sent, no model output was produced, and no real-LLM quality claim is made.

## Repository and refs

- Repository: `ZyfNO2/PaperAgent`
- Dataset base branch: `eval/academic-tailoring-retrieval-v1-authoring`
- Test branch: `eval/academic-tailoring-retrieval-v1-live-test`
- Dataset authoring commit: `60c2a6f6622fa7cd562069dfdb3deb6dfd07492f`
- Production runtime base: `bfc71bee0173231eb659efaf09259c3bb41816cd`
- GLM-5.2 workflow commit: `bdf45f60ed1d73073f30653287ddb6bfe98f3b02`
- Draft PR: `#35`

## Runtime identity

- Provider profile: `openai`
- Adapter: `paperagent.providers.openai_llm.OpenAILLMProvider`
- Model: `z-ai/glm-5.2`
- Base URL: `https://integrate.api.nvidia.com/v1`
- Credential environment variable: `NVIDIA_API_KEY`
- PaperAgent credential bridge: `PAPERAGENT_OPENAI_API_KEY`
- Health probe: bounded non-streaming `/chat/completions` request
- Monetary budget: not asserted because no verified NVIDIA price table is committed

The credential is accepted only from GitHub Actions Secrets. It is not accepted from benchmark input and must not be committed, logged, stored in artifacts, or added to repository variables.

## Isolation contract

1. The authoring file is validated and projected to a public dataset.
2. Gold mutations must not change the public projection.
3. Candidate execution receives only `BenchmarkInput` fields.
4. The candidate job deletes the authoring dataset before execution.
5. Every LLM prompt is logged for post-run leakage inspection.
6. Gold scoring occurs only in a separate evaluator job.

## Implemented files

- `scripts/check_llm_provider_health.py`
- `scripts/project_academic_tailoring_retrieval_v1.py`
- `scripts/run_academic_tailoring_retrieval_v1.py`
- `scripts/score_academic_tailoring_retrieval_v1.py`
- `tests/evals/test_academic_tailoring_retrieval_v1_boundary.py`
- `tests/scripts/test_check_llm_provider_health.py`
- `.github/workflows/academic-tailoring-retrieval-v1-live-test.yml`
- `.github/workflows/academic-tailoring-retrieval-v1-pr.yml` on the dataset base branch

## Executed verification

Workflow: `Academic Tailoring Retrieval v1 Live Test`

- Run ID: `29829487340`
- Exact code head: `bdf45f60ed1d73073f30653287ddb6bfe98f3b02`
- `offline-boundary-gate`: PASS
- Gold projection and static production leakage audit: PASS
- GLM/OpenAI-compatible health-probe unit tests: PASS
- changed-file Ruff formatting: PASS
- changed-file Ruff lint: PASS
- `prepare-public-inputs`: PASS
- `candidate-live-run`: BLOCKED
- blocking step: `Require non-empty NVIDIA credential`
- observed value: repository secret expansion was empty
- GLM health request: NOT EXECUTED
- ten-case candidate run: NOT EXECUTED
- scoring and audit: NOT EXECUTED

The concurrently triggered legacy strict workflow is not accepted as GLM-5.2 evidence because it still follows its previous credential/runtime path.

## Required operator action

Create or update this repository Actions secret:

```text
Name: NVIDIA_API_KEY
Value: the NVIDIA API key issued for https://integrate.api.nvidia.com
```

Then rerun `Academic Tailoring Retrieval v1 Live Test` on the current branch head.

Expected progression:

1. `Require non-empty NVIDIA credential` passes.
2. `Probe NVIDIA GLM-5.2 model access` returns a redacted `llm-health.json` with `status=ok` and `model_accessible=true`.
3. The isolated candidate workspace executes all ten cases.
4. Candidate artifacts contain states, traces, prompt log, execution summary, and runtime exit code.
5. The separate scorer checks minimum score, hard failures, prompt leakage, dataset identity, and Baseline/comparator relations.

## Pending evidence

- NVIDIA authentication and model-access success
- ten-case GLM-5.2 execution summary
- real literature retrieval traces paired with GLM decisions
- prompt leakage findings
- per-case diagnostic scores and hard failures
- final exact-head CI result

Do not merge or mark the PR ready until the credentialed workflow and scorer complete and this handoff is updated with the resulting artifacts and final commit SHA.

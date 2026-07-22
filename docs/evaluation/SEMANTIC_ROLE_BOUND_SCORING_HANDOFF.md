# Semantic Role-Bound Scoring Handoff

## Status

**PARTIAL / WAITING FOR REAL PROVIDER TESTS**

The implementation and isolated offline verification are complete. The branch remains a Draft PR and must not be merged until a real-provider 10-case rerun and a local multi-endpoint router probe have been reviewed.

## Repository and branch

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `master`
- Base commit: `ad44e6337f002aa8ecea3559cc0a2f213e1c8859`
- Development branch: `fix/semantic-tailoring-role-bound-scoring`
- Draft PR: `#46`
- Authoritative final branch head: the current PR head shown by GitHub after this handoff commit

## Completed work

### Production method-design path

- Added `src/paperagent/strict_method_design.py`.
- Wired `src/paperagent/nodes/method_design.py` to the strict canonicalizer.
- A user-declared baseline is now a hard identity constraint.
- A missed declared baseline no longer falls through to an inferred or repository-backed alternative.
- A user-declared parallel/module paper must be present in accepted evidence.
- Baseline evidence cannot be reused as independent module provenance.
- The final canonical proposal is checked against the declared evidence roles.

### Role-bound semantic scoring

- Added `scripts/score_academic_tailoring_retrieval_v2.py` while retaining v1 for compatibility.
- Expected paper credit is assigned by the role actually used in the generated method, not by presence anywhere in state.
- Module credit requires independently accepted `parallel_method` evidence.
- Compatibility credit requires a non-generic contract and an independently accepted compatibility review.
- Review/survey papers cannot serve as executable alternative baselines.
- `GO` is rejected unless baseline identity, module provenance, compatibility, repository/dataset evidence, and every experiment arm's task-specific protocol pass.
- The live retrieval workflow now scores with v2.

### Local router validation

- Added `scripts/test_provider_router_load.py`.
- Added failover-oriented `config/provider-router-load.example.json`.
- Added balanced, same-pool `config/provider-router-balanced.example.json`.
- Added one-command local runners:
  - `scripts/run_local_semantic_and_router_test.ps1`
  - `scripts/run_local_semantic_and_router_test.sh`
- The runners fail unless the live probe succeeds and at least two endpoints complete requests.
- All credentials and model identifiers are supplied through environment variables; no secret is committed.

## Main files changed

- `src/paperagent/strict_method_design.py`
- `src/paperagent/nodes/method_design.py`
- `scripts/score_academic_tailoring_retrieval_v2.py`
- `scripts/test_provider_router_load.py`
- `scripts/run_local_semantic_and_router_test.ps1`
- `scripts/run_local_semantic_and_router_test.sh`
- `config/provider-router-load.example.json`
- `config/provider-router-balanced.example.json`
- `.github/workflows/academic-tailoring-retrieval-v1-live-test.yml`
- `.github/workflows/semantic-tailoring-role-bound-ci.yml`
- `tests/methodology/test_strict_method_design.py`
- `tests/evals/test_academic_tailoring_retrieval_v2_scorer.py`
- `tests/scripts/test_provider_router_load.py`

## Architecture decisions

1. The production guard is generic and only reads user-declared evidence roles. It contains no benchmark case IDs, domain answer table, Gold decision, or expected method.
2. Scorer v2 wraps the stable v1 CLI/input contract, minimizing workflow changes while replacing role-insensitive scoring behavior.
3. V1 remains available for historical report reproducibility; the active live workflow uses v2.
4. Router load testing uses the existing `RoutingLLMProvider` and real provider delegates. It does not fake endpoint distribution.
5. The balanced profile places NVIDIA and Mistral in one pool so concurrent requests can be distributed for throughput. The failover profile preserves primary/fallback pool semantics.

## Executed verification

Dedicated `Semantic Tailoring Role-Bound CI`:

- Python compilation: passed.
- Ruff on all changed Python files: passed, zero findings.
- Strict Mypy on the changed production path: passed, zero issues in two source files.
- Focused regression: **37 passed**.
- Committed formatting check: passed.

The academic corpus generation job also completed successfully.

## CI limitation outside this change

The repository-wide main CI and academic verification jobs are currently stopped at Ruff by pre-existing E501 findings in:

- `.github/scripts/apply_artifact_driven_fixes.py`
- `.github/scripts/apply_artifact_driven_fixes_v2.py`

Those files have the same content on `master` and are not changed by PR #46. This branch therefore uses an isolated strict gate for the files it modifies rather than changing unrelated parallel-development files.

## Not executed / not verified

- A fresh real-provider run of all 10 academic-tailoring cases with the new production canonicalizer.
- A real multi-endpoint router load test using the user's NVIDIA/Mistral credentials and models.
- A production-cost or sustained-rate benchmark.
- Automatic acceleration of the 10-case benchmark itself through the router. The supplied router test validates endpoint distribution and throughput independently; the existing 10-case runner still constructs one provider per case.

## Local verification

### Required environment variables

PowerShell example:

```powershell
$env:NVIDIA_API_KEY_A = "<your key>"
$env:NVIDIA_MODEL = "<model available on NVIDIA endpoint>"
$env:MISTRAL_API_KEY = "<your key>"
$env:MISTRAL_MODEL = "<model available on Mistral endpoint>"
```

Bash example:

```bash
export NVIDIA_API_KEY_A='<your key>'
export NVIDIA_MODEL='<model available on NVIDIA endpoint>'
export MISTRAL_API_KEY='<your key>'
export MISTRAL_MODEL='<model available on Mistral endpoint>'
```

### One-command Windows verification

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_local_semantic_and_router_test.ps1 \
  -Requests 24 \
  -Concurrency 8 \
  -RequireSuccessfulEndpoints 2
```

### One-command Linux/macOS verification

```bash
chmod +x scripts/run_local_semantic_and_router_test.sh
scripts/run_local_semantic_and_router_test.sh \
  --requests 24 \
  --concurrency 8 \
  --require-successful-endpoints 2
```

### Rescore an existing 10-case artifact

```bash
python scripts/score_academic_tailoring_retrieval_v2.py \
  --authoring evals/academic_tailoring_retrieval_v1/dataset-authoring.json \
  --states PATH_TO_RUN/states.jsonl \
  --traces PATH_TO_RUN/run-traces.jsonl \
  --prompts PATH_TO_RUN/prompt-log.jsonl \
  --runtime-summary PATH_TO_RUN/execution-summary.json \
  --output PATH_TO_RUN/diagnostic-report-v2.json \
  --minimum-score 80
```

Add `--require-pass` only when the candidate is expected to satisfy the strict gate. During diagnosis, omit it so the report is still generated on failure.

## Pass/fail criteria

### Semantic fix passes when

- all 37 focused tests pass;
- PatchTST cannot silently become TimeMachine;
- BERT cannot silently become BEiT;
- baseline evidence is not reused as module evidence;
- generic experiment templates cannot support `GO`.

### Router load test passes when

- the script exits with code 0;
- report status is `passed`;
- final request failures are zero;
- at least two configured endpoints have `successes > 0`;
- `artifacts/provider-router-load-report.json` contains endpoint distribution, throughput, latency, errors, and circuit snapshots.

## Known limitations

- Explicit role binding can enforce declared identities, but it cannot invent a correct undeclared domain baseline. Scorer v2 still rejects unsupported role choices.
- A provider may accept prompt-injected JSON differently from another provider; the load report exposes endpoint-specific schema failures.
- Small probe counts are functional checks, not statistically reliable throughput benchmarks. Use at least 24 requests for a quick check and a larger run only after cost/rate limits are understood.

## Next developer steps

1. Check out PR #46's branch.
2. Run the one-command local script with two valid endpoints.
3. Return `artifacts/provider-router-load-report.json` if endpoint distribution or fallback fails.
4. Run the real 10-case workflow or local candidate runner and score it with v2.
5. Compare the new per-case hard failures with the manual review before considering the Draft PR mergeable.

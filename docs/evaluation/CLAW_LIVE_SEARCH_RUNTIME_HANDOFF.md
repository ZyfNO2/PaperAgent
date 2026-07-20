# CLAW Live Search Runtime Handoff

## Status

- Repository: `ZyfNO2/PaperAgent`
- Branch: `feat/claw-live-search-runtime`
- Base: `feat/claw-academic-tailoring-benchmark-v1`
- Pull request: `#34` (Draft; do not merge or mark ready automatically)
- Scope: connect the 20-case CLAW benchmark to the existing Literature Runtime and add bounded Web supplementation.

## Live verification progress

- Case 017 (`at-017-mobilenetv3-plant-disease-supplied`) attempt 2 completed successfully with Web search disabled.
- Persisted result commit: `bf473916e3c0c9bacbb485712b39eab56e66f5aa`.
- Result: `status=passed`, `score=94`, expected and observed decision both `REVISE_TO_PILOT`, and zero hard failures.
- The accepted evidence includes the exact original paper `Searching for MobileNetV3`; task evidence is restricted to plant-disease candidates and rejects retinal, skin-lesion, and healthy-leaf species-classification candidates.
- Case 017 offline gate: workflow run `29757888425`; Ruff, formatter, Mypy, and pytest all returned zero; pytest reported `91 passed`.
- Case 015 has a successful offline patch gate (`29755802086`, `72 passed`) but is not considered live-passed without a real single-case or batch result.
- Final live validation was triggered by commit `955a107027c1445cb93869d4eb7c47c9d414d226` for Cases 015, 018, 019, and 020. The batch result remains pending until `four-case-batch-latest.json` is written back.
- Web search remains disabled for these live validations.

## Corrected problem statement

PaperAgent already had real academic retrieval:

- OpenAlex, Semantic Scholar, and arXiv for discovery;
- Crossref and DataCite for DOI metadata verification;
- arXiv identifier verification;
- merge, deduplication, ranking, coverage, and Evidence Ledger enforcement.

The missing part was the benchmark execution seam. Empty Fake Search fixtures caused zero evidence and blocked the Evidence Quality Gate. The solution is not to rebuild OpenAlex or arXiv; it is to let the benchmark select the existing Literature Runtime while preserving an explicit fixture mode for deterministic CI.

## Retrieval policy

External providers are rate-limited and must not be fanned out blindly. Each query follows this sequence.

1. **Query precision review before network use**
   - Reject queries that contain no discriminative academic terms.
   - Reject generic-only queries such as `deep learning`.
   - Reject queries lacking at least two task, domain, dataset, or mechanism terms unless the query is an exact DOI/arXiv identifier.
   - Record precision risk, informative terms, discriminative terms, and rejection reasons.

2. **One academic provider first**
   - OpenAlex is the normal first source.
   - arXiv is first for recent/preprint/year-sensitive or exact arXiv queries.
   - Exact identifiers require only one relevant verified result before stopping.

3. **Quality-based escalation**
   - Stop when the configured count of verified, relevant papers reaches both the relevance and rank thresholds.
   - Otherwise escalate sequentially to Semantic Scholar and then arXiv/OpenAlex as appropriate.
   - No parallel multi-provider fan-out is used by the benchmark adapter.

4. **Web supplementation only after academic insufficiency**
   - Web search must be enabled explicitly.
   - The query must be approved and classified as low precision risk.
   - Tavily is preferred when a key is configured; DuckDuckGo HTML is a best-effort fallback.
   - Tavily uses `search_depth=basic`, `auto_parameters=false`, at most five results, and an academic/code/data domain allowlist.
   - Web pages without DOI/arXiv identity stay pending and cannot bypass Verification or the Evidence Ledger.

## Budgets

- Per query: at most three academic provider attempts and at most one Web attempt.
- Per provider response: six results by default; Tavily returns at most five.
- Production Literature Runtime: 48 uncached external provider calls per task by default.
- 20-case benchmark runner: 60 uncached external provider calls across the selected cases by default.
- Cache hits and request coalescing do not consume the external-call budget.
- A plan with `max_rounds=1` cannot trigger a hidden focused-rewrite round.

## Runtime modes

### Deterministic fixture mode

`fake` mode is injection-only. The runner refuses to create an empty Fake Search provider implicitly.

```bash
python scripts/run_claw_academic_runtime.py \
  --search-mode fake \
  --search-fixtures path/to/search-fixtures.jsonl \
  --max-cases 1
```

### Existing Literature Runtime

```bash
export PAPERAGENT_LLM_PROVIDER=mistral
export PAPERAGENT_LLM_MODEL=mistral-small-latest
export MISTRAL_API_KEY='...'
export PAPERAGENT_CONTACT_EMAIL='you@example.com'

python scripts/run_claw_academic_runtime.py \
  --search-mode literature \
  --provider-call-budget 60 \
  --max-cases 20 \
  --output-dir build/claw-live-runtime
```

Optional bounded Web supplementation:

```bash
export TAVILY_API_KEY='...'
python scripts/run_claw_academic_runtime.py \
  --search-mode literature \
  --enable-web-search \
  --provider-call-budget 60
```

## Outputs

- `states.jsonl`: primitive final PaperAgent states;
- `run-traces.jsonl`: Gold-independent normalized benchmark traces;
- `execution-summary.json`: completion errors and provider budget usage;
- `report.json`: generated only when all 20 cases complete.

## Regression coverage

The branch adds tests for:

- generic query rejection before any provider call;
- single-source stop after sufficient verified relevant evidence;
- sequential escalation only until the threshold is met;
- Web fallback gating by precision risk and scope;
- exact one-round enforcement;
- task-level provider budget exhaustion;
- Tavily authentication, low-cost request parameters, DOI extraction, and non-self-verification;
- DuckDuckGo redirect parsing and bot-challenge isolation;
- explicit Fake Search fixture requirement;
- production Literature Runtime construction;
- exact MobileNetV3 identity retrieval and Case 017 plant-disease domain precision.

## Acceptance boundary

This work establishes the connection layer and deterministic enforcement rules. Case 017 now has a recorded real-LLM/live-provider single-case pass, but this does not establish a paid full-corpus 20/20 result, full-text review for every result, reproduced scientific baselines, or measured full-corpus retrieval recall/precision. Those claims require separately recorded live executions and semantic review.

## Current handoff state

- Current status: `PARTIAL / LIVE VALIDATION IN PROGRESS`.
- Do not merge PR #34 or mark it ready automatically.
- Next step: inspect the persisted final batch result for Cases 015, 018, 019, and 020; repair only failed cases; rerun targeted offline gates before consuming another live attempt.
- Verification commands for the Case 017 precision path:

```bash
ruff check src/paperagent/literature/specialized_guards.py src/paperagent/literature/task_query_overrides.py tests/literature/test_mobilenetv3_plant_disease_precision.py
ruff format --check src/paperagent/literature/specialized_guards.py src/paperagent/literature/task_query_overrides.py tests/literature/test_mobilenetv3_plant_disease_precision.py
mypy --config-file pyproject.toml
pytest -q tests/literature/test_mobilenetv3_plant_disease_precision.py tests/literature/test_second_batch_query_precision.py tests/literature/test_third_batch_query_precision.py
```

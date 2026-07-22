# Multi-Provider Router Skeleton Handoff

## Status

`SKELETON COMPLETE / LIVE INTEGRATION PENDING`

This branch adds the isolated in-process routing core requested by the multi-provider design. The skeleton and focused cloud tests are complete. It does not yet replace the active single-provider runtime used by the evaluation workflows.

## Repository identity

- Repository: `ZyfNO2/PaperAgent`
- Base branch: `fix/academic-eval-diagnostics-baseline-binding`
- Base commit: `b1ebc1641de86f9c6d0fd2fa7c6d1084ef5295e9`
- Development branch: `feat/multi-provider-router-skeleton`
- Draft PR: `#42`
- Validated implementation commit: `0604ecd328d01ceab895114187c8672f614f0ba4`

## Implemented

### Endpoint and pool contracts

`src/paperagent/providers/endpoint.py` defines:

- vendor and API-protocol identity as separate fields;
- endpoint IDs suitable for per-account health and telemetry;
- structured-output capability flags;
- per-endpoint concurrency, RPM, and timeout limits;
- ordered provider pools;
- disabled endpoint support;
- circuit-breaker thresholds and cooldowns.

No credential value is stored in these contracts. `api_key_env` contains only an environment-variable name.

### Routing core

`src/paperagent/providers/router.py` preserves the existing `LLMProvider.generate_structured(...)` call shape and adds:

- ordered cross-pool fallback;
- same-pool endpoint selection;
- Least-In-Flight scoring;
- EWMA latency penalty;
- recent-failure penalty;
- endpoint concurrency caps;
- `CLOSED`, `OPEN`, and `HALF_OPEN` circuit states;
- permanent circuit opening for authentication, permission, and configuration failures;
- bounded cooldown for retryable failures;
- one endpoint attempt per logical router attempt;
- a global total-attempt budget;
- fail-closed behavior for task budget exhaustion and cancellation;
- winner endpoint, pool, usage, latency, and attempt records;
- lifecycle propagation through `aclose()`;
- health snapshots for later diagnostics and metrics.

### Tests

`tests/providers/test_routing_llm_provider.py` covers:

1. preferred-pool success;
2. 429 rotation from account A to account B in the same pool;
3. provider failure and fallback to the next pool;
4. open-circuit skipping and successful half-open recovery;
5. global attempt-budget enforcement;
6. fail-closed task-budget exhaustion;
7. concurrent Least-In-Flight distribution across two accounts.

The focused workflow runs lint, format, strict Mypy, and tests on Python 3.11 and 3.12.

## Verification

### Local isolated compatibility harness

```text
pytest: 7 passed
compileall: passed
```

### GitHub Actions

Workflow: `Provider Router Skeleton`

- run ID: `29934655002`;
- source commit: `0604ecd328d01ceab895114187c8672f614f0ba4`;
- Python 3.11: Ruff lint PASS, Ruff format PASS, strict Mypy PASS, 7 focused tests PASS;
- Python 3.12: Ruff lint PASS, Ruff format PASS, strict Mypy PASS, 7 focused tests PASS;
- final conclusion: SUCCESS.

This is offline control-flow evidence. It is not a real NVIDIA, OpenCode, Mistral, or DeepSeek end-to-end test.

## Deliberately not implemented in this slice

- YAML/profile loading for `smoke_fast`, `eval_fixed`, and `prod_resilient`;
- integration into `build_llm_provider(...)`;
- shared persistent `httpx.AsyncClient` ownership in `OpenAILLMProvider`;
- endpoint capability preflight and TTL cache;
- `Retry-After` propagation from the delegate into router cooldown;
- per-endpoint RPM limiter wiring;
- DeepSeek paid-budget policy;
- checkpoint persistence of route attempts;
- live provider smoke tests;
- Bifrost integration.

## Next implementation slice

1. Add a profile loader that builds `EndpointConfig`, `ProviderPool`, and `RoutingLLMProvider` from environment-referenced configuration.
2. Refactor `OpenAILLMProvider` to reuse one lifecycle-managed `httpx.AsyncClient` per base URL or endpoint.
3. Make provider error identity use the endpoint ID instead of the compatibility adapter name.
4. Add endpoint preflight for authentication, normal chat, `json_schema`, `json_object`, schema-injected chat, usage shape, and output-token parameter behavior.
5. Integrate routing only into the `smoke_fast` path first; keep fixed-model evaluation unchanged.
6. Add router attempt records to execution summaries before enabling production fallback.

## Validation commands

```bash
python -m pip install -e ".[dev]"
ruff check \
  src/paperagent/providers/endpoint.py \
  src/paperagent/providers/router.py \
  src/paperagent/providers/__init__.py \
  tests/providers/test_routing_llm_provider.py
ruff format --check \
  src/paperagent/providers/endpoint.py \
  src/paperagent/providers/router.py \
  src/paperagent/providers/__init__.py \
  tests/providers/test_routing_llm_provider.py
mypy \
  src/paperagent/providers/endpoint.py \
  src/paperagent/providers/router.py
python -m pytest tests/providers/test_routing_llm_provider.py
```

## Safety and merge boundary

- No secrets are committed.
- No live paid or free-provider request is made by this branch.
- No existing production provider path is replaced.
- The PR remains Draft.
- Do not merge until the next integration slice wires profiles, shared clients, and preflight with its own regression evidence.

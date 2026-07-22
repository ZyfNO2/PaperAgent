# TODO: Multi-API Load Expansion Beyond Dual-Endpoint

## Status

`PLANNED / NOT STARTED`

Current router supports exactly 2 endpoints (NVIDIA + Mistral) in a single pool. This TODO tracks expanding to truly multi-provider load balancing with 3+ endpoints, additional vendor support, and dynamic pool management.

## Current State

As of commit `124b6b75` (`fix/semantic-tailoring-role-bound-scoring`):

- Router (`src/paperagent/providers/router.py`) supports N endpoints in M pools
- Only NVIDIA + Mistral are tested and configured
- Config is static JSON (`config/provider-router-balanced.example.json`)
- No mechanism to add/remove endpoints without config file edits
- `.env` file lacks NVIDIA/Mistral model names — must be manually exported per session

## Scope

### 1. Additional Provider Endpoints

Add at least one more provider to the active load pool:

- **OpenAI** (direct, not via NVIDIA wrapper)
- **DeepSeek** (already has price table at `config/price-table-deepseek.json`)
- **Ollama** (local, zero-cost load testing)
- **OpenCode** (key already in system env as `OPENCODE_API_KEY`)

### 2. Model Specification System

Current gap: model names are not in `.env`, only API keys are. This makes reproduction hard.

- Add `NVIDIA_MODEL`, `MISTRAL_MODEL`, `OPENAI_MODEL`, `DEEPSEEK_MODEL` to `.env`
- Create a loader that reads `.env` automatically for router tests
- Document available models per provider

### 3. Multi-Pool Topology

Current: single pool with 2 endpoints. Target: multiple pools with priority/cost/latency tiers:

- **Tier 1 (fast/cheap)**: Ollama local, DeepSeek
- **Tier 2 (balanced)**: NVIDIA, Mistral
- **Tier 3 (premium)**: OpenAI direct

Each tier should be a separate `ProviderPool` with its own concurrency and budget limits.

### 4. Dynamic Endpoint Registration

Instead of static JSON config:

- Load endpoints from env vars with a convention (e.g., `PAPERAGENT_PROVIDER_1_VENDOR`, `PAPERAGENT_PROVIDER_1_KEY`)
- Support runtime addition/removal of endpoints
- Validate connectivity on registration

### 5. Load Report Enhancement

Current report shows per-endpoint stats. Add:

- Cost per provider (using price tables)
- Latency distribution comparison across 3+ providers
- Automatic failover event log
- Per-model breakdown (same provider, different models)

### 6. Integration with Benchmark Runner

Current: each case constructs a single provider; router is not used for batch dispatch.

- Route benchmark cases through `RoutingLLMProvider`
- Auto-distribute 10 cases across available providers
- Track per-provider success rate and latency for the full benchmark

## Sequencing

1. Add model env vars to `.env` + auto-loader
2. Add at least one more provider (DeepSeek or Ollama) to the load pool
3. Test with 3+ endpoints concurrently
4. Implement multi-pool topology
5. Integrate with benchmark runner

## Out of Scope

- Auto-scaling endpoint count based on load
- Cross-region endpoint selection
- Provider cost optimization as an objective function
- Replacing the existing single-provider evaluation pipeline

## Dependencies

- `fix/semantic-tailoring-role-bound-scoring` merged to master first
- Real API keys for additional providers
- Price tables for any new provider added to the pool

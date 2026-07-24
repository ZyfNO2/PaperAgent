# v0.6 Implementation Invariants

- Preserve the frozen v0.1 graph topology and structured output schemas.
- Keep the deterministic demo and Fake providers as credential-free regression baselines.
- Add provider-specific behavior only at adapter and runtime-factory boundaries.
- Never persist API keys, authorization headers, raw chain-of-thought, or unredacted provider payloads.
- Count every physical retry or repair attempt against call, token, time, and configured cost budgets.
- Fail closed on unsupported schemas, authentication errors, invalid provider responses, and exhausted budgets.
- Keep live-provider tests opt-in and separately marked from deterministic offline verification.

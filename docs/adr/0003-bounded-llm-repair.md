# ADR 0003: Permit One Bounded Structured-Output Repair

- Status: Accepted
- Context: real LLM execution

## Decision

Validate every structured model response with the production Pydantic schema. For malformed JSON or schema mismatch, allow one explicit repair request. Do not recursively repair or mix transport retry with schema repair.

## Rationale

- provider-native structured output improves but does not guarantee valid application state;
- one repair recovers common formatting failures;
- a strict bound prevents runaway cost and latency;
- separate telemetry exposes first-pass schema quality instead of hiding it.

## Consequences

- repair counts as a physical provider call and consumes all budgets;
- repair prompts are fingerprinted and audited separately;
- failure after repair becomes a typed terminal error;
- scientific correctness is not inferred from schema validity.

## Rejected alternatives

- Unlimited repair loops: unbounded cost and unstable latency.
- Lenient parsing into partial objects: permits invalid state into the graph.
- Silently filling missing scientific fields: fabricates unsupported content.

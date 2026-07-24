# ADR 0005: Fail Closed When a Configured Budget Cannot Be Proven

- Status: Accepted
- Context: v0.6 provider runtime

## Decision

Enforce call, token, elapsed-time, and optional monetary ceilings across retries and repairs. When a monetary ceiling is configured but provider usage or pricing is unavailable, stop rather than treating unknown cost as zero.

## Rationale

- unknown cost is not equivalent to free execution;
- retries and repairs must not bypass the task budget;
- predictable failure is preferable to silent overspend;
- the policy is testable without relying on a provider dashboard.

## Consequences

- some otherwise valid responses fail when usage cannot be measured;
- operators must supply an explicit price table for models without built-in pricing;
- telemetry distinguishes estimated cost, unknown cost, and budget exhaustion;
- budget enforcement limits resource use but does not guarantee provider billing reconciliation.

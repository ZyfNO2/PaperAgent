# Gate L provider/model policy

## Principle

Gate L scientific acceptance is **provider- and model-agnostic**.

No handoff, acceptance decision, or frozen holdout contract should prescribe a specific LLM vendor or model as the required runtime for PaperAgent.

The model used for one engineering diagnostic is evidence about that diagnostic only; it does not become the required model for local use, formal acceptance, or future deployments.

## Current usage roles

- Cloud engineering/debug runs may use any configured remote provider available to the development environment.
- Local development may use any compatible configured provider/model.
- Local or self-hosted inference may use Ollama or another supported serving channel.
- Additional remote/provider channels may be evaluated independently.

A handoff should therefore say **configured provider/model** or **real configured provider**, not prescribe a vendor/model unless it is describing a historical run whose exact identity is part of immutable evidence.

## Evidence requirements

Every formal execution must record the actual runtime identity used for that execution, including at minimum:

- provider;
- model;
- endpoint/base URL or serving channel identity where applicable;
- pricing/accounting configuration when monetary budget gates apply;
- repository SHA and frozen holdout digest.

These fields are provenance, not a recommendation or product requirement.

## Comparability

Results from different providers/models must not be silently pooled into one Gate L acceptance result.

Each formal run should preserve its own execution identity and evidence bundle. Cross-model or cross-provider comparisons should be reported as separate evaluation runs unless an explicitly defined comparison protocol says otherwise.

## Handoff wording rule

Future handoffs should avoid wording such as:

> Run the formal Gate L suite with Mistral/model-X.

Prefer:

> Run the frozen Gate L suite with the configured provider/model and preserve the exact provider/model identity in immutable execution evidence.

Historical diagnostics may still name the provider/model when that identity is necessary to reproduce the recorded evidence.

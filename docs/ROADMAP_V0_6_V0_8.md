# PaperAgent v0.6-v0.8 Delivery Roadmap

## Version sequence

| Version | Product milestone | Main implementation | Plugin status |
|---|---|---|---|
| v0.6 | Real LLM and evaluation MVP | Mistral adapter, bounded runtime, telemetry, budgets, evaluation corpus | No third-party plugin loading |
| v0.7 | Local plugin runtime MVP | Strict manifests, registry, allow-listed entry points, list/inspect/run CLI | Infrastructure plus deterministic echo contract plugin |
| v0.8 | Academic method tailoring MVP | Structured method-plan audit, GO/REVISE/NO_GO policy, fixtures and reports | First product-facing built-in plugin |

## Dependency order

```text
v0.6 provider/evaluation contracts
        ↓
v0.7 controlled local plugin host
        ↓
v0.8 academic-method-tailoring plugin
```

v0.7 must not start by weakening v0.6 provider, telemetry, or evaluation contracts. v0.8 must use the v0.7 request/result host rather than adding a one-off CLI path.

## Delivery branches

Recommended stack:

```text
feat/v0.6-real-llm-integration
  └── docs/v0.6-v0.8-mvp-roadmap
        └── feat/v0.6-v0.8-mvp-plugins
```

The final feature branch is a stacked development branch. It must remain a Draft PR until its base strategy is resolved and all required CI is green.

## Release decisions

### v0.6

Can be marked engineering-complete after the 48-case corpus and its deterministic validation are added. It remains `LIVE NOT VERIFIED` until credentialed Mistral smoke and complete vertical runs are executed. It remains `SCIENTIFIC QUALITY NOT VERIFIED` until the holdout and blinded review are complete.

### v0.7

Can be marked complete from offline evidence because its release contract forbids network access and does not require a real provider. Installed-wheel CLI behavior is part of the gate.

### v0.8

Can be marked complete from deterministic fixture and CLI evidence. It audits supplied research plans; it does not claim real scientific quality, run experiments, or verify external sources over the network.

## Cross-version engineering gates

Every release candidate must preserve:

- Python 3.11 and 3.12 verification;
- Ruff, formatting, and strict Mypy;
- at least 90% combined coverage;
- deterministic demo compatibility;
- wheel, CLI, packaged web, SQLite, browser, and Docker regression gates where applicable;
- explicit separation of Fake/Mock/offline, live provider, browser, and human evidence;
- no secret, raw chain-of-thought, or unredacted provider payload persistence.

## Deferred milestones

The following require later versioned plans:

- full-text PDF ingestion and OCR;
- embeddings and vector databases;
- automatic source verification inside the method plugin;
- plugin sandboxing, signing, installation, or marketplace;
- graph-node injection and autonomous tool plugins;
- authentication, accounts, tenancy, quotas, billing, or public deployment;
- PaperClaw execution integration;
- multi-provider routing and fallback.

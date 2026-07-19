# PaperAgent v0.7 Plugin Runtime MVP Execution Plan

## Status

`PROPOSED / IMPLEMENTATION NOT STARTED`

## 1. Goal

Add a small, explicit, local plugin runtime without weakening PaperAgent's bounded workflow, validation, security, or reproducibility contracts.

The target outcome is:

> An operator can list, inspect, validate, and explicitly invoke a versioned PaperAgent plugin through a stable contract. Built-in plugins are available without discovery. Third-party plugins are loaded only through Python package entry points and an explicit allow-list.

v0.7 is not a general autonomous tool marketplace. It is a controlled extension boundary for deterministic research utilities and future adapters.

## 2. Frozen contracts

v0.7 preserves:

- the existing LangGraph topology and node semantics;
- all v0.1-v0.6 Pydantic schemas, prompts, provider behavior, task API, persistence, review, and export contracts;
- the v0.6 provider budgets, telemetry, redaction, and evaluation evidence boundaries;
- deterministic demo and Fake-provider behavior;
- localhost-first and single-user deployment boundaries.

A plugin must not mutate graph state, SQLite records, task events, prompts, or provider configuration except through an explicit host operation defined by a later versioned contract.

## 3. MVP contracts

### 3.1 Plugin manifest

Every plugin exposes a frozen manifest with:

- API version;
- stable plugin name;
- semantic plugin version;
- description;
- capabilities;
- deterministic flag;
- network requirement;
- filesystem-write requirement;
- supported operations.

Unknown fields are rejected. Duplicate names fail closed.

### 3.2 Invocation contract

A plugin receives a structured request:

- operation name;
- JSON-compatible payload;
- request identifier.

It returns a structured result:

- plugin name and version;
- operation;
- JSON-compatible output;
- warnings;
- deterministic evidence metadata.

The host validates request and result objects. Arbitrary object graphs, provider SDK objects, secrets, and raw chain-of-thought are forbidden.

### 3.3 Registry and discovery

The registry supports:

1. explicit built-in registration;
2. read-only manifest inspection;
3. exact-name resolution;
4. Python entry-point discovery under `paperagent.plugins`;
5. explicit external-plugin allow-listing;
6. duplicate, incompatible API, malformed-manifest, and load-failure reporting.

External entry points are not loaded by default. Discovery must not scan arbitrary directories or download code.

### 3.4 CLI

Add:

```text
paperagent plugins list
paperagent plugins inspect <name>
paperagent plugins run <name> --operation <operation> --input input.json --output output.json
```

Optional repeated `--enable-external-plugin <name>` flags authorize exact third-party entry-point names for that command only.

CLI plugin execution is local, explicit, bounded to one invocation, and never exposed through the unauthenticated HTTP API in v0.7.

## 4. Built-in MVP plugin

v0.7 ships one deterministic `echo-contract` plugin used solely to verify manifest, registry, invocation, serialization, CLI, and packaging behavior. It must not access the network, filesystem, provider, graph, or SQLite.

The first product-facing plugin is delivered in v0.8.

## 5. Security rules

- No remote installation or marketplace.
- No import from user-supplied paths.
- No automatic entry-point loading.
- No plugin secrets in payloads or output.
- No HTTP exposure.
- No background execution.
- No shell or arbitrary code execution capability in the host contract.
- Plugin failures are typed and do not crash discovery of unrelated explicitly allowed plugins.
- Plugin output must be JSON-compatible and pass Pydantic validation.

Third-party Python plugins still execute local Python code when explicitly loaded. Documentation must state this trust boundary plainly.

## 6. Implementation phases

### Phase A — Contracts

Deliver:

- manifest, request, result, capability, and error contracts;
- JSON-compatibility validation;
- unit tests for strict validation and serialization.

### Phase B — Registry

Deliver:

- built-in registration;
- exact-name lookup;
- entry-point discovery with explicit allow-list;
- duplicate and API-version rejection;
- deterministic registry ordering;
- failure-isolation tests.

### Phase C — CLI and packaging

Deliver:

- list, inspect, and run commands;
- atomic UTF-8 JSON output;
- explicit overwrite refusal;
- built-in echo plugin;
- installed-wheel smoke.

### Phase D — Handoff

Deliver:

- implementation summary;
- plugin authoring guide;
- security boundary;
- test report;
- known limitations;
- final Handoff.

## 7. Acceptance gates

- Existing v0.1-v0.6 default tests remain passing.
- Combined coverage remains at or above 90%.
- Built-in plugin listing and invocation pass from an installed wheel.
- External plugins are not loaded without exact authorization.
- Duplicate names and incompatible API versions fail closed.
- Plugin output cannot contain non-JSON-compatible values.
- No plugin command modifies SQLite, starts the API, or performs a network call in the release test suite.

## 8. Out of scope

- plugin installation, updates, signatures, sandboxing, or isolation;
- remote registries or marketplaces;
- HTTP plugin execution;
- graph node injection;
- provider fallback/routing;
- arbitrary tools, MCP, shell execution, or browser automation;
- long-running/background plugins;
- plugin-owned database migrations;
- multi-user permissions.

## 9. Stop conditions

Stop and version a separate architecture change if a plugin requires:

- graph topology mutation;
- unbounded loops or background workers;
- unreviewed SQLite writes;
- secret transport in request payloads;
- public unauthenticated execution;
- arbitrary user-code execution beyond explicitly installed Python entry points.

## 10. Definition of done

v0.7 is complete when PaperAgent has a tested, deterministic, explicitly authorized local plugin contract and CLI, while the existing research workflow remains behaviorally unchanged.

# PaperAgent v0.7 Development Status

## Current state

`OFFLINE MVP COMPLETE`

```text
Repository:             ZyfNO2/PaperAgent
Implementation branch:  feat/v0.6-v0.8-mvp-plugins
Draft PR:               #14
Verified implementation: ad31be15f1e741c3e9f989cfb26331ddb46f4d2b
```

## Delivered

- frozen strict plugin manifest, request, result, capability, failure, and protocol contracts;
- deterministic built-in registration and exact-name resolution;
- Python entry-point discovery under `paperagent.plugins`;
- exact command-local external-plugin authorization;
- duplicate, missing, incompatible, malformed, load-failure, invocation-failure, and result-integrity handling;
- deterministic `echo-contract` built-in plugin;
- `paperagent plugins list`, `inspect`, and `run` commands;
- canonical request IDs and atomic UTF-8 JSON output;
- overwrite refusal unless explicitly requested;
- plugin authoring and trust-boundary documentation;
- installed-wheel plugin listing and invocation smoke.

## Verified evidence

- PaperAgent CI run `29615492804`: Python 3.11 and 3.12 lint, format, strict Mypy, tests, and coverage passed.
- Release Hardening run `29615492807`: dual-version verification, wheel build, installed CLI/plugin/web smoke, Chromium vertical smoke, live literature-provider smoke, and Docker readiness passed.
- External entry points remain disabled unless their exact installed name is explicitly authorized.

## Security boundary

Explicit authorization is not sandboxing. An authorized third-party entry point executes installed Python code in the PaperAgent process. v0.7 does not download, install, sign, isolate, or expose plugins over HTTP, and it does not grant shell, graph, provider, SQLite, background-worker, or arbitrary path capabilities.

## Deferred work

- plugin sandboxing, signatures, installation, updates, or marketplace;
- HTTP plugin execution and multi-user authorization;
- graph-node injection or long-running plugins;
- plugin-owned database migrations;
- MCP or arbitrary tool execution.

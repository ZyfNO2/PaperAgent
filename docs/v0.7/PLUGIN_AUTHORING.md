# PaperAgent v0.7 Plugin Authoring Guide

## Trust boundary

A PaperAgent plugin is installed Python code. Explicit entry-point authorization prevents accidental loading; it is not a sandbox. Only install and authorize code you trust.

The v0.7 host does not download plugins, scan arbitrary directories, expose plugins over HTTP, or provide shell, graph, SQLite, provider, or background-worker capabilities.

## Entry point

Third-party packages register one entry point in `pyproject.toml`:

```toml
[project.entry-points."paperagent.plugins"]
my-plugin = "my_package.plugin:MyPlugin"
```

The loaded object may be a plugin instance or a zero-argument plugin class.

## Required contract

Implement `PaperAgentPlugin`:

```python
from paperagent.plugins import PluginManifest, PluginRequest, PluginResult


class MyPlugin:
    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="my-plugin",
            version="1.0.0",
            description="A deterministic example.",
            capabilities=("contract_test",),
            operations=("run",),
            deterministic=True,
            requires_network=False,
            writes_files=False,
        )

    def invoke(self, request: PluginRequest) -> PluginResult:
        return PluginResult(
            plugin_name=self.manifest.name,
            plugin_version=self.manifest.version,
            request_id=request.request_id,
            operation=request.operation,
            output={"received": request.payload},
        )
```

Use `PluginCapability` enum values in production code. All request, output, warning, and evidence values must be JSON-compatible.

## Explicit authorization

External plugins are never loaded by default:

```bash
paperagent plugins list --enable-external-plugin my-plugin
paperagent plugins inspect my-plugin --enable-external-plugin my-plugin
paperagent plugins run my-plugin \
  --operation run \
  --input input.json \
  --output output.json \
  --enable-external-plugin my-plugin
```

Authorization is exact-name and command-local. A missing, duplicate, incompatible, malformed, or failed plugin is reported and does not become available.

## Result integrity

The registry rejects a result when plugin name, version, request ID, or operation differs from the invoked manifest/request. The host also rejects non-JSON-compatible payloads and results.

## Prohibited assumptions

Do not assume the v0.7 host provides:

- secrets;
- network clients;
- task or graph state;
- SQLite access;
- provider access;
- shell execution;
- filesystem paths other than data already supplied by the operator;
- retries, background execution, scheduling, or isolation.

A capability requiring those resources needs a separate versioned host contract.

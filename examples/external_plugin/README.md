# External Plugin Example

This directory is an independently packaged Python distribution. It demonstrates the `paperagent.plugins` entry-point contract without adding the plugin to PaperAgent's built-in registry.

## Install locally

```bash
python -m pip install --no-deps ./examples/external_plugin
```

## Default behavior

The host does not load the package automatically:

```bash
paperagent plugins list
```

## Explicit authorization

```bash
paperagent plugins inspect interview-summary \
  --enable-external-plugin interview-summary

paperagent plugins run interview-summary \
  --enable-external-plugin interview-summary \
  --operation summarize \
  --payload-json '{"points":["idempotency","bounded retries","durable events"]}'
```

The authorization applies only to the current command. The plugin executes local Python in the PaperAgent process and is therefore trusted code, not isolated code.

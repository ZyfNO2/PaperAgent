# ADR 0004: Require Explicit Authorization for External Plugins

- Status: Accepted
- Context: v0.7 plugin runtime

## Decision

Load built-in plugins deterministically. Discover installed Python entry points only when the current command supplies an exact authorized entry-point name. Reject missing, duplicate, malformed, or API-incompatible candidates.

## Rationale

- Python entry points execute code during load;
- automatic discovery would turn package installation into implicit code execution;
- exact command-local authorization is inspectable and easy to test;
- strict manifest and result metadata prevent accidental contract spoofing.

## Consequences

- users must explicitly authorize each external plugin invocation;
- authorization is not a sandbox: authorized code runs in the host process;
- remote installation and a plugin marketplace remain out of scope;
- stronger isolation should use a subprocess and a fixed JSON IPC contract.

# PaperAgent v0.6 Real Provider Security Boundary

- Real LLM execution is local single-user/trusted-network only.
- `MISTRAL_API_KEY` is process configuration, never task or browser input.
- The adapter persists fingerprints and redacted metadata, not raw chain-of-thought or authorization data.
- Retries are bounded and authentication, permission, invalid-request, schema-capability, and budget errors fail closed.
- Provider enablement does not add authentication, tenancy, quotas, billing, or public deployment approval.
- Live CI must use repository Secrets and must not run secret-bearing code from untrusted forks.

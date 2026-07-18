# PaperAgent Threat Model

## Scope

This model covers the local single-user/trusted-network deployment, real LLM transport, literature retrieval, durable task API, review/export, telemetry, and local plugin runtime.

## Assets

- provider credentials and configuration;
- user research questions and material references;
- task state, evidence, reviews, and exports;
- call, token, latency, and cost telemetry;
- local filesystem and Python process integrity;
- scientific provenance and citation metadata.

## Trust boundaries

```text
Browser / CLI -> FastAPI
FastAPI -> SQLite
Runner -> LLM provider
Runner -> literature providers
Operator -> external plugin authorization
Plugin -> PaperAgent process
PaperAgent -> export filesystem / response
```

## STRIDE review

| Category | Threat | Existing mitigation | Residual risk / next step |
|---|---|---|---|
| Spoofing | Unauthenticated remote client uses a public bind | Loopback default; explicit public-bind acknowledgement; no public security claim | Add authentication and tenant identity before public deployment |
| Spoofing | Plugin result claims another plugin identity | Host verifies name, version, request ID, and operation | Move external plugins to signed packages or subprocess isolation |
| Tampering | Same idempotency key is rebound to different work | Canonical request hash and unique key; conflict on mismatch | Tenant-scope keys in a multi-user version |
| Tampering | Concurrent Review overwrites newer decision | Optimistic expected version | Add actor and audit identity when authentication exists |
| Tampering | Old program writes a newer database | Schema version gate rejects unsupported future versions | Add backup and rollback tooling before production migrations |
| Repudiation | Task transition cannot be reconstructed | Durable ordered task events and timestamps | Central append-only audit storage for regulated deployments |
| Information disclosure | Credential appears in logs or task payload | Credentials come from process config; recursive redaction; no raw authorization persistence | Add automated log scanning and centralized retention policy |
| Information disclosure | Diagnostics exposes user content | Metrics and diagnostics contain low-cardinality counts only | Protect endpoints with authentication in public deployments |
| Denial of service | Unbounded model calls or repair loops | Call/token/time/cost budgets; bounded retry; one repair | Add per-user quotas and admission control |
| Denial of service | Oversized event payload or API input | Pydantic limits and 16 KiB event payload ceiling | Add reverse-proxy request limits for public deployment |
| Denial of service | SQLite write contention | WAL, busy timeout, immediate transactions, single worker | PostgreSQL and distributed queue when concurrency grows |
| Elevation of privilege | Installed plugin executes arbitrary local code | No automatic external loading; exact command-local authorization | Subprocess isolation, environment allowlist, filesystem/network policy |
| Elevation of privilege | Model chooses unrestricted host capability | Fixed workflow and capability set; structured outputs | Maintain explicit capability review for every new tool |

## Scientific integrity threats

| Threat | Mitigation | Remaining evidence requirement |
|---|---|---|
| Invented or mismatched citation | Verification status, locator, source metadata, Review gate | Live identifier validity and metadata-match measurement |
| Unsupported claim | Evidence mapping and blocked/insufficient states | External Claim-to-Evidence evaluation |
| Hidden conflict | Conflict fields and review surface | Domain-expert blind review |
| Development-set overfitting | Separate development corpus and holdout manifest | Freeze and execute an external holdout |
| Demo mistaken for scientific evidence | Synthetic notice and separate live-provider tests | Clear release report and human review |

## Security release gates

Before a public or multi-tenant deployment:

1. authentication and authorization;
2. tenant-scoped data and idempotency;
3. rate limits and cost quotas;
4. protected diagnostics and metrics;
5. plugin subprocess isolation or removal;
6. centralized audit and retention policy;
7. database backup, restore, and migration rehearsal;
8. external security review and adversarial testing.

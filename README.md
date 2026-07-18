# PaperAgent

PaperAgent `v0.5.1` is a bounded research-workflow release candidate for local single-user use and
trusted-network evaluation. It combines the frozen v0.1 workflow, v0.2 literature retrieval, v0.3
durable task API, v0.4 review/export layer, and v0.5 package-served PWA shell with an executable demo,
readiness checks, wheel packaging, and a minimal container.

## Current status

```text
Package version: v0.5.1
Workflow engine contract: v0.1 (frozen)
Literature retrieval contract: v0.2
Task API contract: v0.3
Review/export contract: v0.4
Web shell contract: v0.5
Release contract: v0.5.1
Stage: MVP release candidate
Deployment boundary: local single user / trusted network
```

The development stack additionally implements the v0.6 real-LLM offline MVP, the v0.7 controlled
local plugin runtime, the v0.8 deterministic academic method auditor, and interview-hardening evidence.
Those capabilities are not released to `master`, and v0.6 live Mistral/scientific quality remains
unverified.

## Run the deterministic demo

```bash
python -m pip install -e '.[dev,release]'
paperagent serve
```

Open `http://127.0.0.1:8000/app`.

The built-in executor produces synthetic, deterministic evidence for product-contract testing. It
exercises task submission, progress, review guards, favorites, and exports without credentials. It is
not a scientific answer and does not call an LLM.

The CLI refuses a non-loopback bind unless `--allow-public-bind` is supplied. That flag is an explicit
operator acknowledgement only; it does not add authentication or tenant isolation.

## One-command interview demonstration

```bash
python scripts/interview_demo.py --output interview-demo-summary.json
```

This credential-free script demonstrates asynchronous submission, idempotency reuse and conflict,
durable events, Review, deterministic export, the academic-method plugin, schema versioning, runtime
diagnostics, and metrics against a temporary SQLite database.

Supporting material:

- [architecture overview](docs/architecture/OVERVIEW.md)
- [request lifecycle](docs/architecture/REQUEST_LIFECYCLE.md)
- [failure model](docs/architecture/FAILURE_MODEL.md)
- [project pitch](docs/interview/PROJECT_PITCH.md)
- [backend Q&A](docs/interview/BACKEND_QA.md)
- [Agent Q&A](docs/interview/AGENT_QA.md)
- [incident cases](docs/interview/INCIDENT_CASES.md)
- [demo runbook](docs/interview/DEMO_SCRIPT.md)

## Development-branch plugins

```bash
paperagent plugins list
paperagent plugins inspect academic-method-tailoring
paperagent plugins run academic-method-tailoring \
  --operation audit \
  --input examples/v0_8/go-plan.json \
  --output method-audit.json
```

External Python entry points are never loaded automatically. They require an exact
`--enable-external-plugin <entry-point-name>` authorization for the current command. This authorization
is not sandboxing; an authorized installed plugin executes local Python code in the PaperAgent process.

An independently packaged example is available in [`examples/external_plugin`](examples/external_plugin).

## Runtime diagnostics

```bash
paperagent diagnostics --database paperagent.db
curl http://127.0.0.1:8000/v1/diagnostics/runtime
curl http://127.0.0.1:8000/metrics
```

Diagnostics expose low-cardinality task, event, database, and schema metadata. They do not return
research requests, idempotency keys, provider credentials, prompts, or model response bodies.

## Live provider smoke

```bash
PAPERAGENT_CONTACT_EMAIL=you@example.com \
  paperagent provider-smoke --timeout 20
```

This checks OpenAlex and arXiv discovery plus Crossref and DataCite DOI verification.

## Container

```bash
docker build -t paperagent:0.5.1 .
docker run --rm -p 8000:8000 -v paperagent-data:/data paperagent:0.5.1
```

The image runs as an unprivileged user, stores SQLite state in `/data`, and exposes `/readyz` for
SQLite integrity, schema compatibility, executor, and packaged-asset checks.

## Main routes

```text
GET  /app
GET  /app/{task_id}
POST /v1/tasks
GET  /v1/tasks/{task_id}
GET  /v1/tasks/{task_id}/events
GET  /v1/tasks/{task_id}/events/stream
POST /v1/tasks/{task_id}/cancel
GET  /v1/tasks/{task_id}/papers
PUT  /v1/tasks/{task_id}/papers/{paper_id}/review
GET  /v1/tasks/{task_id}/exports/{json|markdown|bibtex}
GET  /v1/diagnostics/runtime
GET  /metrics
GET  /healthz
GET  /readyz
```

## Implemented v0.5.1 MVP scope

- bounded LangGraph workflow and frozen schema/prompt/fixture contracts;
- OpenAlex, Semantic Scholar, and arXiv discovery adapters;
- Crossref and DataCite DOI verification;
- deterministic merge, ranking, coverage, cache, and retry budgets;
- SQLite task/result/error/event persistence and single-process execution;
- idempotent submission, Polling, SSE, cancellation, and fail-closed restart semantics;
- durable paper review decisions, stable pagination, and deterministic exports;
- responsive package-local PWA shell with restrictive CSP and shell-only caching;
- deterministic credential-free demo executor;
- localhost-first CLI, readiness diagnostics, wheel installation, and Docker packaging.

The browser contains no Agent, retrieval, ranking, prompt, or provider logic. All workflow decisions
remain in the Python service.

## Automated release gates

```bash
python -m pip install -e '.[dev,release]'
ruff check .
ruff format --check .
mypy --config-file pyproject.toml
pytest --cov=paperagent --cov-branch --cov-report=term-missing -q
python -m build --wheel
```

The release workflow additionally runs:

- Python 3.11 and 3.12 verification;
- installed-wheel CLI, plugin, and packaged-web smoke;
- headless Chromium submit → progress → review → export smoke;
- live OpenAlex, arXiv, Crossref, and DataCite smoke;
- Docker build and readiness smoke.

Contract and benchmark utilities:

```bash
python scripts/export_openapi.py --output build/openapi.json
python scripts/repository_benchmark.py --tasks 500 --output build/repository-benchmark.json
```

## Security and product boundary

This release has no authentication, user accounts, tenant isolation, quotas, payments, or public
abuse controls. Do not expose it as an unauthenticated public multi-user service. The deterministic
demo does not establish scientific quality, real-LLM quality, or production scalability.

See the expanded [threat model](docs/security/THREAT_MODEL.md) and
[benchmark methodology](docs/benchmarks/BASELINE.md).

## Development contracts

- [v0.6-v0.8 delivery roadmap](docs/ROADMAP_V0_6_V0_8.md)
- [combined v0.6-v0.8 handoff](docs/v0.6-v0.8/HANDOFF.md)
- [v0.6 real LLM integration and evaluation plan](docs/v0.6/EXECUTION_PLAN.md)
- [v0.6 MVP delivery contract](docs/v0.6/MVP_DELIVERY_CONTRACT.md)
- [v0.6 implementation status](docs/v0.6/DEVELOPMENT_STATUS.md)
- [v0.6 implementation handoff](docs/v0.6/HANDOFF.md)
- [v0.7 plugin runtime MVP plan](docs/v0.7/EXECUTION_PLAN.md)
- [v0.7 implementation status](docs/v0.7/DEVELOPMENT_STATUS.md)
- [v0.7 plugin authoring guide](docs/v0.7/PLUGIN_AUTHORING.md)
- [v0.8 academic method plugin MVP plan](docs/v0.8/EXECUTION_PLAN.md)
- [v0.8 implementation status](docs/v0.8/DEVELOPMENT_STATUS.md)
- [v0.5.1 execution plan](docs/v0.5.1/EXECUTION_PLAN.md)
- [v0.5.1 release runbook](docs/v0.5.1/RELEASE_CANDIDATE.md)
- [v0.5 handoff](docs/v0.5/HANDOFF.md)
- [v0.4 handoff](docs/v0.4/HANDOFF.md)
- [v0.3 handoff](docs/v0.3/HANDOFF.md)
- [v0.2 handoff](docs/v0.2/HANDOFF.md)
- [v0.1 handoff](docs/v0.1/HANDOFF.md)

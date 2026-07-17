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
SQLite integrity and packaged-asset checks.

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
GET  /healthz
GET  /readyz
```

## Implemented MVP scope

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
- installed-wheel CLI and packaged-web smoke;
- headless Chromium submit → progress → review → export smoke;
- live OpenAlex, arXiv, Crossref, and DataCite smoke;
- Docker build and readiness smoke.

## Security and product boundary

This release has no authentication, user accounts, tenant isolation, quotas, payments, or public
abuse controls. Do not expose it as an unauthenticated public multi-user service. The deterministic
demo does not establish scientific quality, real-LLM quality, or production scalability.

## Development contracts

- [v0.6 real LLM integration and evaluation plan](docs/v0.6/EXECUTION_PLAN.md)
- [v0.5.1 execution plan](docs/v0.5.1/EXECUTION_PLAN.md)
- [v0.5.1 release runbook](docs/v0.5.1/RELEASE_CANDIDATE.md)
- [v0.5 handoff](docs/v0.5/HANDOFF.md)
- [v0.4 handoff](docs/v0.4/HANDOFF.md)
- [v0.3 handoff](docs/v0.3/HANDOFF.md)
- [v0.2 handoff](docs/v0.2/HANDOFF.md)
- [v0.1 handoff](docs/v0.1/HANDOFF.md)

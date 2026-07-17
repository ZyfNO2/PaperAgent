# PaperAgent v0.5.1 Release Hardening Plan

## Goal

Turn the verified v0.5 package-served PWA into a directly runnable, reproducible single-user release candidate without expanding the product into a public multi-tenant platform.

## In scope

1. Add a localhost-first `paperagent serve` command.
2. Add a deterministic demo executor so the full submit → progress → review → export path can be exercised without credentials.
3. Add `/readyz` diagnostics for SQLite and packaged web assets.
4. Add a minimal Docker image for trusted-network evaluation.
5. Add a live OpenAlex/arXiv/Crossref smoke workflow.
6. Add a Chromium browser smoke that exercises the complete vertical path.
7. Build and install the wheel during release verification.
8. Remove known application-owned deprecation warnings and publish a release/manual-test handoff.

## Explicitly out of scope

- authentication, accounts, tenant isolation, quotas, billing, or collaboration;
- public-internet hardening claims;
- a real LLM provider adapter or production prompt orchestration;
- distributed workers, Redis, PostgreSQL, or automatic provider-call replay;
- PDF/full-text RAG, vector databases, native mini-programs, or SSR;
- scientific-quality claims based on the deterministic demo executor.

## Acceptance gates

- Ruff, Ruff format, Mypy, and branch coverage >= 90% on Python 3.11 and 3.12;
- deterministic demo API and review/export integration tests pass;
- package wheel builds and installed package serves `/app`, `/healthz`, and `/readyz`;
- headless Chromium completes task submission, terminal progress, paper review, and JSON export;
- live OpenAlex, arXiv, and Crossref smoke passes from GitHub Actions;
- Docker image builds and responds to readiness checks;
- temporary verification transport is removed before merge;
- final PR remains reviewable as one stacked hardening layer.

## Stop condition

After these gates pass, stop feature development. Remaining work becomes environment-specific manual validation or a separate post-MVP product decision.
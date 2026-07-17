# PaperAgent v0.5.1 Handoff

## Delivery status

`MVP RELEASE CANDIDATE COMPLETE`

Feature development stops at this contract. Further work requires either environment-specific manual
validation or an explicit post-MVP product decision.

## Delivered

- localhost-first `paperagent serve` command;
- deterministic synthetic demo executor for the full product contract;
- `/readyz` SQLite and packaged-asset diagnostics;
- installable wheel with console entry point and package-local web assets;
- unprivileged Docker image with persistent `/data` volume and healthcheck;
- live OpenAlex, arXiv, Crossref, and DataCite smoke command;
- Playwright Chromium submit → progress → review → export smoke;
- current HTTP 422 constant and release documentation.

## Automated evidence

Release Hardening run `29552014523` passed on code head
`eb0aa6650b59b55ad4fe2dcdbcc108917f918a5d`:

- Python 3.11 offline verification, Mypy, coverage gate, and wheel build — PASS;
- Python 3.12 offline verification, Mypy, coverage gate, and wheel build — PASS;
- installed-wheel CLI and packaged-web smoke — PASS;
- Chromium vertical smoke — PASS;
- live OpenAlex/arXiv/Crossref/DataCite smoke — PASS;
- Docker image build and readiness smoke — PASS.

The Python 3.12 coverage artifact contains 3,043 of 3,174 executable lines and 529 of 650 branches,
for a combined coverage score of approximately 93.41%, above the 90% gate.

The standard `PaperAgent CI` run `29552014571` also completed successfully on the same code head.

## Non-claims

- The deterministic demo is not a scientific answer and does not validate LLM quality.
- Semantic Scholar authenticated quota behavior was not included in the live release smoke.
- This release is not approved for an unauthenticated public multi-user deployment.
- Distributed execution, automatic in-flight provider replay, PDF RAG, and native mini-programs are
  not implemented.
- Mobile Safari, iOS installation, Android installation, long-duration soak, and reverse-proxy
  deployment remain manual checks.

## Operator entry points

```bash
paperagent serve
paperagent provider-smoke --timeout 20
docker build -t paperagent:0.5.1 .
```

See `docs/v0.5.1/MANUAL_TEST_CHECKLIST.md` before a real deployment or external demonstration.

# PaperAgent v0.5 Package-Served PWA Shell MVP Handoff

> Status: `OFFLINE MVP COMPLETE / BROWSER E2E PENDING`  
> Repository: `ZyfNO2/PaperAgent`  
> Branch: `feat/v0.5-pwa-shell-mvp`  
> Base: `feat/v0.4-review-export-mvp`  
> Draft PR: `#10`

## Completed scope

- Added package-served `/app` and `/app/{task_id}` shell routes.
- Added package-local HTML, CSS, JavaScript, SVG icon, web manifest, and service worker.
- Added task submission with generated idempotency keys.
- Added shareable task URLs and local recent-task history.
- Added polling-first progress with SSE enhancement and ordered event rendering.
- Added queued/running cancellation control.
- Added paper-card filters, pending/accepted/rejected decisions, and favorites.
- Added JSON, Markdown, and BibTeX downloads with checksum feedback.
- Added loading, offline, failed, cancelled, empty, and terminal states.
- Added responsive mobile layout, semantic markup, focus states, and reduced-motion behavior.
- Added restrictive CSP and security headers for shell documents.
- Limited service-worker caching to shell routes/assets; `/v1` API state is never cached.
- Kept all Agent, retrieval, ranking, prompt, and provider logic on the server.

## Main files

```text
src/paperagent/web/routes.py
src/paperagent/web/assets/index.html
src/paperagent/web/assets/styles.css
src/paperagent/web/assets/app.js
src/paperagent/web/assets/manifest.webmanifest
src/paperagent/web/assets/service-worker.js
src/paperagent/web/assets/icon.svg
src/paperagent/api/v05.py
tests/web/test_shell.py
docs/v0.5/EXECUTION_PLAN.md
```

## Verification evidence

Official GitHub Actions:

```text
Run ID:                  29542982869
Verified head:           e7b83be1b3d847f8155150fa14f9d5721e6d1143
Python 3.11 job:         PASS
Python 3.12 job:         PASS
Install:                 PASS
Ruff lint/format:        PASS
Mypy:                    PASS
Tests and coverage:      PASS
Coverage artifacts:      PASS
```

Audited detailed run:

```text
Run ID:                  29542980304
Python 3.11 tests:       175 passed, 1 skipped
Python 3.11 coverage:    93.38%
Python 3.12 tests:       175 passed, 1 skipped
Python 3.12 coverage:    93.43%
Coverage threshold:      90%
```

The skipped test is the inherited opt-in real-network literature provider smoke test.

## Browser contract covered by tests

- `/app`, `/app/`, and one-segment task URLs return the same shell;
- shell routes are excluded from OpenAPI;
- manifest, worker, JavaScript, CSS, and SVG assets are served with expected media types;
- the JavaScript contract contains submit, idempotency, polling, EventSource, cancellation, review,
  optimistic version, export, local history, task navigation, and service-worker registration;
- no external CDN, `eval`, browser-side LLM provider, or `innerHTML` rendering is used;
- service worker does not intercept `/v1` API responses.

## Important limitations

1. No real Playwright/Selenium/browser-device E2E was executed.
2. The PWA shell can cache its static shell, but task execution and API state require connectivity.
3. There is no login, user isolation, payment, collaboration, or public deployment hardening.
4. Recent task history is device-local and stores task IDs/titles only.
5. This is not a native mini-program package.
6. There is no PDF reader, trace debugger, or admin console.
7. Real provider network smoke inherited from v0.2 is still pending.

## Release state

The v0.3-v0.5 stacked MVP sequence is implemented as separate Draft PRs. No branch has been merged or
auto-merged. A future release should first resolve the stacked review order, run real-provider smoke,
then perform a trusted deployment and real-browser E2E before any public exposure.

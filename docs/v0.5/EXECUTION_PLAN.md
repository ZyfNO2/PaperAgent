# PaperAgent v0.5 Package-Served PWA Shell MVP

> Status: `IMPLEMENTED`  
> Base: `feat/v0.4-review-export-mvp`  
> Branch: `feat/v0.5-pwa-shell-mvp`

## Goal

Provide a usable browser shell over the v0.3 task API and v0.4 review/export API without adding a
second backend stack. The shell is static package data served by FastAPI; all workflow and evidence
logic remains on the server.

## Included

- responsive `/app` and `/app/{task_id}` shell routes;
- package-local HTML, CSS, JavaScript, SVG icon, manifest, and service worker;
- research-question submission with generated idempotency keys;
- shareable task URL and local recent-task history;
- polling-first task progress with SSE enhancement;
- durable event rendering and cancel action;
- paper-card filters, decisions, and favorites;
- JSON, Markdown, and BibTeX downloads with checksum feedback;
- loading, offline, failed, cancelled, empty, and terminal states;
- keyboard focus states, semantic markup, reduced-motion support, and mobile layout;
- restrictive CSP and shell response security headers;
- service-worker caching limited to shell routes/assets, never `/v1` API responses.

## Architecture

```text
Browser PWA shell
  -> v0.3 task endpoints
  -> v0.4 paper review/export endpoints

FastAPI
  -> serves static package assets
  -> remains the only application backend
```

## Explicitly excluded

- browser-side Agent, retrieval, ranking, or prompt logic;
- Node backend, Next.js server, SSR, or external CDN;
- native mini-program package;
- login, payments, organizations, and collaboration;
- PDF reader, trace debugger, or admin console;
- offline task execution or background API synchronization.

## Acceptance

- `/app` and one-segment task URLs serve the same shell;
- static assets are package-local and included in the Python distribution;
- no external script/style dependency is required;
- submit, poll, SSE, cancel, review, favorite, and export contracts are present in the browser client;
- refresh preserves navigation through the task URL;
- recent task IDs survive locally without storing full task results;
- service worker does not cache API state;
- all v0.1-v0.4 tests remain green;
- Python 3.11/3.12, Ruff, Mypy, tests, and >=90% branch coverage pass.

## Post-MVP

A real browser E2E run, authentication, public deployment hardening, native mini-program shell, and
full PDF evidence reading each require separate versions and measurable usage evidence.

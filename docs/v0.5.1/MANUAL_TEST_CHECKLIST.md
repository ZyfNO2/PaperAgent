# PaperAgent v0.5.1 Manual Supplemental Test Checklist

Automated CI validates the deterministic demo, live core literature providers, Chromium, wheel
installation, and Docker readiness. The following checks require human judgement, credentials,
platform-specific devices, longer observation windows, or deployment infrastructure.

## P0 — Required before any external or public-network demonstration

- [ ] Confirm the service is reachable only by the intended operator or trusted network.
- [ ] Put HTTPS and an authenticated reverse proxy in front of any non-local deployment.
- [ ] Verify `/docs`, `/openapi.json`, `/healthz`, `/readyz`, `/app`, and `/v1/*` exposure is intentional.
- [ ] Inspect server logs, SSE frames, task results, SQLite rows, and browser storage for API keys,
      cookies, authorization headers, raw exceptions, or private source material.
- [ ] Restart the process during a running task and confirm the task fails closed with the documented
      restart error instead of silently replaying provider calls.
- [ ] Back up the SQLite file, restore it into a fresh container, and verify tasks, events, review
      decisions, favorites, and exports remain readable.
- [ ] Exercise disk-full, read-only-volume, missing-volume, and corrupted-SQLite conditions; confirm
      `/readyz` fails and the operator receives a clear diagnostic.
- [ ] Confirm the deterministic demo disclaimer is visible and cannot be mistaken for real research.

## P1 — Required before relying on real literature retrieval

- [ ] Run `paperagent provider-smoke` repeatedly from the actual deployment region and record latency,
      intermittent failures, and HTTP rate-limit behavior.
- [ ] Test Semantic Scholar with the real API key, including valid, missing, expired, and quota-exhausted
      credentials.
- [ ] Test provider schema drift using several research domains, Unicode titles, long author lists,
      missing abstracts, missing years, duplicate DOI records, arXiv-only papers, and retracted papers.
- [ ] Validate Crossref/DataCite mismatched-title and mismatched-DOI paths against known records.
- [ ] Disconnect the network during provider calls and verify partial failure, timeout, cache, and retry
      budgets remain bounded.
- [ ] Cancel a task while a real provider request is in flight and confirm no later graph node starts
      after the current boundary finishes.
- [ ] Review at least 20 real research questions and manually score relevance, diversity, evidence-gap
      coverage, metadata correctness, and ranking explanations.
- [ ] Confirm that no test fixture answer, benchmark-specific wording, or unrelated domain answer leaks
      into out-of-distribution questions.

## P1 — Browser and PWA devices

- [ ] Desktop Chrome: install PWA, refresh task URLs, reconnect after offline mode, and download all
      export formats.
- [ ] Android Chrome: install to home screen, background/foreground the app, rotate the device, and
      exercise touch controls and downloads.
- [ ] iPhone/iPad Safari: Add to Home Screen, relaunch, verify service-worker behavior, task URLs,
      scrolling, text input, and file downloads.
- [ ] macOS Safari and Firefox: verify Polling fallback when SSE or service-worker behavior differs.
- [ ] Simulate slow 3G, intermittent connectivity, duplicate SSE events, SSE disconnects, and browser
      refreshes; confirm Polling recovers without duplicate UI state.
- [ ] Verify the service worker never caches `/v1` task, event, review, or export responses.
- [ ] Clear site data and confirm recent-task history disappears without affecting server-side tasks.
- [ ] Open the same task in two tabs, create conflicting review updates, and confirm the stale tab
      receives a version conflict and recovers correctly.

## P1 — Accessibility and usability

- [ ] Complete the entire flow using keyboard only; verify visible focus and logical focus order.
- [ ] Test with NVDA or VoiceOver for headings, task status changes, errors, buttons, filters, and cards.
- [ ] Verify 200% and 400% browser zoom without clipped controls or horizontal content loss.
- [ ] Test high-contrast mode, reduced-motion mode, dark OS settings, and long Chinese/English titles.
- [ ] Confirm status and verification meaning is not communicated by color alone.
- [ ] Ask at least three target users to complete submit → review → export without instructions and
      record misunderstandings or dead ends.

## P1 — Export interoperability

- [ ] Import BibTeX exports into Zotero, JabRef, and at least one LaTeX workflow.
- [ ] Open JSON and Markdown exports containing Chinese, Japanese, emoji, braces, quotes, and long URLs.
- [ ] Verify downloaded filenames on Windows, macOS, Android, and iOS.
- [ ] Re-export unchanged selections and compare SHA-256 values byte-for-byte.
- [ ] Change one review decision and confirm only the expected export content and checksum changes.
- [ ] Confirm rejected and failed-verification papers cannot enter an accepted-only export.

## P2 — Capacity and operational behaviour

- [ ] Submit repeated idempotent requests and conflicting payloads using the same key.
- [ ] Queue many tasks and confirm the single-process runner remains ordered and memory use stays bounded.
- [ ] Test maximum-length questions, maximum metadata, maximum event payload, and maximum result payload.
- [ ] Run a 24-hour soak with periodic tasks, browser reconnects, exports, container restarts, and SQLite
      growth monitoring.
- [ ] Measure p50/p95/p99 API latency, provider latency, queue time, task duration, memory, CPU, disk,
      and SQLite WAL growth.
- [ ] Verify log rotation, database retention, backup frequency, restore time, and operator alerting.
- [ ] Test two application processes against the same SQLite file and confirm this unsupported topology
      is rejected operationally rather than assumed safe.

## P2 — Real LLM integration decision

No production LLM adapter is part of v0.5.1. Before adding one:

- [ ] Select the provider/model and define timeout, retry, token, cost, structured-output, and redaction
      contracts.
- [ ] Run prompt-leakage, prompt-injection, secret-exfiltration, malformed-output, and cost-limit tests.
- [ ] Compare deterministic fixtures with real-model outputs on in-domain and out-of-domain tasks.
- [ ] Establish human evaluation criteria for scientific correctness, unsupported claims, citation
      fidelity, method feasibility, and reproducibility.
- [ ] Keep real-provider tests separately marked and never weaken deterministic offline fixtures.

## Sign-off record

Record tester, environment, commit SHA, container/wheel digest, date, evidence links, result, and owner
for every failed item. P0 failures block any external deployment. P1 failures block reliance on the
affected feature. P2 failures become measured post-MVP backlog rather than silent assumptions.

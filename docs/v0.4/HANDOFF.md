# PaperAgent v0.4 Review and Export MVP Handoff

> Status: `OFFLINE MVP COMPLETE / DRAFT PR ONLY`  
> Repository: `ZyfNO2/PaperAgent`  
> Branch: `feat/v0.4-review-export-mvp`  
> Base: `feat/v0.3-durable-task-api-mvp`  
> Draft PR: `#9`

## Completed scope

- Added durable paper-review records keyed by task and paper ID.
- Added `pending`, `accepted`, and `rejected` decisions plus an independent favorite flag.
- Added optimistic `expected_version` updates and repeat-safe identical updates.
- Added stable opaque cursor pagination ordered by paper ID.
- Derived paper cards only from succeeded task evidence with `source_type=paper`.
- Prevented rejected or failed-verification evidence from being marked accepted.
- Added deterministic JSON, Markdown, and BibTeX exporters.
- Added accepted, favorite, and all export selections.
- Added SHA-256, item count, selection, filename, and media-type metadata.
- Added API routes for listing cards, updating reviews, and downloading exports.

## API

```text
GET /v1/tasks/{task_id}/papers
PUT /v1/tasks/{task_id}/papers/{paper_id}/review
GET /v1/tasks/{task_id}/exports/{json|markdown|bibtex}
```

## Verification evidence

Audited dual-version run:

```text
Run ID:                  29542354269
Verified head:           30296a488031ad6e611442916db8f8aaee68468e
Python 3.11 install:     PASS
Python 3.11 Ruff:        PASS
Python 3.11 format:      PASS
Python 3.11 Mypy:        PASS
Python 3.11 tests:       171 passed, 1 skipped
Python 3.11 coverage:    93.31%
Python 3.12 install:     PASS
Python 3.12 Ruff:        PASS
Python 3.12 format:      PASS
Python 3.12 Mypy:        PASS
Python 3.12 tests:       171 passed, 1 skipped
Python 3.12 coverage:    93.36%
Coverage threshold:      90%
```

The skipped test is the inherited opt-in real-network literature provider smoke test.

## Main files

```text
src/paperagent/api/review.py
src/paperagent/api/review_models.py
src/paperagent/api/review_routes.py
src/paperagent/api/v04.py
tests/api/test_review_export.py
docs/v0.4/EXECUTION_PLAN.md
```

## Important semantics

1. Review records do not mutate the original Evidence Bundle.
2. A stale version fails with HTTP 409 instead of overwriting a newer decision.
3. Repeating an identical update at the current version is idempotent.
4. Accepted export cannot contain rejected or failed-verification evidence.
5. Export output is byte-deterministic for the same task, decisions, selection, and format.
6. Export files are generated on demand and are not stored in object storage.

## Not completed

- accounts, authentication, authorization, or collaboration;
- manual override for failed-verification evidence;
- CSL citation-style support;
- saved export files or object storage;
- PDF/full-text processing;
- frontend;
- real provider network smoke inherited from v0.2.

## Next branch

`feat/v0.5-pwa-shell-mvp` should be created from the final clean v0.4 branch and add only a
package-served responsive web shell for submit, progress, paper review, and export. It must not add a
Node backend, Next.js server, native mini-program package, login, payments, collaboration, or PDF RAG.

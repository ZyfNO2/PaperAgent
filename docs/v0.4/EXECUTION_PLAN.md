# PaperAgent v0.4 Review and Export MVP

> Status: `IMPLEMENTED`  
> Base: `feat/v0.3-durable-task-api-mvp`  
> Branch: `feat/v0.4-review-export-mvp`

## Goal

Add the smallest durable human-review layer over terminal paper evidence. Users can page through paper
cards, record accept/reject/pending decisions, mark favorites, and export a selected set as JSON,
Markdown, or BibTeX.

## Included

- SQLite `paper_reviews` table keyed by `(task_id, paper_id)`;
- decision values `pending / accepted / rejected` plus a separate favorite flag;
- optimistic `expected_version` updates;
- identical repeat updates return the existing version without another mutation;
- stable opaque cursor pagination ordered by paper ID;
- paper cards derived only from succeeded task evidence with `source_type=paper`;
- rejected or failed-verification evidence cannot be marked accepted;
- deterministic JSON, Markdown, and BibTeX output;
- SHA-256, item count, selection, filename, and media-type export metadata;
- accepted, favorite, and all export selections.

## API

```text
GET /v1/tasks/{task_id}/papers
PUT /v1/tasks/{task_id}/papers/{paper_id}/review
GET /v1/tasks/{task_id}/exports/{json|markdown|bibtex}
```

## Explicitly excluded

- accounts, sharing permissions, teams, and collaborative comments;
- force-accept override for failed-verification evidence;
- CSL citation styles or a citation-style engine;
- object storage and saved export files;
- PDF/full-text download;
- frontend.

## Acceptance

- decisions survive repository re-open;
- stale update versions return 409;
- invalid paper/task IDs return 404;
- non-terminal tasks return 409;
- pagination is stable and bounded;
- exports are byte-deterministic and checksum-verifiable;
- selection filters cannot leak rejected items into accepted export;
- all prior v0.1-v0.3 tests remain green;
- Python 3.11/3.12, Ruff, Mypy, tests, and >=90% branch coverage pass.

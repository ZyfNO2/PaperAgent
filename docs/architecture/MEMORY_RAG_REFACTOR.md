# PaperAgent Memory and Academic RAG Refactor

## Status

This document describes the upload-first application boundary introduced on
`refactor/paperagent-memory-rag`. It does not change `master` history and does not merge the
superseded provider-resilience branches.

## Product boundary

PaperAgent now treats user-supplied papers as the primary corpus. Open-ended provider search is an
optional acquisition aid rather than a hard workflow dependency.

```text
Research Project
  -> versioned paper ingestion
  -> evidence units with citation locators
  -> deterministic hybrid project retrieval
  -> gated project memory
  -> evidence-bound method tailoring
```

## Research projects

A research project owns its research question, paper corpus, evidence units, and memory. The new
SQLite tables are additive and do not modify the existing task or review tables.

## Versioned paper ingestion

Supported inputs:

- PDF via `pypdf`;
- UTF-8 Markdown;
- UTF-8 plain text.

Every ingestion records a SHA-256 content digest and monotonically increasing version. Historical
versions remain stored, while retrieval uses only the latest version of each paper.

Each extracted evidence unit records:

- project, paper, and ingestion identities;
- section, page, and paragraph when available;
- character offsets;
- an evidence quote;
- deterministic keywords.

## Hybrid academic retrieval

The first implementation is local and deterministic. It combines:

- lexical term-frequency and inverse-document-frequency scoring;
- a stable SHA-256 hashed semantic vector;
- exact-phrase and evidence-keyword bonuses.

This is intentionally not presented as a learned embedding model. It provides a testable local
baseline that can later be replaced behind the same repository boundary.

## Project memory

Memory writes are not automatically trusted. Each write moves through:

```text
proposed -> approved | rejected
```

Approved memory is returned by default. Pending proposals require an explicit query flag. Every
state transition is persisted in `memory_write_audit`. Evidence references must resolve inside the
same project before a proposal can be created.

Memory scopes:

- `long_term`: stable objectives, constraints, and accepted decisions;
- `working`: current findings and next actions.

## Evidence-bound tailoring

The tailoring service requires:

1. an ingested baseline paper;
2. evidence matching the proposed hypothesis;
3. at least one independently ingested module paper;
4. matching evidence for each module.

Missing evidence produces a scientific `BLOCKED` decision with explicit reason codes, including
`module_design_deferred:insufficient_independent_evidence`. A corpus-supported composition remains
`REVISE` until semantic, gradient, loss-scale, license, compute, and implementation contracts are
independently verified.

No performance result or novelty claim is generated from textual evidence alone.

## CLI

The application boundary is available through:

```text
paperagent project-create
paperagent paper-ingest
paperagent rag-query
paperagent memory-propose
paperagent memory-review
paperagent memory-show
paperagent tailor
```

All commands use `--database` or `PAPERAGENT_DATABASE` and write to the same SQLite database as the
existing local runtime without changing its existing schemas.

## Verification target

The vertical test demonstrates:

```text
create project
-> ingest ResNet
-> ingest ECA and mixup
-> cross-paper retrieval
-> propose and approve project memory
-> restart and recover corpus plus memory
-> produce an evidence-cited REVISE tailoring plan
```

This is an offline project-corpus verification. It is not a real model-training experiment and does
not claim that ECA or mixup improves ResNet in the tested repository.

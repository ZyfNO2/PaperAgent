# Academic RAG PaperClaw sync handoff

Status: PaperAgent is synchronized with PaperClaw 0.43 through the optional
versioned Python interface. The local Project RAG adapter remains available as a
text-only fallback.

## PaperAgent interface boundary

PaperAgent consumes an injected `AcademicEvidenceSource` with two operations:

- `retrieve(AcademicRetrievalRequest) -> AcademicRetrievalResult`
- `resolve(AcademicLocator) -> AcademicCandidate`

The workflow never reads a PaperClaw database, page cache, or model index. A later
PaperClaw adapter must map its canonical `academic.v1` JSON models into these
consumer-side types and preserve every locator field used by PaperAgent.

## Required PaperClaw behavior

- Preserve paper/version/source hash, page, section, object, bbox, paragraph,
  line, and table row/column identity.
- Return per-channel degradation explicitly. A visual request with an unavailable
  visual channel cannot be reported as `sufficient`.
- Validate `source_hash` in `resolve` and fail closed on version drift, missing
  objects, or corrupt indexes.
- Persist artifact revisions append-only. PaperAgent only creates drafts and
  requests review/finalization through `AcademicArtifactSink`.

## Bounded control flow

PaperAgent performs one primary retrieval, at most one corrective retrieval, and
at most one conflict check. DOI/arXiv identifiers are preserved verbatim in the
rewritten query. Claims in generated drafts may reference accepted evidence IDs
only.

## Implemented adapters

`PaperClawAcademicEvidenceSource` maps PaperAgent's bounded rounds to canonical
PaperClaw requests without reading PaperClaw storage. It preserves the `exact`,
lexical, dense, and visual channels and converts complete locators at the seam.

`PaperClawAcademicArtifactSink` persists draft, review, and final states as
append-only PaperClaw Artifact revisions.

The integration is optional because PaperAgent supports Python 3.11 while
PaperClaw 0.43 requires Python 3.12. Base PaperAgent imports remain independent
of PaperClaw; the real adapter is exercised on Python 3.12.

## Local fallback

`ProjectRAGEvidenceSource` adapts the existing text Project RAG. It marks visual
retrieval as degraded. `InMemoryAcademicArtifactSink` exists only for offline
tests and CLI previews; its output is labelled
`in_memory_pending_paperclaw_sync`.

## Sync acceptance

The structural adapter and real PaperClaw runtime pass the same seam tests:
locator replay, source hash validation, exact identifier routing, degradation
behavior, and append-only Artifact review. A real generated PDF also passes the
PaperClaw ingest → parse → index → retrieve → PaperAgent ledger path.

This engineering synchronization does not replace the remaining release gate:
the frozen real-paper corpus report, real LLM run, and human Desktop approval
must be recorded before declaring Academic RAG P0 GO.

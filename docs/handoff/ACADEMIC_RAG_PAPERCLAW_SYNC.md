# Academic RAG PaperClaw sync handoff

Status: PaperAgent implementation complete for the local Project RAG adapter.
PaperClaw synchronization is intentionally deferred.

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

## Current local fallback

`ProjectRAGEvidenceSource` adapts the existing text Project RAG. It marks visual
retrieval as degraded. `InMemoryAcademicArtifactSink` exists only for offline
tests and CLI previews; its output is labelled
`in_memory_pending_paperclaw_sync`.

## Sync acceptance

The later PaperClaw adapter and the fake/local adapters must pass the same
contract suite. Synchronization is complete only when locator replay, source hash
validation, degradation behavior, and append-only artifact review all pass
against PaperClaw's canonical `academic.v1` implementation.

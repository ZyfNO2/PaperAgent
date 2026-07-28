"""Optional adapters for PaperClaw's canonical academic and Artifact interfaces."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from importlib import import_module
from typing import Any, Literal, Protocol, cast

from paperagent.academic.artifacts import (
    AcademicArtifactDraft,
    AcademicArtifactRevision,
    AcademicArtifactType,
)
from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicChannel,
    AcademicLocator,
    AcademicObjectType,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
    EvidenceLocatorView,
    SufficiencyDecision,
)


class _ClawBoundingBox(Protocol):
    x0: float
    y0: float
    x1: float
    y1: float


class _ClawLocator(Protocol):
    schema_version: str
    paper_id: str
    version_id: str
    object_id: str
    page_number: int
    object_type: str
    source_hash: str
    section_path: tuple[str, ...]
    bounding_box: _ClawBoundingBox | None
    paragraph_index: int | None
    line_range: tuple[int, int] | None
    table_row: int | None
    table_column: int | None


class _ClawCandidate(Protocol):
    locator: _ClawLocator
    text: str
    channel_scores: dict[str, float]
    fused_score: float
    explanation: tuple[str, ...]
    provenance: Literal["extracted", "inferred"]


class _ClawTrace(Protocol):
    trace_id: str
    degraded_channels: tuple[str, ...]
    stop_reason: str


class _ClawResult(Protocol):
    candidates: tuple[_ClawCandidate, ...]
    sufficiency: Literal["sufficient", "partial", "insufficient"]
    reasons: tuple[str, ...]
    trace: _ClawTrace | None


class _ClawEvidenceBundle(Protocol):
    schema_version: str
    candidates: tuple[_ClawCandidate, ...]
    sufficiency: Literal["sufficient", "partial", "insufficient"]
    reasons: tuple[str, ...]
    trace: _ClawTrace


class _ClawObject(Protocol):
    locator: object
    text: str | None
    provenance: Literal["extracted", "inferred"]


class PaperClawAcademicRuntime(Protocol):
    def retrieve(self, query: object) -> _ClawResult: ...

    def evidence_bundle(self, result: _ClawResult) -> _ClawEvidenceBundle: ...

    def resolve(self, locator: object) -> _ClawObject: ...


class _ClawRetrievalResponse(Protocol):
    bundle: _ClawEvidenceBundle


class PaperClawRetrievalService(Protocol):
    def search(self, request: object) -> _ClawRetrievalResponse: ...

    def resolve_locator(self, locator: object) -> _ClawObject: ...


class _ArtifactRecord(Protocol):
    artifact_id: str
    artifact_type: str


class _ArtifactRevision(Protocol):
    revision_number: int
    content_hash: str


class PaperClawArtifactStore(Protocol):
    def create_artifact(
        self,
        **kwargs: Any,
    ) -> tuple[_ArtifactRecord, _ArtifactRevision, bool]: ...

    def add_revision(
        self,
        artifact_id: str,
        **kwargs: Any,
    ) -> tuple[_ArtifactRevision, bool]: ...

    def read_revision(
        self,
        artifact_id: str,
        revision_number: int | None = None,
    ) -> bytes: ...


def _academic_module() -> Any:
    return import_module("paperclaw.academic")


def _artifact_module() -> Any:
    return import_module("paperclaw.artifacts")


class PaperClawAcademicEvidenceSource:
    """Map PaperAgent retrieval rounds onto PaperClaw's canonical runtime."""

    def __init__(
        self,
        runtime: PaperClawAcademicRuntime | PaperClawRetrievalService,
    ) -> None:
        self.runtime = runtime

    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult:
        canonical = _academic_module()
        canonical_request = canonical.RetrievalRequest(
            text=request.query,
            channels=request.channels,
            paper_ids=request.paper_ids,
            object_types=request.object_types,
            budget=canonical.RetrievalBudget(
                max_candidates=request.max_candidates,
                max_chars=request.max_chars,
                max_primary_rounds=1,
                max_corrective_rounds=1 if request.round_kind == "corrective" else 0,
                max_conflict_rounds=1 if request.round_kind == "conflict" else 0,
            ),
        )
        if hasattr(self.runtime, "search"):
            result = self.runtime.search(canonical_request).bundle
        else:
            raw_result = self.runtime.retrieve(canonical_request)
            result = self.runtime.evidence_bundle(raw_result)
        if result.schema_version != "academic.v1":
            raise ValueError(f"unsupported PaperClaw academic schema: {result.schema_version!r}")
        if hasattr(result, "to_dict"):
            return normalize_bundle_payload(result.to_dict())
        trace = result.trace
        degraded = tuple(
            channel
            for channel in trace.degraded_channels
            if channel in {"lexical", "dense", "visual"}
        )
        sufficiency: SufficiencyDecision = result.sufficiency
        return AcademicRetrievalResult(
            candidates=tuple(self._candidate(item) for item in result.candidates),
            sufficiency=sufficiency,
            reasons=result.reasons,
            degraded_channels=cast(tuple[AcademicChannel, ...], degraded),
            conflict_detected=bool(trace.stop_reason in {"conflict", "conflict_detected"}),
            trace_id=trace.trace_id,
        )

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        canonical_locator = self._canonical_locator(locator)
        if hasattr(self.runtime, "resolve_locator"):
            resolved = self.runtime.resolve_locator(canonical_locator)
        else:
            resolved = self.runtime.resolve(canonical_locator)
        if resolved.locator != canonical_locator:
            raise ValueError("PaperClaw resolved a different academic locator")
        return AcademicCandidate(
            evidence_id=self._evidence_id(locator),
            locator=locator,
            text=resolved.text or "",
            score=1.0,
            provenance=resolved.provenance,
            channel_scores={},
            explanation=("paperclaw_resolve",),
        )

    @classmethod
    def _candidate(cls, candidate: _ClawCandidate) -> AcademicCandidate:
        locator = cls._locator(candidate.locator)
        return AcademicCandidate(
            evidence_id=cls._evidence_id(locator),
            locator=locator,
            text=candidate.text,
            score=max(0.0, candidate.fused_score),
            provenance=candidate.provenance,
            channel_scores={
                cast(AcademicChannel, channel): score
                for channel, score in candidate.channel_scores.items()
                if channel in {"exact", "lexical", "dense", "visual"}
            },
            explanation=candidate.explanation,
        )

    @staticmethod
    def _evidence_id(locator: AcademicLocator) -> str:
        return f"{locator.paper_id}:{locator.version_id}:{locator.object_id}"

    @staticmethod
    def _locator(locator: _ClawLocator) -> AcademicLocator:
        if locator.schema_version != "academic.v1":
            raise ValueError(f"unsupported PaperClaw locator schema: {locator.schema_version!r}")
        bbox = locator.bounding_box
        return AcademicLocator(
            schema_version="academic.v1",
            paper_id=locator.paper_id,
            version_id=locator.version_id,
            object_id=locator.object_id,
            page_number=locator.page_number,
            object_type=cast(AcademicObjectType, locator.object_type),
            source_hash=locator.source_hash,
            section_path=locator.section_path,
            bounding_box=((bbox.x0, bbox.y0, bbox.x1, bbox.y1) if bbox is not None else None),
            paragraph_index=locator.paragraph_index,
            line_range=locator.line_range,
            table_row=locator.table_row,
            table_column=locator.table_column,
        )

    @staticmethod
    def _canonical_locator(locator: AcademicLocator) -> object:
        canonical = _academic_module()
        bbox = (
            canonical.BoundingBox(*locator.bounding_box)
            if locator.bounding_box is not None
            else None
        )
        return canonical.EvidenceLocator(
            paper_id=locator.paper_id,
            version_id=locator.version_id,
            object_id=locator.object_id,
            page_number=locator.page_number,
            object_type=locator.object_type,
            source_hash=locator.source_hash,
            section_path=locator.section_path,
            bounding_box=bbox,
            paragraph_index=locator.paragraph_index,
            line_range=locator.line_range,
            table_row=locator.table_row,
            table_column=locator.table_column,
        )


def normalize_bundle_payload(payload: Mapping[str, Any]) -> AcademicRetrievalResult:
    """Normalize a canonical EvidenceBundle for both Python and REST seams."""

    if payload.get("schema_version") != "academic.v1":
        raise ValueError(
            f"unsupported PaperClaw academic schema: {payload.get('schema_version')!r}"
        )
    raw_trace = payload.get("trace")
    if not isinstance(raw_trace, Mapping):
        raise ValueError("PaperClaw EvidenceBundle trace is malformed")
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("PaperClaw EvidenceBundle candidates are malformed")
    candidates: list[AcademicCandidate] = []
    for raw in raw_candidates:
        if not isinstance(raw, Mapping):
            raise ValueError("PaperClaw evidence candidate is malformed")
        raw_locator = raw.get("locator")
        if not isinstance(raw_locator, Mapping):
            raise ValueError("PaperClaw evidence locator is malformed")
        locator_payload = dict(raw_locator)
        bbox = locator_payload.get("bounding_box")
        if isinstance(bbox, Mapping):
            locator_payload["bounding_box"] = (
                bbox["x0"],
                bbox["y0"],
                bbox["x1"],
                bbox["y1"],
            )
        locator = EvidenceLocatorView.model_validate(locator_payload)
        if raw.get("provenance") not in {"extracted", "inferred"}:
            raise ValueError("PaperClaw evidence provenance is incompatible")
        channel_scores = raw.get("channel_scores")
        if not isinstance(channel_scores, Mapping):
            raise ValueError("PaperClaw channel scores are malformed")
        candidates.append(
            AcademicCandidate(
                evidence_id=(f"{locator.paper_id}:{locator.version_id}:{locator.object_id}"),
                locator=locator,
                text=str(raw.get("text", "")),
                score=max(0.0, float(raw.get("fused_score", 0.0))),
                provenance=raw["provenance"],
                channel_scores={
                    cast(AcademicChannel, channel): float(score)
                    for channel, score in channel_scores.items()
                    if channel in {"exact", "lexical", "dense", "visual"}
                },
                explanation=tuple(raw.get("explanation", ())),
            )
        )
    sufficiency = payload.get("sufficiency")
    if sufficiency not in {"sufficient", "partial", "insufficient"}:
        raise ValueError("PaperClaw sufficiency state is incompatible")
    degraded = tuple(
        channel
        for channel in raw_trace.get("degraded_channels", ())
        if channel in {"lexical", "dense", "visual"}
    )
    return AcademicRetrievalResult(
        candidates=tuple(candidates),
        sufficiency=cast(SufficiencyDecision, sufficiency),
        reasons=tuple(payload.get("reasons", ())),
        degraded_channels=cast(tuple[AcademicChannel, ...], degraded),
        conflict_detected=raw_trace.get("stop_reason") in {"conflict", "conflict_detected"},
        trace_id=str(raw_trace.get("trace_id", "")),
    )


class PaperClawAcademicArtifactSink:
    """Persist PaperAgent drafts and review states as append-only PaperClaw revisions."""

    def __init__(self, store: PaperClawArtifactStore) -> None:
        self.store = store

    def create_draft(self, draft: AcademicArtifactDraft) -> AcademicArtifactRevision:
        if draft.state != "draft":
            raise ValueError("new artifact must be draft")
        content = self._content(draft)
        key = hashlib.sha256(content).hexdigest()
        record, revision, _ = self.store.create_artifact(
            idempotency_key=f"paperagent-academic-draft:{key}",
            artifact_type=draft.artifact_type,
            title=draft.title,
            media_type="application/json",
            content=content,
            source=_artifact_module().ArtifactSourceLinks(project_id=draft.project_id),
            metadata={"academic_state": "draft", "producer": "paperagent"},
            revision_message="PaperAgent academic draft",
        )
        return self._revision(record, revision, "draft")

    def review(
        self,
        artifact_id: str,
        *,
        decision: Literal["approved", "rejected"],
        note: str,
    ) -> AcademicArtifactRevision:
        current = self._read(artifact_id)
        if current.state != "draft":
            raise ValueError("only draft artifacts can be reviewed")
        clean_note = note.strip()
        if not clean_note:
            raise ValueError("review note must not be empty")
        updated = current.model_copy(update={"state": decision, "review_note": clean_note})
        revision, _ = self.store.add_revision(
            artifact_id,
            idempotency_key=self._revision_key(updated),
            media_type="application/json",
            content=self._content(updated),
            message=f"Human review: {decision}",
            metadata={"academic_state": decision},
        )
        return self._revision_for_id(
            artifact_id,
            revision,
            decision,
            current.artifact_type,
        )

    def finalize(self, artifact_id: str) -> AcademicArtifactRevision:
        current = self._read(artifact_id)
        if current.state != "approved":
            raise ValueError("final revision requires approved artifact")
        updated = current.model_copy(update={"state": "final"})
        revision, _ = self.store.add_revision(
            artifact_id,
            idempotency_key=self._revision_key(updated),
            media_type="application/json",
            content=self._content(updated),
            message="Approved academic artifact finalized",
            metadata={"academic_state": "final"},
        )
        return self._revision_for_id(
            artifact_id,
            revision,
            "final",
            current.artifact_type,
        )

    def _read(self, artifact_id: str) -> AcademicArtifactDraft:
        return AcademicArtifactDraft.model_validate_json(self.store.read_revision(artifact_id))

    @staticmethod
    def _content(draft: AcademicArtifactDraft) -> bytes:
        return json.dumps(
            draft.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @classmethod
    def _revision_key(cls, draft: AcademicArtifactDraft) -> str:
        digest = hashlib.sha256(cls._content(draft)).hexdigest()
        return f"paperagent-academic-revision:{digest}"

    @staticmethod
    def _revision(
        record: _ArtifactRecord,
        revision: _ArtifactRevision,
        state: Literal["draft", "approved", "rejected", "final"],
    ) -> AcademicArtifactRevision:
        return PaperClawAcademicArtifactSink._revision_for_id(
            record.artifact_id,
            revision,
            state,
            cast(AcademicArtifactType, record.artifact_type),
        )

    @staticmethod
    def _revision_for_id(
        artifact_id: str,
        revision: _ArtifactRevision,
        state: Literal["draft", "approved", "rejected", "final"],
        artifact_type: AcademicArtifactType,
    ) -> AcademicArtifactRevision:
        return AcademicArtifactRevision(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            revision_number=revision.revision_number,
            state=state,
            content_hash=revision.content_hash,
        )

from __future__ import annotations

import hashlib
import json

from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicChannel,
    AcademicLocator,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
    SufficiencyDecision,
)
from paperagent.projects.models import SearchHit
from paperagent.projects.rag import HybridAcademicRetriever
from paperagent.projects.repository import SQLiteProjectRepository


class ProjectRAGEvidenceSource:
    """Compatibility adapter for the current text-only Project RAG vertical."""

    def __init__(
        self,
        repository: SQLiteProjectRepository,
        retriever: HybridAcademicRetriever | None = None,
    ) -> None:
        self.repository = repository
        self.retriever = retriever or HybridAcademicRetriever(repository)
        self._resolved: dict[tuple[str, str, str], AcademicCandidate] = {}

    def retrieve(self, request: AcademicRetrievalRequest) -> AcademicRetrievalResult:
        hits = self.retriever.search(
            project_id=request.project_id,
            query=request.query,
            limit=request.max_candidates,
            paper_ids=request.paper_ids or None,
        )
        candidates = tuple(self._candidate(request.project_id, hit) for hit in hits)
        for candidate in candidates:
            key = (
                candidate.locator.paper_id,
                candidate.locator.version_id,
                candidate.locator.object_id,
            )
            self._resolved[key] = candidate
        degraded: tuple[AcademicChannel, ...] = ("visual",) if "visual" in request.channels else ()
        if not candidates:
            sufficiency: SufficiencyDecision = "insufficient"
            reasons = ("no project evidence matched",)
        elif candidates[0].score >= 0.2:
            sufficiency = "sufficient"
            reasons = ("text fallback evidence matched",)
        else:
            sufficiency = "partial"
            reasons = ("weak text fallback evidence matched",)
        fingerprint = hashlib.sha256(
            json.dumps(
                request.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return AcademicRetrievalResult(
            candidates=candidates,
            sufficiency=sufficiency,
            reasons=reasons,
            degraded_channels=degraded,
            conflict_detected=False,
            trace_id=f"project-rag:{fingerprint}",
        )

    def resolve(self, locator: AcademicLocator) -> AcademicCandidate:
        key = (locator.paper_id, locator.version_id, locator.object_id)
        try:
            candidate = self._resolved[key]
        except KeyError as exc:
            raise KeyError("academic locator was not produced by this adapter") from exc
        if candidate.locator.source_hash != locator.source_hash:
            raise KeyError("academic locator source hash mismatch")
        return candidate

    def _candidate(self, project_id: str, hit: SearchHit) -> AcademicCandidate:
        paper = self.repository.get_latest_paper(
            project_id=project_id,
            paper_id=hit.unit.paper_id,
        )
        locator = AcademicLocator(
            paper_id=hit.unit.paper_id,
            version_id=f"{hit.unit.paper_id}:v{hit.unit.ingestion_version}",
            object_id=hit.unit.unit_id,
            page_number=hit.unit.page or 1,
            object_type="paragraph",
            source_hash=paper.content_sha256,
            section_path=(hit.unit.section,) if hit.unit.section else (),
            paragraph_index=(hit.unit.paragraph - 1 if hit.unit.paragraph is not None else None),
        )
        return AcademicCandidate(
            evidence_id=hit.unit.unit_id,
            locator=locator,
            text=hit.unit.content,
            score=hit.score,
            provenance="extracted",
            channel_scores={
                "lexical": hit.lexical_score,
                "dense": hit.semantic_score,
            },
            explanation=("paperagent_project_rag_text_fallback",),
        )

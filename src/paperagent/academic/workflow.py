from __future__ import annotations

import re
from typing import Literal

from paperagent.academic.contracts import (
    AcademicCandidate,
    AcademicChannel,
    AcademicEvidenceEntry,
    AcademicEvidenceLedger,
    AcademicEvidenceSource,
    AcademicObjectType,
    AcademicQueryKind,
    AcademicQueryPlan,
    AcademicRAGResult,
    AcademicRetrievalRequest,
    AcademicRetrievalResult,
    RetrievalRoundKind,
    SufficiencyDecision,
)

_DOI = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b", re.IGNORECASE)
_ARXIV = re.compile(r"\barXiv:\d{4}\.\d{4,5}\b", re.IGNORECASE)


def _route(question: str) -> AcademicQueryPlan:
    clean = question.strip()
    if not clean:
        raise ValueError("question must not be empty")
    identifiers = tuple(dict.fromkeys((*_DOI.findall(clean), *_ARXIV.findall(clean))))
    lowered = clean.casefold()
    kind: AcademicQueryKind
    channels: tuple[AcademicChannel, ...]
    object_types: tuple[AcademicObjectType, ...]
    if identifiers:
        kind, channels, object_types = "identity", ("exact", "lexical"), ()
    elif any(token in lowered for token in ("figure", "architecture diagram", "架构图", "图")):
        kind = "figure"
        channels = ("visual", "lexical", "dense")
        object_types = ("figure", "caption", "page")
    elif any(token in lowered for token in ("table", "表格", "表 ")):
        kind = "table"
        channels = ("exact", "lexical", "dense", "visual")
        object_types = ("table", "table_cell", "caption", "page")
    elif any(token in lowered for token in ("equation", "formula", "公式")):
        kind = "equation"
        channels = ("lexical", "dense", "visual")
        object_types = ("equation", "paragraph", "page")
    elif any(token in lowered for token in ("compare", "comparison", "比较", "对比")):
        kind = "comparison"
        channels = ("exact", "lexical", "dense")
        object_types = ("section", "paragraph", "table", "table_cell")
    elif any(token in lowered for token in ("baseline", "module", "模块", "消融", "ablation")):
        kind = "tailoring"
        channels = ("exact", "lexical", "dense")
        object_types = ("section", "paragraph", "table", "table_cell")
    else:
        kind = "method"
        channels = ("lexical", "dense")
        object_types = ("section", "paragraph", "algorithm", "equation")
    rewritten = clean
    for identifier in identifiers:
        if identifier not in rewritten:
            rewritten = f"{rewritten} {identifier}"
    return AcademicQueryPlan(
        kind=kind,
        original_question=clean,
        rewritten_query=rewritten,
        exact_identifiers=identifiers,
        channels=channels,
        object_types=object_types,
    )


class AcademicRAGWorkflow:
    def __init__(self, source: AcademicEvidenceSource) -> None:
        self.source = source

    def run(
        self,
        *,
        project_id: str,
        question: str,
        paper_ids: tuple[str, ...] = (),
    ) -> AcademicRAGResult:
        plan = _route(question)
        rounds: dict[RetrievalRoundKind, int] = {
            "primary": 0,
            "corrective": 0,
            "conflict": 0,
        }
        results: list[AcademicRetrievalResult] = []
        primary = self._retrieve(project_id, plan, "primary", paper_ids)
        rounds["primary"] = 1
        results.append(primary)
        current = primary
        if current.sufficiency in {"insufficient", "blocked"}:
            current = self._retrieve(project_id, plan, "corrective", paper_ids)
            rounds["corrective"] = 1
            results.append(current)
        if current.conflict_detected:
            current = self._retrieve(project_id, plan, "conflict", paper_ids)
            rounds["conflict"] = 1
            results.append(current)

        sufficiency: SufficiencyDecision = current.sufficiency
        stop_reason: str = current.sufficiency
        degraded = {channel for result in results for channel in result.degraded_channels}
        if "visual" in plan.channels and "visual" in degraded and sufficiency == "sufficient":
            sufficiency = "partial"
            stop_reason = "visual_channel_degraded"
        ledger = self._build_ledger(results)
        return AcademicRAGResult(
            project_id=project_id,
            query_plan=plan,
            ledger=ledger,
            sufficiency=sufficiency,
            reasons=current.reasons,
            trace_ids=tuple(result.trace_id for result in results),
            rounds_used=rounds,
            stop_reason=stop_reason,
        )

    def _retrieve(
        self,
        project_id: str,
        plan: AcademicQueryPlan,
        round_kind: RetrievalRoundKind,
        paper_ids: tuple[str, ...],
    ) -> AcademicRetrievalResult:
        channels = plan.channels
        if round_kind == "corrective":
            channels = tuple(dict.fromkeys((*channels, "exact", "visual")))
        return self.source.retrieve(
            AcademicRetrievalRequest(
                project_id=project_id,
                query=plan.rewritten_query,
                original_question=plan.original_question,
                kind=plan.kind,
                round_kind=round_kind,
                channels=channels,
                paper_ids=paper_ids,
                object_types=plan.object_types,
            )
        )

    def _build_ledger(
        self,
        results: list[AcademicRetrievalResult],
    ) -> AcademicEvidenceLedger:
        latest: dict[str, AcademicCandidate] = {}
        conflicted: set[str] = set()
        for result in results:
            for candidate in result.candidates:
                if (
                    candidate.evidence_id in latest
                    and latest[candidate.evidence_id].text != candidate.text
                ):
                    conflicted.add(candidate.evidence_id)
                latest[candidate.evidence_id] = candidate
        entries: list[AcademicEvidenceEntry] = []
        for candidate in latest.values():
            rejection_reasons: tuple[str, ...] = ()
            status: Literal["accepted", "rejected", "conflicted"] = "accepted"
            if candidate.evidence_id in conflicted:
                status = "conflicted"
            else:
                try:
                    resolved = self.source.resolve(candidate.locator)
                    if resolved.locator != candidate.locator:
                        status = "rejected"
                        rejection_reasons = ("locator_resolution_mismatch",)
                except (KeyError, OSError, RuntimeError, ValueError):
                    status = "rejected"
                    rejection_reasons = ("locator_unresolvable",)
            entries.append(
                AcademicEvidenceEntry(
                    evidence_id=candidate.evidence_id,
                    locator=candidate.locator,
                    status=status,
                    limitations=(
                        ("inferred evidence requires human confirmation",)
                        if candidate.provenance == "inferred"
                        else ()
                    ),
                    rejection_reasons=rejection_reasons,
                )
            )
        return AcademicEvidenceLedger(
            entries=tuple(entries),
            accepted_ids=tuple(
                entry.evidence_id for entry in entries if entry.status == "accepted"
            ),
            rejected_ids=tuple(
                entry.evidence_id for entry in entries if entry.status == "rejected"
            ),
            conflicted_ids=tuple(
                entry.evidence_id for entry in entries if entry.status == "conflicted"
            ),
        )

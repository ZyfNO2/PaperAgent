from __future__ import annotations

import re
from typing import Literal

from paperagent.academic.claims import (
    check_citation_claim_mismatch,
    generate_claims_from_ledger,
)
from paperagent.academic.context import (
    AcademicEvidenceInsufficientError,
    build_accepted_context_manifest,
)
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
from paperagent.academic.planner import AcademicSubQuery, decompose_question

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
        decomposition = decompose_question(question, paper_ids=paper_ids)
        rounds: dict[RetrievalRoundKind, int] = {
            "primary": 0,
            "corrective": 0,
            "conflict": 0,
        }
        results: list[AcademicRetrievalResult] = []
        current: AcademicRetrievalResult | None = None
        for sub_query in decomposition.sub_queries:
            current = self._retrieve(project_id, plan, sub_query, "primary")
            rounds["primary"] += 1
            results.append(current)
            if current.sufficiency in {"insufficient", "blocked"}:
                current = self._retrieve(project_id, plan, sub_query, "corrective")
                rounds["corrective"] += 1
                results.append(current)
            if current.conflict_detected:
                current = self._retrieve(project_id, plan, sub_query, "conflict")
                rounds["conflict"] += 1
                results.append(current)
        if current is None:  # pragma: no cover - planner guarantees one sub-query
            raise RuntimeError("academic planner produced no sub-queries")

        sufficiency: SufficiencyDecision = current.sufficiency
        stop_reason: str = current.sufficiency
        degraded = {channel for result in results for channel in result.degraded_channels}
        if "visual" in plan.channels and "visual" in degraded and sufficiency == "sufficient":
            sufficiency = "partial"
            stop_reason = "visual_channel_degraded"
        ledger = self._build_ledger(results)
        context_ids: tuple[str, ...] = ()
        generated_claim_texts: tuple[str, ...] = ()
        mismatch_kinds: tuple[str, ...] = ()
        if ledger.accepted_ids:
            try:
                context = build_accepted_context_manifest(
                    ledger,
                    self.source,
                    character_budget=min(
                        100_000,
                        sum(item.character_budget for item in decomposition.sub_queries),
                    ),
                    token_budget=sum(item.token_budget for item in decomposition.sub_queries),
                    retrieval_trace_ids=tuple(result.trace_id for result in results),
                )
                claims = generate_claims_from_ledger(
                    ledger,
                    self.source,
                    question=question,
                )
                mismatches = check_citation_claim_mismatch(claims, self.source)
                context_ids = context.evidence_ids
                generated_claim_texts = tuple(item.text for item in claims)
                mismatch_kinds = tuple(item.kind for item in mismatches)
                if mismatches:
                    sufficiency = "blocked"
                    stop_reason = "citation_semantic_mismatch"
            except AcademicEvidenceInsufficientError:
                sufficiency = "blocked"
                stop_reason = "accepted_context_unresolvable"
        return AcademicRAGResult(
            project_id=project_id,
            query_plan=plan,
            ledger=ledger,
            sufficiency=sufficiency,
            reasons=current.reasons,
            trace_ids=tuple(result.trace_id for result in results),
            rounds_used=rounds,
            stop_reason=stop_reason,
            decomposition_strategy=decomposition.strategy,
            sub_query_ids=tuple(item.sub_query_id for item in decomposition.sub_queries),
            context_evidence_ids=context_ids,
            generated_claims=generated_claim_texts,
            citation_mismatches=mismatch_kinds,
            retrieval_candidates=tuple(
                {item.evidence_id: item for result in results for item in result.candidates}.values()
            ),
            retrieval_trace_details=tuple(result.trace_details for result in results),
        )

    def _retrieve(
        self,
        project_id: str,
        plan: AcademicQueryPlan,
        sub_query: AcademicSubQuery,
        round_kind: RetrievalRoundKind,
    ) -> AcademicRetrievalResult:
        channels = sub_query.channels
        query = sub_query.rewritten_query
        if round_kind == "corrective":
            channels = tuple(dict.fromkeys((*channels, "exact")))
            if sub_query.corrective_reason:
                query = f"{query} {sub_query.corrective_reason}".strip()
        elif round_kind == "conflict":
            channels = tuple(dict.fromkeys(("exact", "lexical", "dense", *channels)))
            query = f"{query} resolve metric unit dataset split active version"
        return self.source.retrieve(
            AcademicRetrievalRequest(
                project_id=project_id,
                query=query,
                original_question=plan.original_question,
                kind=plan.kind,
                round_kind=round_kind,
                channels=channels,
                paper_ids=sub_query.paper_ids,
                object_types=sub_query.object_types,
                section_scope=sub_query.section_scope,
                max_candidates=sub_query.result_budget,
                max_chars=sub_query.character_budget,
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

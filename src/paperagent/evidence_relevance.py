from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal, cast

from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.relevance import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    EvidenceScope,
    GapSupportAssessment,
    GapSupportType,
    LexicalRelevanceAssessment,
    RelevanceAssessment,
    ResearchContract,
)
from paperagent.telemetry import hash_payload

_STOPWORDS = frozenset(
    {
        "about",
        "after",
        "against",
        "analysis",
        "approach",
        "based",
        "between",
        "could",
        "evaluate",
        "evaluation",
        "evidence",
        "method",
        "paper",
        "problem",
        "research",
        "result",
        "study",
        "system",
        "using",
        "with",
        "would",
    }
)


def _terms(text: str | None) -> list[str]:
    if not text:
        return []
    raw = re.findall(r"[a-z][a-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}", text.lower())
    output: list[str] = []
    for value in raw:
        normalized = value.strip("_-")
        if len(normalized) < 3 or normalized in _STOPWORDS or normalized in output:
            continue
        output.append(normalized)
    return output


def _dedupe(
    values: Iterable[str],
    *,
    limit: int = 64,
    lowercase: bool = True,
) -> list[str]:
    output: list[str] = []
    for raw in values:
        stripped = raw.strip()
        value = stripped.lower() if lowercase else stripped
        if value and value not in output:
            output.append(value)
        if len(output) >= limit:
            break
    return output


def derive_research_contract(
    request: ResearchRequest | None,
    plan: ResearchPlan | None,
) -> ResearchContract:
    required_gaps = [gap.gap_id for gap in plan.evidence_gaps if gap.required] if plan else []
    positive_sources: list[str] = []
    if request is not None:
        positive_sources.extend(_terms(request.question))
        positive_sources.extend(_terms(request.domain_hint))
        for constraint in request.required_constraints:
            positive_sources.extend(_terms(constraint))
    if plan is not None:
        positive_sources.extend(_terms(plan.problem_statement))
        positive_sources.extend(_terms(plan.scope))
        for question in plan.research_questions:
            positive_sources.extend(_terms(question))
        for gap in plan.evidence_gaps:
            positive_sources.extend(_terms(gap.description))
        for query in plan.search_queries:
            positive_sources.extend(_terms(query.query))
        for criterion in plan.success_criteria:
            positive_sources.extend(_terms(criterion))
    problem_terms = _terms(plan.problem_statement) if plan is not None else []
    return ResearchContract(
        task_type=problem_terms[0] if problem_terms else None,
        domain=request.domain_hint if request else None,
        deployment_constraints=list(request.required_constraints) if request else [],
        research_claim=(
            plan.problem_statement if plan else (request.question if request else None)
        ),
        positive_terms=_dedupe(positive_sources),
        required_gap_ids=required_gaps,
        assumptions=list(plan.risks) if plan else [],
    )


def assess_lexical_relevance(
    item: EvidenceItem,
    contract: ResearchContract,
) -> LexicalRelevanceAssessment:
    text = f"{item.title}\n{item.summary}".lower()
    matched = [term for term in contract.positive_terms if term in text]
    negative = [term for term in contract.negative_terms if term in text]
    domain_terms = _terms(contract.domain)
    domain_matches = [term for term in domain_terms if term in text]
    missing_mandatory = [] if not domain_terms or domain_matches else domain_terms
    strict_contract = len(contract.positive_terms) >= 2 or bool(domain_terms)
    reason_codes: list[str] = []
    decision: Literal["pass", "reject"] = "pass"
    if negative:
        decision = "reject"
        reason_codes.append("LEXICAL_NEGATIVE_MATCH")
    elif missing_mandatory:
        decision = "reject"
        reason_codes.append("DOMAIN_MISMATCH")
    elif strict_contract and not matched:
        decision = "reject"
        reason_codes.append("LEXICAL_NO_MATCH")
    elif not strict_contract:
        reason_codes.append("LEXICAL_WEAK_CONTRACT_COMPATIBILITY")
    denominator = max(1, min(5, len(contract.positive_terms)))
    score = min(1.0, len(matched) / denominator)
    if not strict_contract and decision == "pass":
        score = max(score, 0.5)
    return LexicalRelevanceAssessment(
        evidence_id=item.evidence_id,
        lexical_score=score,
        matched_terms=matched,
        missing_mandatory_terms=missing_mandatory,
        negative_matches=negative,
        decision=decision,
        reason_codes=reason_codes,
    )


def _supporting_spans(item: EvidenceItem, matched_terms: list[str]) -> list[str]:
    text = f"{item.title}. {item.summary}".strip()
    spans: list[str] = []
    for sentence in re.split(r"(?<=[.!?。])\s+", text):
        normalized = sentence.lower()
        if any(term in normalized for term in matched_terms):
            span = sentence.strip()
            if span and span not in spans:
                spans.append(span)
    return spans[:3]


def assess_abstract_relevance(
    item: EvidenceItem,
    contract: ResearchContract,
    lexical: LexicalRelevanceAssessment,
) -> RelevanceAssessment:
    fixture_scope_raw = item.metadata.get("relevance_scope")
    fixture_spans = [
        value.strip()
        for value in item.metadata.get("supporting_spans", "").split("||")
        if value.strip()
    ]
    valid_scopes = {"direct", "indirect", "background_only", "irrelevant"}
    if fixture_scope_raw in valid_scopes:
        fixture_scope = cast(EvidenceScope, fixture_scope_raw)
        fixture_decision: Literal["pass", "reject"] = (
            "pass" if fixture_scope in {"direct", "indirect"} and fixture_spans else "reject"
        )
        return RelevanceAssessment(
            evidence_id=item.evidence_id,
            task_match=fixture_decision == "pass",
            domain_match=not lexical.missing_mandatory_terms,
            evidence_scope=fixture_scope,
            relevance_score=float(item.metadata.get("relevance_score", lexical.lexical_score)),
            decision=fixture_decision,
            supporting_spans=fixture_spans,
            conflict_spans=[],
            reason_codes=[
                item.metadata.get(
                    "relevance_reason",
                    "FIXTURE_RELEVANCE_ASSESSMENT",
                )
            ],
            assessment_source="fixture",
        )
    if lexical.decision == "reject":
        return RelevanceAssessment(
            evidence_id=item.evidence_id,
            task_match=False,
            domain_match=not lexical.missing_mandatory_terms,
            evidence_scope="irrelevant",
            relevance_score=lexical.lexical_score,
            decision="reject",
            supporting_spans=[],
            conflict_spans=[item.title],
            reason_codes=[
                *lexical.reason_codes,
                "ABSTRACT_REJECTED_BY_LEXICAL_GATE",
            ],
        )
    spans = _supporting_spans(item, lexical.matched_terms)
    if not spans:
        spans = [item.summary.strip() or item.title.strip()]
    scope: EvidenceScope = (
        "direct" if len(lexical.matched_terms) >= 2 or lexical.lexical_score >= 0.4 else "indirect"
    )
    return RelevanceAssessment(
        evidence_id=item.evidence_id,
        task_match=True,
        domain_match=True,
        evidence_scope=scope,
        relevance_score=max(
            lexical.lexical_score,
            0.5 if scope == "direct" else 0.35,
        ),
        decision="pass",
        supporting_spans=spans[:3],
        conflict_spans=[],
        reason_codes=["ABSTRACT_SUPPORTING_SPAN_PRESENT"],
    )


def _candidate_gap_ids(item: EvidenceItem) -> set[str]:
    values = item.metadata.get("candidate_gap_ids", "")
    return {value.strip() for value in values.split(",") if value.strip()} | set(
        item.supports_gap_ids
    )


def assess_gap_support(
    item: EvidenceItem,
    gap: EvidenceGap,
    relevance: RelevanceAssessment,
) -> GapSupportAssessment:
    if relevance.decision == "reject":
        return GapSupportAssessment(
            evidence_id=item.evidence_id,
            gap_id=gap.gap_id,
            support_type="unrelated",
            checklist_results={
                "relevance_passed": False,
                "gap_overlap": False,
            },
            limitations=["evidence failed relevance assessment"],
            confidence=0.0,
            decision="reject",
        )
    gap_terms = _terms(gap.description) + _terms(gap.gap_id.replace("-", " "))
    normalized_gap_terms = _dedupe(gap_terms)
    text = f"{item.title}\n{item.summary}".lower()
    overlap = [term for term in normalized_gap_terms if term in text]
    origin_match = gap.gap_id in _candidate_gap_ids(item)
    weak_gap = not normalized_gap_terms
    accepted = bool(overlap) or (origin_match and weak_gap)
    if not accepted:
        return GapSupportAssessment(
            evidence_id=item.evidence_id,
            gap_id=gap.gap_id,
            support_type="insufficient",
            checklist_results={
                "relevance_passed": True,
                "gap_overlap": False,
                "query_provenance_match": origin_match,
            },
            limitations=["no claim-level overlap with the requested gap"],
            confidence=0.2 if origin_match else 0.0,
            decision="reject",
        )
    span = relevance.supporting_spans[0]
    support_type: GapSupportType = (
        "direct_support" if relevance.evidence_scope == "direct" else "indirect_support"
    )
    return GapSupportAssessment(
        evidence_id=item.evidence_id,
        gap_id=gap.gap_id,
        support_type=support_type,
        supported_claim=gap.description,
        supporting_span_hash=hash_payload(span),
        checklist_results={
            "relevance_passed": True,
            "gap_overlap": bool(overlap),
            "query_provenance_match": origin_match,
        },
        limitations=(
            [] if overlap else ["accepted from explicit query provenance under a weak gap"]
        ),
        confidence=0.9 if overlap and origin_match else 0.7 if overlap else 0.55,
        decision="accept",
    )


def build_evidence_ledger(
    *,
    request: ResearchRequest | None,
    plan: ResearchPlan | None,
    evidence: EvidenceBundle,
) -> tuple[
    ResearchContract,
    list[LexicalRelevanceAssessment],
    list[RelevanceAssessment],
    list[GapSupportAssessment],
    EvidenceLedger,
]:
    contract = derive_research_contract(request, plan)
    lexical_results: list[LexicalRelevanceAssessment] = []
    relevance_results: list[RelevanceAssessment] = []
    gap_results: list[GapSupportAssessment] = []
    entries: list[EvidenceLedgerEntry] = []
    gaps = list(plan.evidence_gaps) if plan is not None else []
    for item in evidence.items:
        identity_verified = item.verification_status == "accepted"
        lexical = assess_lexical_relevance(item, contract)
        relevance = assess_abstract_relevance(item, contract, lexical)
        lexical_results.append(lexical)
        relevance_results.append(relevance)
        supports = [assess_gap_support(item, gap, relevance) for gap in gaps]
        if not gaps and identity_verified and relevance.decision == "pass":
            for gap_id in sorted(_candidate_gap_ids(item)):
                span = relevance.supporting_spans[0]
                support_type: GapSupportType = (
                    "direct_support" if relevance.evidence_scope == "direct" else "indirect_support"
                )
                supports.append(
                    GapSupportAssessment(
                        evidence_id=item.evidence_id,
                        gap_id=gap_id,
                        support_type=support_type,
                        supported_claim=gap_id,
                        supporting_span_hash=hash_payload(span),
                        checklist_results={
                            "relevance_passed": True,
                            "gap_overlap": True,
                            "query_provenance_match": True,
                        },
                        confidence=0.6,
                        decision="accept",
                    )
                )
        gap_results.extend(supports)
        accepted_supports = [support for support in supports if support.decision == "accept"]
        accepted = (
            identity_verified
            and relevance.decision == "pass"
            and (bool(accepted_supports) or not gaps)
        )
        rejection_reasons: list[str] = []
        if not identity_verified:
            rejection_reasons.append("IDENTITY_NOT_VERIFIED")
        if relevance.decision == "reject":
            rejection_reasons.extend(relevance.reason_codes)
        if gaps and not accepted_supports:
            rejection_reasons.append("NO_VALID_GAP_BINDING")
        supported_claims = [
            support.supported_claim
            for support in accepted_supports
            if support.supported_claim is not None
        ]
        entries.append(
            EvidenceLedgerEntry(
                evidence_id=item.evidence_id,
                identity_verified=identity_verified,
                relevance_scope=relevance.evidence_scope,
                gap_supports=supports,
                supported_claims=supported_claims,
                limitations=[
                    limitation for support in supports for limitation in support.limitations
                ],
                accepted=accepted,
                rejection_reasons=_dedupe(
                    rejection_reasons,
                    lowercase=False,
                ),
            )
        )
    accepted_ids = [entry.evidence_id for entry in entries if entry.accepted]
    rejected_ids = [entry.evidence_id for entry in entries if not entry.accepted]
    coverage: dict[str, int] = {}
    for entry in entries:
        if not entry.accepted:
            continue
        for support in entry.gap_supports:
            if support.decision == "accept":
                coverage[support.gap_id] = coverage.get(support.gap_id, 0) + 1
    ledger = EvidenceLedger(
        entries=entries,
        accepted_ids=accepted_ids,
        rejected_ids=rejected_ids,
        coverage_by_gap=coverage,
    )
    return contract, lexical_results, relevance_results, gap_results, ledger


def apply_ledger_to_bundle(
    evidence: EvidenceBundle,
    ledger: EvidenceLedger,
) -> EvidenceBundle:
    accepted = set(ledger.accepted_ids)
    accepted_gaps = {
        entry.evidence_id: sorted(
            support.gap_id for support in entry.gap_supports if support.decision == "accept"
        )
        for entry in ledger.entries
    }
    items = [
        item.model_copy(
            update={
                "supports_gap_ids": accepted_gaps.get(item.evidence_id, []),
            }
        )
        for item in evidence.items
    ]
    identity_verified_ids = [
        item.evidence_id for item in items if item.verification_status == "accepted"
    ]
    relevance_rejected_ids = sorted(set(identity_verified_ids) - accepted)
    return EvidenceBundle(
        items=items,
        accepted_ids=ledger.accepted_ids,
        identity_verified_ids=identity_verified_ids,
        relevance_rejected_ids=relevance_rejected_ids,
        rejected_ids=evidence.rejected_ids,
        pending_ids=evidence.pending_ids,
        failed_verification_ids=evidence.failed_verification_ids,
        coverage_by_gap=ledger.coverage_by_gap,
        conflicts=evidence.conflicts,
    )


__all__ = [
    "apply_ledger_to_bundle",
    "assess_abstract_relevance",
    "assess_gap_support",
    "assess_lexical_relevance",
    "build_evidence_ledger",
    "derive_research_contract",
]

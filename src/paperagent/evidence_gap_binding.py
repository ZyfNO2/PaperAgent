from __future__ import annotations

import re
from collections.abc import Iterable

from paperagent import evidence_relevance as legacy
from paperagent.literature.query_concepts import matches_required_candidate_terms
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
    GapSupportAssessment,
    GapSupportType,
    LexicalRelevanceAssessment,
    RelevanceAssessment,
    ResearchContract,
)
from paperagent.telemetry import hash_payload

_ROLE_ONLY_TERMS = frozenset(
    {
        "baseline",
        "comparison",
        "comparative",
        "strong",
        "reproducible",
        "reproduction",
        "parallel",
        "mechanism",
        "limitation",
        "limitations",
        "failure",
        "risk",
        "negative",
        "claim",
        "support",
    }
)
_BASELINE_ROLE_HINTS = (
    "baseline",
    "comparison",
    "strong_comparison",
    "基线",
    "比较",
    "对比",
)
_MECHANISM_ROLE_HINTS = (
    "mechanism",
    "parallel",
    "intervention",
    "failure_mechanism",
    "机制",
    "并行",
    "改进",
)
_RISK_ROLE_HINTS = (
    "risk",
    "negative",
    "limitation",
    "failure",
    "风险",
    "负面",
    "局限",
    "失败",
)
_METRIC_PATTERN = re.compile(
    r"\b(?:m?ap(?:50|75|_small)?|f1|auc|accuracy|precision|recall|fps|latency|"
    r"flops?|parameters?|params?|memory|energy|power)\b",
    re.IGNORECASE,
)


def _dedupe(values: Iterable[str]) -> list[str]:
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in output:
            output.append(value)
    return output


def _candidate_gap_ids(item: EvidenceItem) -> set[str]:
    values = item.metadata.get("candidate_gap_ids", "")
    return {value.strip() for value in values.split(",") if value.strip()} | set(
        item.supports_gap_ids
    )


def _gap_role(gap: EvidenceGap) -> str:
    text = f"{gap.gap_id} {gap.description}".casefold()
    if any(value in text for value in _BASELINE_ROLE_HINTS):
        return "baseline"
    if any(value in text for value in _MECHANISM_ROLE_HINTS):
        return "mechanism"
    if any(value in text for value in _RISK_ROLE_HINTS):
        return "risk"
    return "general"


def _query_terms(query_texts: Iterable[str]) -> list[str]:
    terms = [term for query in query_texts for term in legacy._terms(query)]
    return _dedupe(term for term in terms if term not in _ROLE_ONLY_TERMS)


def _query_overlap(item: EvidenceItem, query_texts: Iterable[str]) -> list[str]:
    text = f"{item.title}\n{item.summary}".casefold()
    return [term for term in _query_terms(query_texts) if term in text]


def _baseline_role_support(text: str) -> bool:
    evaluation_context = any(
        cue in text
        for cue in (
            "dataset",
            "benchmark",
            "experimental result",
            "experiment result",
            "evaluation",
            "test set",
            "validation set",
        )
    )
    measured_result = bool(_METRIC_PATTERN.search(text))
    comparison = any(
        cue in text
        for cue in (
            "compared",
            "comparison",
            "baseline",
            "outperform",
            "improvement over",
            "enhancement over",
            "versus",
            " than ",
        )
    )
    return sum((evaluation_context, measured_result, comparison)) >= 2


def _mechanism_role_support(text: str) -> bool:
    problem = any(
        cue in text
        for cue in (
            "challenge",
            "limitation",
            "failure",
            "difficult",
            "occlusion",
            "small object",
            "tiny object",
            "complex background",
            "redundant computation",
            "low-light",
            "low light",
            "nighttime",
            "less effective",
            "drawback",
            "low-resolution",
            "low resolution",
            "noise",
            "degradation",
            "background interference",
            "illumination",
            "domain shift",
            "distribution shift",
            "missing modality",
            "modality absence",
            "misregistration",
            "computational and energy requests",
            "computational request",
            "energy request",
            "energy demand",
            "temporal order",
            "similar poses",
            "crowded scene",
            "complex environment",
        )
    )
    intervention = any(
        cue in text
        for cue in (
            "we propose",
            "we introduce",
            "module",
            "architecture",
            "network",
            "feature fusion",
            "attention",
            "self-attention",
            "self-attentional",
            "loss",
            "branch",
            "detection head",
            "super-resolution",
            "temporal",
            "pose representation",
            "multimodal",
        )
    )
    return problem and intervention


def _risk_role_support(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "limitation",
            "failure",
            "degradation",
            "performance drop",
            "bottleneck",
            "unacceptable",
            "challenge",
            "high latency",
            "power consumption",
            "energy consumption",
            "computational cost",
            "occlusion",
            "domain shift",
        )
    )


def _role_support(gap: EvidenceGap, item: EvidenceItem) -> bool:
    text = f"{item.title}. {item.summary}".casefold()
    role = _gap_role(gap)
    if role == "baseline":
        return _baseline_role_support(text)
    if role == "mechanism":
        return _mechanism_role_support(text)
    if role == "risk":
        return _risk_role_support(text)
    return True


def assess_gap_support(
    item: EvidenceItem,
    gap: EvidenceGap,
    relevance: RelevanceAssessment,
    *,
    query_texts: Iterable[str] = (),
    allow_cross_gap_reuse: bool = False,
) -> GapSupportAssessment:
    """Apply the legacy binding first, then a strict cross-language semantic fallback.

    The fallback never treats provenance or prior acceptance as sufficient by itself. It
    requires direct relevance, a supporting span, query-specific concept coverage,
    query-term overlap, and evidence structure appropriate for the declared gap role.
    """

    legacy_result = legacy.assess_gap_support(item, gap, relevance)
    if legacy_result.decision == "accept" or relevance.decision == "reject":
        return legacy_result

    queries = tuple(value for value in query_texts if value.strip())
    origin_match = gap.gap_id in _candidate_gap_ids(item)
    cross_gap_reuse = allow_cross_gap_reuse and not origin_match
    provenance_qualified = origin_match or cross_gap_reuse
    direct_relevance = relevance.evidence_scope == "direct"
    supporting_span_present = bool(relevance.supporting_spans)
    overlap = _query_overlap(item, queries)
    query_term_overlap = len(overlap) >= 2
    text = f"{item.title}. {item.summary}"
    required_concepts_match = bool(queries) and any(
        matches_required_candidate_terms(query, text) for query in queries
    )
    role_evidence_present = _role_support(gap, item)
    accepted = all(
        (
            provenance_qualified,
            direct_relevance,
            supporting_span_present,
            required_concepts_match,
            query_term_overlap,
            role_evidence_present,
        )
    )
    checklist = {
        "baseline_match": legacy_result.checklist_results.get("baseline_match", False),
        "claim_match": legacy_result.checklist_results.get("claim_match", False),
        "constraints_match": legacy_result.checklist_results.get("constraints_match", False),
        "direct_relevance": direct_relevance,
        "evidence_role_match": legacy_result.checklist_results.get(
            "evidence_role_match", False
        ),
        "identity_verified": relevance.identity_verified,
        "provenance_qualified": provenance_qualified,
        "query_provenance_match": origin_match,
        "query_term_overlap": query_term_overlap,
        "reproducibility_match": legacy_result.checklist_results.get(
            "reproducibility_match", False
        ),
        "required_concepts_match": required_concepts_match,
        "role_evidence_present": role_evidence_present,
        "semantic_gap_binding": accepted,
        "supporting_span_present": supporting_span_present,
    }
    limitations = list(legacy_result.limitations)
    if cross_gap_reuse:
        limitations.append("cross-gap reuse accepted only after independent semantic qualification")
    if overlap:
        limitations.append(f"query overlap terms: {', '.join(overlap[:8])}")
    return GapSupportAssessment(
        evidence_id=item.evidence_id,
        gap_id=gap.gap_id,
        support_type=(
            GapSupportType.DIRECT_SUPPORT if accepted else GapSupportType.NO_SUPPORT
        ),
        supported_claim=gap.description if accepted else None,
        supporting_span_hash=(
            relevance.supporting_spans[0].span_hash if supporting_span_present else None
        ),
        checklist_results=checklist,
        limitations=limitations,
        confidence=(0.72 if accepted and origin_match else 0.58 if accepted else 0.2),
        decision="accept" if accepted else "reject",
    )


def build_evidence_ledger(
    *,
    request: ResearchRequest,
    plan: ResearchPlan,
    evidence: EvidenceBundle,
) -> tuple[
    ResearchContract,
    list[LexicalRelevanceAssessment],
    list[RelevanceAssessment],
    list[GapSupportAssessment],
    EvidenceLedger,
]:
    """Build the canonical relevance and gap-support ledger with guarded cross-gap reuse."""

    contract = legacy.build_research_contract(request, plan)
    lexical: list[LexicalRelevanceAssessment] = []
    semantic: list[RelevanceAssessment] = []
    supports: list[GapSupportAssessment] = []
    accepted_ids: list[str] = []
    rejected_ids: list[str] = []
    entries: list[EvidenceLedgerEntry] = []
    coverage = {gap.gap_id: 0 for gap in plan.evidence_gaps}
    queries_by_gap: dict[str, list[str]] = {}
    for query in plan.search_queries:
        queries_by_gap.setdefault(query.gap_id, []).append(query.query)

    for item in evidence.items:
        lexical_assessment = legacy.assess_lexical_relevance(contract, item)
        relevance = legacy.assess_semantic_relevance(contract, item, lexical_assessment)
        lexical.append(lexical_assessment)
        semantic.append(relevance)

        direct_supports: list[GapSupportAssessment] = []
        for gap in plan.evidence_gaps:
            support = assess_gap_support(
                item,
                gap,
                relevance,
                query_texts=queries_by_gap.get(gap.gap_id, ()),
            )
            direct_supports.append(support)

        initial_accepted = any(support.decision == "accept" for support in direct_supports)
        item_supports = direct_supports
        if initial_accepted:
            item_supports = [
                (
                    support
                    if support.decision == "accept"
                    else assess_gap_support(
                        item,
                        gap,
                        relevance,
                        query_texts=queries_by_gap.get(gap.gap_id, ()),
                        allow_cross_gap_reuse=True,
                    )
                )
                for gap, support in zip(plan.evidence_gaps, direct_supports, strict=True)
            ]

        supports.extend(item_supports)
        accepted_supports = [support for support in item_supports if support.decision == "accept"]
        accepted = bool(accepted_supports)
        if accepted:
            accepted_ids.append(item.evidence_id)
            for support in accepted_supports:
                coverage[support.gap_id] = coverage.get(support.gap_id, 0) + 1
        else:
            rejected_ids.append(item.evidence_id)

        supported_claims = _dedupe(
            support.supported_claim or ""
            for support in accepted_supports
            if support.supported_claim
        )
        limitations = _dedupe(
            limitation
            for support in item_supports
            for limitation in support.limitations
        )
        rejection_reasons = (
            []
            if accepted
            else _dedupe(
                [
                    "identity verification failed"
                    if not relevance.identity_verified
                    else "",
                    *relevance.exclusion_reasons,
                    "no independently qualified gap support",
                ]
            )
        )
        entries.append(
            EvidenceLedgerEntry(
                evidence_id=item.evidence_id,
                identity_verified=relevance.identity_verified,
                relevance_scope=relevance.evidence_scope,
                gap_supports=item_supports,
                supported_claims=supported_claims,
                limitations=limitations,
                accepted=accepted,
                rejection_reasons=rejection_reasons,
            )
        )

    ledger = EvidenceLedger(
        entries=entries,
        accepted_ids=accepted_ids,
        rejected_ids=rejected_ids,
        coverage_by_gap=coverage,
    )
    return contract, lexical, semantic, supports, ledger


__all__ = ["assess_gap_support", "build_evidence_ledger"]

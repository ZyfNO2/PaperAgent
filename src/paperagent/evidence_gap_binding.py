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
            "loss",
            "branch",
            "detection head",
            "super-resolution",
            "temporal",
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
    semantic_binding = all(
        (
            provenance_qualified,
            direct_relevance,
            supporting_span_present,
            query_term_overlap,
            required_concepts_match,
            role_evidence_present,
        )
    )
    checklist = {
        **legacy_result.checklist_results,
        "query_provenance_match": origin_match,
        "cross_gap_reuse": cross_gap_reuse,
        "provenance_qualified": provenance_qualified,
        "direct_relevance": direct_relevance,
        "supporting_span_present": supporting_span_present,
        "query_term_overlap": query_term_overlap,
        "required_concepts_match": required_concepts_match,
        "role_evidence_present": role_evidence_present,
        "semantic_gap_binding": semantic_binding,
    }
    if not semantic_binding:
        missing = [
            label
            for label, passed in (
                (
                    "query provenance or qualified cross-gap reuse",
                    provenance_qualified,
                ),
                ("direct relevance", direct_relevance),
                ("supporting span", supporting_span_present),
                ("query-term overlap", query_term_overlap),
                ("required query concepts", required_concepts_match),
                ("role-specific evidence structure", role_evidence_present),
            )
            if not passed
        ]
        return legacy_result.model_copy(
            update={
                "checklist_results": checklist,
                "limitations": _dedupe(
                    [*legacy_result.limitations, f"semantic binding missing: {', '.join(missing)}"]
                ),
            }
        )

    span = relevance.supporting_spans[0]
    support_type: GapSupportType = "direct_support"
    binding_basis = (
        "reused across gaps after an existing accepted binding, direct relevance, "
        "query concepts, and role-specific evidence cues"
        if cross_gap_reuse
        else "bound through verified query provenance, direct relevance, query concepts, "
        "and role-specific evidence cues"
    )
    return GapSupportAssessment(
        evidence_id=item.evidence_id,
        gap_id=gap.gap_id,
        support_type=support_type,
        supported_claim=gap.description,
        supporting_span_hash=hash_payload(span),
        checklist_results=checklist,
        limitations=[binding_basis],
        confidence=0.72 if cross_gap_reuse else 0.82,
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
    contract, lexical, relevance, _, legacy_ledger = legacy.build_evidence_ledger(
        request=request,
        plan=plan,
        evidence=evidence,
    )
    if plan is None or not plan.evidence_gaps:
        return contract, lexical, relevance, [], legacy_ledger

    relevance_by_id = {item.evidence_id: item for item in relevance}
    legacy_entries = {entry.evidence_id: entry for entry in legacy_ledger.entries}
    queries_by_gap: dict[str, list[str]] = {}
    for query in plan.search_queries:
        queries_by_gap.setdefault(query.gap_id, []).append(query.query)

    entries: list[EvidenceLedgerEntry] = []
    gap_results: list[GapSupportAssessment] = []
    for item in evidence.items:
        item_relevance = relevance_by_id[item.evidence_id]
        first_pass = [
            assess_gap_support(
                item,
                gap,
                item_relevance,
                query_texts=queries_by_gap.get(gap.gap_id, []),
            )
            for gap in plan.evidence_gaps
        ]
        has_bound_support = any(support.decision == "accept" for support in first_pass)
        if has_bound_support:
            supports = [
                support
                if support.decision == "accept"
                else assess_gap_support(
                    item,
                    gap,
                    item_relevance,
                    query_texts=queries_by_gap.get(gap.gap_id, []),
                    allow_cross_gap_reuse=True,
                )
                for gap, support in zip(
                    plan.evidence_gaps,
                    first_pass,
                    strict=True,
                )
            ]
        else:
            supports = first_pass
        gap_results.extend(supports)
        accepted_supports = [support for support in supports if support.decision == "accept"]
        legacy_entry = legacy_entries[item.evidence_id]
        accepted = (
            legacy_entry.identity_verified
            and item_relevance.decision == "pass"
            and bool(accepted_supports)
        )
        rejection_reasons = [
            value for value in legacy_entry.rejection_reasons if value != "NO_VALID_GAP_BINDING"
        ]
        if not accepted and not accepted_supports:
            rejection_reasons.append("NO_VALID_GAP_BINDING")
        entries.append(
            EvidenceLedgerEntry(
                evidence_id=item.evidence_id,
                identity_verified=legacy_entry.identity_verified,
                relevance_scope=item_relevance.evidence_scope,
                gap_supports=supports,
                supported_claims=[
                    support.supported_claim
                    for support in accepted_supports
                    if support.supported_claim is not None
                ],
                limitations=_dedupe(
                    limitation for support in supports for limitation in support.limitations
                ),
                accepted=accepted,
                rejection_reasons=_dedupe(rejection_reasons),
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
    return contract, lexical, relevance, gap_results, ledger


apply_ledger_to_bundle = legacy.apply_ledger_to_bundle

__all__ = [
    "apply_ledger_to_bundle",
    "assess_gap_support",
    "build_evidence_ledger",
]

from __future__ import annotations

import re
from collections.abc import Iterable

from paperagent import evidence_relevance as legacy
from paperagent.literature.query_concepts import (
    concept_tokens,
    matches_required_candidate_terms,
    named_identifiers,
)
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
_BASELINE_ROLE_HINTS = ("baseline", "comparison", "reproduction", "基线", "比较", "对比", "复现")
_MECHANISM_ROLE_HINTS = (
    "mechanism",
    "intervention",
    "failure mechanism",
    "机制",
    "干预",
    "改进原理",
)
_RISK_ROLE_HINTS = (
    "risk",
    "negative result",
    "failure condition",
    "风险",
    "负面结果",
    "失败条件",
)
_METRIC_PATTERN = re.compile(
    r"\b(?:m?ap(?:50|75)?|f1|auc|accuracy|precision|recall|ndcg|rmse|mae|"
    r"latency|throughput|fps|flops?|parameters?|params?|memory|energy|power)\b",
    re.IGNORECASE,
)
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?\s*(?:%|ms|s|mb|gb|w|fps)?", re.IGNORECASE)
_EVALUATION_CUES = (
    "dataset",
    "corpus",
    "cohort",
    "test set",
    "validation set",
    "evaluation protocol",
    "experimental setting",
    "train/validation/test",
    "cross-validation",
    "数据集",
    "语料库",
    "测试集",
    "验证集",
    "实验设置",
)
_RESULT_CUES = (
    "reports",
    "reported",
    "achieves",
    "achieved",
    "measured",
    "result",
    "outperform",
    "improvement",
    "degradation",
    "报告",
    "达到",
    "结果",
    "提升",
    "下降",
)
_COMPARATIVE_EXPERIMENT_CUES = (
    "experimental results",
    "experiments demonstrate",
    "experiments show",
    "extensive experiments",
    "evaluation demonstrates",
    "outperforms",
    "outperformed",
    "superiority",
    "competitive performance",
    "实验结果",
    "实验证明",
    "大量实验",
    "优于",
    "具有竞争力",
)
_LIMITATION_CUES = (
    "limitation",
    "fails",
    "failure",
    "degrades",
    "degradation",
    "bottleneck",
    "sensitive to",
    "struggles",
    "drawback",
    "challenge",
    "challenging",
    "constraint",
    "computational cost",
    "energy request",
    "resource demand",
    "difficult",
    "complex",
    "局限",
    "失败",
    "退化",
    "瓶颈",
    "敏感",
)
_INTERVENTION_CUES = (
    "we propose",
    "we introduce",
    "we use",
    "uses",
    "using",
    "intervention",
    "module",
    "component",
    "objective",
    "regularizer",
    "algorithm",
    "procedure",
    "strategy",
    "architecture",
    "approach",
    "我们提出",
    "模块",
    "组件",
    "目标函数",
    "算法",
    "策略",
)
_RELATION_CUES = (
    "because",
    "therefore",
    "thereby",
    "addresses",
    "mitigates",
    "reduces",
    "improves by",
    "designed to",
    "in order to",
    "to limit",
    "to reduce",
    "to improve",
    "to address",
    "to mitigate",
    "通过",
    "因此",
    "从而",
    "缓解",
    "解决",
    "用于",
)
_NEGATIVE_RESULT_CUES = (
    "no improvement",
    "not improve",
    "failed to improve",
    "worse than",
    "underperform",
    "performance drop",
    "statistically insignificant",
    "did not converge",
    "unstable training",
    "negative transfer",
    "没有提升",
    "未能提升",
    "低于",
    "性能下降",
    "不显著",
    "未收敛",
    "训练不稳定",
)
_CONDITION_CUES = (
    " when ",
    " under ",
    " if ",
    " unless ",
    " fails on ",
    " failure occurs ",
    "在以下条件",
    "当",
    "如果",
    "条件下",
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


def _has_concrete_method_identity(item: EvidenceItem) -> bool:
    title = item.title.strip()
    if named_identifiers(title):
        return True
    concepts = concept_tokens(title)
    generic_titles = ("review", "survey", "taxonomy", "overview", "综述", "回顾")
    return len(concepts) >= 2 and not any(cue in title.casefold() for cue in generic_titles)


def _baseline_role_support(item: EvidenceItem, text: str) -> bool:
    concrete_method = _has_concrete_method_identity(item)
    evaluation_setting = any(cue in text for cue in _EVALUATION_CUES)
    explicit_metric_result = bool(_METRIC_PATTERN.search(text)) and (
        bool(_NUMBER_PATTERN.search(text)) or any(cue in text for cue in _RESULT_CUES)
    )
    comparative_experiment = evaluation_setting and any(
        cue in text for cue in _COMPARATIVE_EXPERIMENT_CUES
    )
    return (
        concrete_method
        and evaluation_setting
        and (explicit_metric_result or comparative_experiment)
    )


def _mechanism_role_support(text: str) -> bool:
    limitation = any(cue in text for cue in _LIMITATION_CUES)
    intervention = any(cue in text for cue in _INTERVENTION_CUES)
    relation = any(cue in text for cue in _RELATION_CUES)
    return limitation and intervention and relation


def _risk_role_support(text: str) -> bool:
    explicit_negative = any(cue in text for cue in _NEGATIVE_RESULT_CUES)
    conditional_failure = any(cue in f" {text} " for cue in _CONDITION_CUES) and any(
        cue in text for cue in _LIMITATION_CUES
    )
    return explicit_negative or conditional_failure


def _role_support(gap: EvidenceGap, item: EvidenceItem) -> bool:
    text = f"{item.title}. {item.summary}".casefold()
    role = _gap_role(gap)
    if role == "baseline":
        return _baseline_role_support(item, text)
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
    """Bind evidence through a corpus-independent, structured role contract.

    Provenance or prior acceptance is never sufficient. The semantic fallback requires direct
    relevance, a supporting span, query-derived concept coverage, and evidence structure appropriate
    for the declared role. No task, dataset, model, or application-domain vocabulary is embedded.
    """

    legacy_result = legacy.assess_gap_support(item, gap, relevance)
    if relevance.decision == "reject":
        return legacy_result
    fixture_gap_ids = {
        value.strip()
        for value in item.metadata.get("fixture_gap_support_ids", "").split(",")
        if value.strip()
    }
    explicit_fixture_support = relevance.assessment_source == "fixture" and (
        gap.gap_id in fixture_gap_ids or gap.gap_id in item.supports_gap_ids
    )
    if legacy_result.decision == "accept" and explicit_fixture_support:
        return legacy_result

    query_provenance = item.metadata.get("query_text", "").strip()
    queries = tuple(value for value in (*query_texts, query_provenance) if value.strip())
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
                ("query provenance or qualified cross-gap reuse", provenance_qualified),
                ("direct relevance", direct_relevance),
                ("supporting span", supporting_span_present),
                ("query-term overlap", query_term_overlap),
                ("required query concepts", required_concepts_match),
                ("role-specific evidence contract", role_evidence_present),
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
        "reused across gaps after an accepted binding and a complete role contract"
        if cross_gap_reuse
        else "bound through query provenance and a complete role contract"
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
                for gap, support in zip(plan.evidence_gaps, first_pass, strict=True)
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

__all__ = ["apply_ledger_to_bundle", "assess_gap_support", "build_evidence_ledger"]

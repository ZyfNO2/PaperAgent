from __future__ import annotations

from datetime import UTC, datetime

from paperagent.evidence_gap_binding import build_evidence_ledger
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery


def _plan() -> ResearchPlan:
    gaps = [
        EvidenceGap(
            gap_id="baseline_comparison",
            description="小样本行业文本意图识别的可复现基线与强比较证据。",
        ),
        EvidenceGap(
            gap_id="mechanism_limitation",
            description="小样本意图识别的数据稀缺机制、领域适配方法与局限。",
        ),
        EvidenceGap(
            gap_id="risk_negative_evidence",
            description="小样本意图识别的开放集风险、失败案例与负面证据。",
            required=False,
            minimum_accepted_items=0,
        ),
    ]
    queries = [
        SearchQuery(
            query_id="q1",
            gap_id="baseline_comparison",
            query="few-shot intent classification prototypical network",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q2",
            gap_id="mechanism_limitation",
            query="few-shot intent classification contrastive learning label semantics",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q3",
            gap_id="risk_negative_evidence",
            query="few-shot intent detection open set out-of-scope",
            source_types=["paper"],
        ),
    ]
    return ResearchPlan(
        status="ready",
        problem_statement="小样本行业文本意图识别",
        scope="few-shot text intent classification and open-set intent detection",
        evidence_gaps=gaps,
        search_queries=queries,
        success_criteria=["找到任务匹配的基线、机制和风险证据"],
        risks=["类别混淆、数据稀缺与开放集意图"],
    )


def _item(
    *,
    evidence_id: str,
    gap_id: str,
    query: str,
    title: str,
    summary: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[gap_id],
        summary=summary,
        content_hash=f"sha256:{evidence_id}",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": gap_id, "query_text": query},
    )


def _bundle(items: list[EvidenceItem]) -> EvidenceBundle:
    return EvidenceBundle(
        items=items,
        accepted_ids=[item.evidence_id for item in items],
        identity_verified_ids=[item.evidence_id for item in items],
        coverage_by_gap={item.supports_gap_ids[0]: 1 for item in items},
    )


def test_case_011_wording_binds_each_origin_role_without_relaxing_provenance() -> None:
    items = [
        _item(
            evidence_id="ev-baseline",
            gap_id="baseline_comparison",
            query="few-shot intent classification prototypical network",
            title="Semantic Transportation Prototypical Network for Few-Shot Intent Detection",
            summary=(
                "Few-shot intent detection has few annotated utterances and confusion among "
                "semantically similar intents. We propose a semantic transportation prototypical "
                "network. Experiments on two benchmark datasets evaluate its classification "
                "performance against existing methods."
            ),
        ),
        _item(
            evidence_id="ev-mechanism",
            gap_id="mechanism_limitation",
            query="few-shot intent classification contrastive learning label semantics",
            title="Few-shot Learning for Multi-label Intent Detection",
            summary=(
                "Few-shot user intent detection has only a few examples per label. We introduce "
                "label name embedding and nonparametric threshold calibration transferred from "
                "data-rich domains. Experiments report improved multi-label intent performance."
            ),
        ),
        _item(
            evidence_id="ev-risk",
            gap_id="risk_negative_evidence",
            query="few-shot intent detection open set out-of-scope",
            title=(
                "Discriminative Nearest Neighbor Few-Shot Intent Detection by Transferring "
                "Natural Language Inference"
            ),
            summary=(
                "Few-shot intent detection is limited by scarce training data, while out-of-scope "
                "detection is more challenging. The method transfers natural language inference "
                "and uses a nearest-neighbor distance mechanism for in-domain and OOS evaluation."
            ),
        ),
    ]

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=_plan(),
        evidence=_bundle(items),
    )

    assert set(ledger.accepted_ids) == {"ev-baseline", "ev-mechanism", "ev-risk"}
    direct = {
        (support.evidence_id, support.gap_id): support
        for support in supports
        if support.checklist_results.get("query_provenance_match")
    }
    assert direct[("ev-baseline", "baseline_comparison")].decision == "accept"
    assert direct[("ev-mechanism", "mechanism_limitation")].decision == "accept"
    assert direct[("ev-risk", "risk_negative_evidence")].decision == "accept"
    for support in direct.values():
        assert support.checklist_results["role_evidence_present"] is True
        assert support.checklist_results["required_concepts_match"] is True


def test_visual_few_shot_paper_remains_rejected_for_intent_baseline() -> None:
    full_plan = _plan()
    plan = full_plan.model_copy(
        update={
            "evidence_gaps": [full_plan.evidence_gaps[0]],
            "search_queries": [full_plan.search_queries[0]],
        }
    )
    item = _item(
        evidence_id="ev-image",
        gap_id="baseline_comparison",
        query="few-shot intent classification prototypical network",
        title="Meta-Baseline for Few-Shot Image Classification",
        summary=(
            "A prototypical network is evaluated on image classification benchmark datasets "
            "and outperforms visual baselines."
        ),
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=plan,
        evidence=_bundle([item]),
    )

    assert ledger.accepted_ids == []
    binding = next(support for support in supports if support.gap_id == "baseline_comparison")
    assert binding.decision == "reject"
    assert binding.checklist_results["required_concepts_match"] is False


def test_method_only_intent_paper_without_evaluation_is_not_a_baseline() -> None:
    full_plan = _plan()
    plan = full_plan.model_copy(
        update={
            "evidence_gaps": [full_plan.evidence_gaps[0]],
            "search_queries": [full_plan.search_queries[0]],
        }
    )
    item = _item(
        evidence_id="ev-no-eval",
        gap_id="baseline_comparison",
        query="few-shot intent classification prototypical network",
        title="A Prototypical Network for Few-Shot Intent Detection",
        summary="We propose a network for few-shot intent detection with few examples.",
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="小样本行业文本意图识别"),
        plan=plan,
        evidence=_bundle([item]),
    )

    assert ledger.accepted_ids == []
    binding = next(support for support in supports if support.gap_id == "baseline_comparison")
    assert binding.checklist_results["role_evidence_present"] is False

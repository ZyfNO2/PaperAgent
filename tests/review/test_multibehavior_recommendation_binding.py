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
            description="多行为推荐的可复现基线与强比较证据。",
        ),
        EvidenceGap(
            gap_id="failure_mechanism",
            description="辅助行为噪声、行为迁移机制与局限。",
        ),
        EvidenceGap(
            gap_id="optional_risk",
            description="冷启动、长尾、稀疏和负迁移风险。",
            required=False,
            minimum_accepted_items=0,
        ),
    ]
    queries = [
        SearchQuery(
            query_id="q1",
            gap_id="baseline_comparison",
            query="multi-behavior recommendation graph neural network",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q2",
            gap_id="failure_mechanism",
            query="multi-behavior recommendation gated auxiliary behavior transfer",
            source_types=["paper"],
        ),
        SearchQuery(
            query_id="q3",
            gap_id="optional_risk",
            query="multi-behavior recommendation data sparsity cold-start long-tail",
            source_types=["paper"],
        ),
    ]
    return ResearchPlan(
        status="ready",
        problem_statement="面向电商场景的多行为推荐系统",
        scope="e-commerce multi-behavior recommendation for purchase ranking",
        evidence_gaps=gaps,
        search_queries=queries,
        success_criteria=["找到任务匹配的基线、机制和风险证据"],
        risks=["辅助行为噪声、冷启动、长尾和未来交互泄漏"],
    )


def _item(*, evidence_id: str, gap_id: str, query: str, title: str, summary: str) -> EvidenceItem:
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


def test_case_015_evidence_binds_to_baseline_mechanism_and_risk_roles() -> None:
    items = [
        _item(
            evidence_id="ev-baseline",
            gap_id="baseline_comparison",
            query="multi-behavior recommendation graph neural network",
            title="Multi-Behavior Recommendation with Graph Convolutional Networks",
            summary=(
                "We propose a graph neural network for multi-behavior recommendation "
                "over click, cart, and purchase interactions. Experiments on two "
                "e-commerce datasets report Recall and NDCG and outperform baselines."
            ),
        ),
        _item(
            evidence_id="ev-mechanism",
            gap_id="failure_mechanism",
            query="multi-behavior recommendation gated auxiliary behavior transfer",
            title="Gated Behavior Transfer for Multi-Behavior Recommendation",
            summary=(
                "Auxiliary behaviors in a multi-behavior recommender are sparse, noisy, "
                "and heterogeneous. We introduce gated behavior-specific transfer and "
                "graph message passing to protect the target purchase behavior."
            ),
        ),
        _item(
            evidence_id="ev-risk",
            gap_id="optional_risk",
            query="multi-behavior recommendation data sparsity cold-start long-tail",
            title="Robust Multi-Behavior Recommendation under Sparse Feedback",
            summary=(
                "Multi-behavior recommendation remains vulnerable to cold-start, "
                "long-tail sparsity, behavior imbalance, and negative transfer from "
                "noisy auxiliary behavior."
            ),
        ),
    ]
    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="面向电商场景的多行为推荐系统"),
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
    assert direct[("ev-mechanism", "failure_mechanism")].decision == "accept"
    assert direct[("ev-risk", "optional_risk")].decision == "accept"
    for support in direct.values():
        assert support.checklist_results["role_evidence_present"] is True
        assert support.checklist_results["required_concepts_match"] is True


def test_method_only_multibehavior_paper_without_evaluation_is_not_baseline() -> None:
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
        query="multi-behavior recommendation graph neural network",
        title="A Graph Network for Multi-Behavior Recommendation",
        summary="We propose a graph network for multi-behavior recommendation.",
    )
    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="面向电商场景的多行为推荐系统"),
        plan=plan,
        evidence=_bundle([item]),
    )
    assert ledger.accepted_ids == []
    binding = next(support for support in supports if support.gap_id == "baseline_comparison")
    assert binding.checklist_results["role_evidence_present"] is False

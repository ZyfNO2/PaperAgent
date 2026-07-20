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

_GAP = EvidenceGap(
    gap_id="failure_mechanism_temporal_action",
    description=("摄像头动作识别中相似姿态、时间顺序、实时计算约束及可独立验证的时序干预证据。"),
)
_QUERY = (
    "camera video pose human action recognition temporal order self-attention real-time mechanism"
)


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="基于摄像头的人体动作识别",
        scope="单人 RGB 或姿态序列动作分类",
        evidence_gaps=[_GAP],
        search_queries=[
            SearchQuery(
                query_id="q-mechanism",
                gap_id=_GAP.gap_id,
                query=_QUERY,
                source_types=["paper"],
            )
        ],
        success_criteria=["找到视觉动作识别的直接时序机制证据"],
        risks=["动作质量评估标签尚未定义"],
    )


def _bundle(*, title: str, summary: str) -> EvidenceBundle:
    item = EvidenceItem(
        evidence_id="ev-action",
        source_type="paper",
        title=title,
        locator="arxiv:2107.00606",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[_GAP.gap_id],
        summary=summary,
        content_hash="sha256:action-mechanism-test",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": _GAP.gap_id},
    )
    return EvidenceBundle(
        items=[item],
        accepted_ids=[item.evidence_id],
        identity_verified_ids=[item.evidence_id],
        coverage_by_gap={_GAP.gap_id: 1},
    )


def test_action_transformer_binds_to_temporal_efficiency_mechanism() -> None:
    summary = (
        "The work introduces Action Transformer, a fully self-attentional architecture for "
        "human action recognition. To limit computational and energy requests, the approach "
        "uses 2D pose representations over small temporal windows and provides a low-latency "
        "solution for accurate real-time performance."
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="我想做一个基于摄像头的人体动作识别系统"),
        plan=_plan(),
        evidence=_bundle(
            title=(
                "Action Transformer: A Self-Attention Model for Short-Time "
                "Pose-Based Human Action Recognition"
            ),
            summary=summary,
        ),
    )

    assert ledger.accepted_ids == ["ev-action"]
    assert ledger.coverage_by_gap == {_GAP.gap_id: 1}
    support = next(item for item in supports if item.gap_id == _GAP.gap_id)
    assert support.decision == "accept"
    assert support.checklist_results["role_evidence_present"] is True
    assert support.checklist_results["semantic_gap_binding"] is True


def test_multiview_dataset_without_method_intervention_does_not_bind() -> None:
    summary = (
        "Human action recognition is challenging from multiple viewpoints. We present a "
        "multi-viewpoint outdoor video dataset with twenty action classes collected from "
        "ground and aerial cameras for future benchmark research."
    )

    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="我想做一个基于摄像头的人体动作识别系统"),
        plan=_plan(),
        evidence=_bundle(
            title="A Multi-viewpoint Outdoor Dataset for Human Action Recognition",
            summary=summary,
        ),
    )

    assert ledger.accepted_ids == []
    support = next(item for item in supports if item.gap_id == _GAP.gap_id)
    assert support.decision == "reject"
    assert support.checklist_results["role_evidence_present"] is False

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

_BASELINE_GAP = EvidenceGap(
    gap_id="baseline_comparison",
    description="寻找可复现的轻量化无人机小目标检测基线、数据集、指标和强比较证据。",
)
_MECHANISM_GAP = EvidenceGap(
    gap_id="failure_mechanism_limitations",
    description="分析轻量化无人机小目标检测的失败机制、局限与可独立验证的并行方法。",
)
_BASELINE_QUERY = (
    "lightweight drone small object detection baseline reproducible method dataset "
    "metrics efficiency real-time"
)
_MECHANISM_QUERY = (
    "lightweight drone small object detection failure mechanism limitation parallel method "
    "feature enhancement data augmentation post-processing"
)
_DRONE_DETR_TITLE = "Drone-DETR: Efficient Small Object Detection for Remote Sensing Image"
_DRONE_DETR_SUMMARY = (
    "Performing low-latency, high-precision object detection on unmanned aerial vehicles "
    "equipped with vision sensors is challenging for numerous small objects. We introduce "
    "Drone-DETR with a lightweight architecture and feature fusion for complex backgrounds "
    "and occlusion. Experimental results on the VisDrone2019 dataset achieve an mAP50 of "
    "53.9% with 28.7 million parameters, an 8.1% enhancement over RT-DETR-R18."
)


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="轻量化无人机小目标检测方法设计",
        scope="无人机航拍图像中的轻量化视觉小目标检测",
        evidence_gaps=[_BASELINE_GAP],
        search_queries=[
            SearchQuery(
                query_id="q_baseline",
                gap_id=_BASELINE_GAP.gap_id,
                query=_BASELINE_QUERY,
                source_types=["paper"],
            )
        ],
        success_criteria=["找到可复现基线与强比较证据"],
        risks=["部署设备和数据集尚未确定"],
    )


def _multi_gap_plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="轻量化无人机小目标检测方法设计",
        scope="无人机航拍图像中的轻量化视觉小目标检测",
        evidence_gaps=[_BASELINE_GAP, _MECHANISM_GAP],
        search_queries=[
            SearchQuery(
                query_id="q_baseline",
                gap_id=_BASELINE_GAP.gap_id,
                query=_BASELINE_QUERY,
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q_mechanism",
                gap_id=_MECHANISM_GAP.gap_id,
                query=_MECHANISM_QUERY,
                source_types=["paper"],
            ),
        ],
        success_criteria=["找到可复现基线与机制证据"],
        risks=["部署设备和数据集尚未确定"],
    )


def _bundle(
    *,
    title: str = _DRONE_DETR_TITLE,
    summary: str,
    candidate_gap_id: str,
) -> EvidenceBundle:
    item = EvidenceItem(
        evidence_id="ev-paper",
        source_type="paper",
        title=title,
        locator="doi:10.3390/s24175496",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[candidate_gap_id],
        summary=summary,
        content_hash="sha256:test",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": candidate_gap_id},
    )
    return EvidenceBundle(
        items=[item],
        accepted_ids=[item.evidence_id],
        identity_verified_ids=[item.evidence_id],
        coverage_by_gap={candidate_gap_id: 1},
    )


def test_verified_drone_detr_binds_to_chinese_baseline_gap() -> None:
    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="轻量化无人机小目标检测"),
        plan=_plan(),
        evidence=_bundle(
            summary=_DRONE_DETR_SUMMARY,
            candidate_gap_id="baseline_comparison",
        ),
    )

    assert ledger.accepted_ids == ["ev-paper"]
    assert ledger.coverage_by_gap == {"baseline_comparison": 1}
    binding = next(item for item in support if item.gap_id == "baseline_comparison")
    assert binding.decision == "accept"
    assert binding.checklist_results["semantic_gap_binding"] is True
    assert binding.checklist_results["role_evidence_present"] is True


def test_verified_bound_paper_can_cover_second_gap_only_after_independent_checks() -> None:
    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="轻量化无人机小目标检测"),
        plan=_multi_gap_plan(),
        evidence=_bundle(
            summary=_DRONE_DETR_SUMMARY,
            candidate_gap_id="baseline_comparison",
        ),
    )

    assert ledger.accepted_ids == ["ev-paper"]
    assert ledger.coverage_by_gap == {
        "baseline_comparison": 1,
        "failure_mechanism_limitations": 1,
    }
    mechanism = next(
        item for item in support if item.gap_id == "failure_mechanism_limitations"
    )
    assert mechanism.decision == "accept"
    assert mechanism.confidence == 0.72
    assert mechanism.checklist_results["query_provenance_match"] is False
    assert mechanism.checklist_results["cross_gap_reuse"] is True
    assert mechanism.checklist_results["required_concepts_match"] is True
    assert mechanism.checklist_results["role_evidence_present"] is True


def test_query_provenance_alone_does_not_accept_rf_uav_paper() -> None:
    rf_title = "Detection and Classification of UAVs Using RF Fingerprints"
    rf_summary = (
        "A radio-frequency fingerprint dataset is used for detection and classification of "
        "UAV controller signals. The classifier reports accuracy under channel interference."
    )

    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="轻量化无人机小目标检测"),
        plan=_plan(),
        evidence=_bundle(
            title=rf_title,
            summary=rf_summary,
            candidate_gap_id="baseline_comparison",
        ),
    )

    assert ledger.accepted_ids == []
    binding = next(item for item in support if item.gap_id == "baseline_comparison")
    assert binding.decision == "reject"
    assert binding.checklist_results["query_provenance_match"] is True
    assert binding.checklist_results["required_concepts_match"] is False


def test_relevant_paper_does_not_bind_without_any_initial_gap_provenance() -> None:
    _, _, _, support, ledger = build_evidence_ledger(
        request=ResearchRequest(question="轻量化无人机小目标检测"),
        plan=_plan(),
        evidence=_bundle(summary=_DRONE_DETR_SUMMARY, candidate_gap_id="different_gap"),
    )

    assert ledger.accepted_ids == []
    binding = next(item for item in support if item.gap_id == "baseline_comparison")
    assert binding.decision == "reject"
    assert binding.checklist_results["query_provenance_match"] is False
    assert binding.checklist_results["cross_gap_reuse"] is False

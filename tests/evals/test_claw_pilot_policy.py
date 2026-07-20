from __future__ import annotations

from typing import cast

from paperagent.claw_pilot_policy import infer_benchmark_pilot_override
from paperagent.schemas import EvidenceGap, ResearchPlan, ResearchRequest, SearchQuery
from paperagent.state import PaperAgentState


def _plan(*, clarification: str, risks: list[str]) -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="Design a bounded research method.",
        scope="Use public evidence before implementation.",
        evidence_gaps=[EvidenceGap(gap_id="baseline", description="baseline evidence")],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id="baseline",
                query="reproducible baseline evidence",
                source_types=["paper"],
            )
        ],
        success_criteria=["Produce a falsifiable plan."],
        risks=risks,
        clarification_question=clarification,
    )


def test_unspecified_medical_target_defers_pilot() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="我上传了 U-Net 论文, 想做医学图像分割, 但还没有确定具体器官和数据集",
                user_material_refs=[
                    "U-Net: Convolutional Networks for Biomedical Image Segmentation "
                    "[declared role: baseline_candidate]"
                ],
            ),
            "plan": _plan(
                clarification="请确认您希望优先研究哪个具体器官或组织类型?",
                risks=["未确定具体器官与数据集, 无法设计可执行的实验计划"],
            ),
        },
    )

    assert infer_benchmark_pilot_override(state) is False


def test_unidentified_supplied_method_defers_pilot() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="Combine LightGCN with a supplied contrastive recommender.",
                user_material_refs=[
                    "LightGCN: Simplifying and Powering Graph Convolution Network for "
                    "Recommendation [declared role: baseline_candidate]",
                    "user-supplied contrastive recommendation paper "
                    "[declared role: parallel_method_candidate]",
                ],
            ),
            "plan": _plan(
                clarification="Which evaluation task and dataset should be used?",
                risks=["The supplied contrastive mechanism is not identified."],
            ),
        },
    )

    assert infer_benchmark_pilot_override(state) is False


def test_business_priority_unknown_keeps_existing_pilot_heuristic() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="面向电商场景的多行为推荐系统"),
            "plan": _plan(
                clarification="请确认转化率, 留存或多样性哪个业务目标优先?",
                risks=["业务目标与延迟约束尚未确定."],
            ),
        },
    )

    assert infer_benchmark_pilot_override(state) is None


def test_concrete_supplied_methods_keep_existing_pilot_heuristic() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="Combine YOLOX and TinyDet for UAV small-object detection.",
                user_material_refs=[
                    "YOLOX: Exceeding YOLO Series in 2021 [declared role: baseline_candidate]",
                    "TinyDet: Accurate Small Object Detection in Lightweight Generic Detectors "
                    "[declared role: parallel_method_candidate]",
                ],
            ),
            "plan": _plan(
                clarification="Should accuracy or inference speed be prioritized?",
                risks=["The accuracy-latency priority remains unresolved."],
            ),
        },
    )

    assert infer_benchmark_pilot_override(state) is None


def test_clarification_answer_releases_foundational_blocker() -> None:
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="Medical image segmentation",
                clarification_answer="Use liver CT segmentation on LiTS.",
            ),
            "plan": _plan(
                clarification="Which specific organ should be studied?",
                risks=["A target organ is required before an executable experiment."],
            ),
        },
    )

    assert infer_benchmark_pilot_override(state) is None

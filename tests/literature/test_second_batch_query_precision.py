from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query

_MEDICAL_CORE = "multimodal medical imaging disease classification feature fusion"


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Nighttime pedestrian detection under low-light conditions uses foreground and "
            "background contrast attention.",
        ),
        (
            "camera video pose human action recognition temporal robustness",
            "A pose-based human action recognition model captures temporal order in video.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A lightweight hand gesture recognition system runs in real time on edge devices.",
        ),
        (
            _MEDICAL_CORE,
            "A multimodal medical imaging classifier fuses MRI and clinical features for "
            "multi-class disease classification.",
        ),
    ],
)
def test_second_batch_guards_accept_task_matched_candidates(
    query: str,
    candidate: str,
) -> None:
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Low-light image enhancement improves naturalness through degradation learning.",
        ),
        (
            "camera video pose human action recognition temporal robustness",
            "Comparison of feature learning methods for human activity recognition using "
            "wearable sensors.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "Korean Sign Language Recognition Using Transformer-Based Deep Neural Network.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A Metaverse taxonomy reviews mobile access, virtual currency, and social content.",
        ),
        (
            _MEDICAL_CORE,
            "The BRATS benchmark evaluates multimodal brain tumor image segmentation.",
        ),
        (
            _MEDICAL_CORE,
            "A survey reviews attention mechanisms for generic computer vision tasks.",
        ),
        (
            _MEDICAL_CORE,
            "Liver Segmentation from Multimodal Images uses HED and Mask R-CNN for automatic "
            "liver segmentation in computer-aided diagnosis.",
        ),
    ],
)
def test_second_batch_guards_reject_cross_task_false_positives(
    query: str,
    candidate: str,
) -> None:
    assert matches_required_candidate_terms(query, candidate) is False


def test_diagnosis_only_query_can_use_diagnostic_evidence_without_classification() -> None:
    query = "multimodal medical imaging diagnosis feature fusion"
    candidate = (
        "A multimodal medical imaging diagnostic system fuses MRI and electronic health records."
    )

    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "gap_id"),
    [
        (
            "multimodal medical image fusion classification baseline comparison benchmark dataset",
            "baseline_comparison",
        ),
        (
            "multimodal medical image fusion classification mechanism limitation "
            "failure mode survey",
            "mechanism_limitation_parallel",
        ),
        (
            "multimodal medical imaging disease classification feature fusion baseline "
            "traditional machine learning deep review reproducible",
            "baseline_methods",
        ),
        (
            "medical imaging disease classification alternatives single-modal ensemble learning",
            "parallel_methods",
        ),
    ],
)
def test_multimodal_medical_queries_converge_to_one_stable_core(
    query: str,
    gap_id: str,
) -> None:
    result = refine_search_query(
        query,
        gap_id=gap_id,
        gap_description="multimodal medical classification evidence",
        research_context="多模态医学影像融合分类",
    )

    assert result.changed is True
    assert result.query == _MEDICAL_CORE
    assert result.reason is not None
    assert "stable task query" in result.reason


def test_camera_context_is_restored_to_action_queries() -> None:
    result = refine_search_query(
        "human action recognition baseline reproducible efficiency",
        gap_id="baseline_repro",
        gap_description="reproducible action recognition baseline",
        research_context="我想做一个基于摄像头的人体动作识别系统",
    )

    assert result.changed is True
    assert result.query.startswith("camera video pose ")
    assert result.reason is not None
    assert "camera modality" in result.reason


@pytest.mark.asyncio
async def test_prepare_search_uses_request_context_for_camera_queries() -> None:
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.retrieval.prepare_search import prepare_search_node
    from paperagent.runtime import RuntimeServices
    from paperagent.schemas import (
        EvidenceGap,
        ResearchPlan,
        ResearchRequest,
        RunBudgets,
        RunContext,
        SearchQuery,
    )
    from paperagent.testing import FixedClock, SequenceIdFactory

    now = datetime(2026, 7, 20, tzinfo=UTC)
    services = RuntimeServices(
        FakeLLMProvider(fixtures={}),
        FakeSearchProvider(fixtures={}),
        FixedClock(now),
        SequenceIdFactory("test"),
        InMemoryStateStore(),
    )
    gap = EvidenceGap(gap_id="baseline_repro", description="camera action baseline")
    plan = ResearchPlan(
        status="ready",
        problem_statement="人体动作识别系统",
        scope="单人动作识别",
        evidence_gaps=[gap],
        search_queries=[
            SearchQuery(
                query_id="q1",
                gap_id=gap.gap_id,
                query="human action recognition baseline reproducible efficiency",
                source_types=["paper"],
            )
        ],
        success_criteria=["find a visual action baseline"],
        risks=["camera setting unresolved"],
    )
    state = {
        "request": ResearchRequest(question="我想做一个基于摄像头的人体动作识别系统"),
        "run": RunContext(
            run_id="run-1",
            thread_id="thread-1",
            created_at=now,
            model_profile="fake",
            network_policy="offline",
            budgets=RunBudgets(max_queries_per_round=3),
        ),
        "plan": plan,
    }

    patch = await prepare_search_node(state, {"configurable": {"services": services}})
    prepared = patch["retrieval"].prepared_queries

    assert len(prepared) == 1
    assert prepared[0].query.startswith("camera video pose ")
    assert prepared[0].original_query == plan.search_queries[0].query

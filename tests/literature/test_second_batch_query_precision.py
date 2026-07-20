from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.literature.query_refinement import refine_search_query

_MEDICAL_QUERY = "multimodal medical image classification feature fusion"


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Nighttime pedestrian detection under low-light conditions.",
        ),
        (
            "camera video pose human action recognition temporal robustness",
            "A pose-based human action recognition model for video.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A lightweight hand gesture recognition system for edge devices.",
        ),
        (
            _MEDICAL_QUERY,
            "A multimodal medical imaging classifier for multi-class disease classification.",
        ),
    ],
)
def test_second_batch_guards_accept_task_matched_candidates(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate) is True


@pytest.mark.parametrize(
    ("query", "candidate"),
    [
        (
            "low-light pedestrian detection accuracy speed nighttime",
            "Low-light image enhancement improves naturalness.",
        ),
        (
            "camera video pose human action recognition temporal robustness",
            "Human activity recognition using wearable sensors.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "Korean Sign Language Recognition Using a Transformer.",
        ),
        (
            "lightweight gesture recognition mobile devices",
            "A Metaverse taxonomy reviews virtual currency.",
        ),
        (
            _MEDICAL_QUERY,
            "Multimodal brain tumor image segmentation on BRATS.",
        ),
        (
            _MEDICAL_QUERY,
            "Liver segmentation from multimodal images for diagnosis.",
        ),
    ],
)
def test_second_batch_guards_reject_cross_task_false_positives(query: str, candidate: str) -> None:
    assert matches_required_candidate_terms(query, candidate) is False


def test_diagnosis_query_can_use_diagnostic_evidence() -> None:
    assert matches_required_candidate_terms(
        "multimodal medical imaging diagnosis feature fusion",
        "A multimodal medical imaging diagnostic system fuses MRI and clinical records.",
    )


@pytest.mark.parametrize(
    ("gap_id", "description", "expected"),
    [
        (
            "baseline_methods",
            "reproducible baseline comparison",
            "multimodal medical image classification MultiFusionNet",
        ),
        (
            "failure_mechanism",
            "failure mechanism and limitations",
            "multimodal medical image classification incomplete data limitations",
        ),
        (
            "parallel_methods",
            "parallel alternatives",
            "multimodal medical image classification fusion techniques",
        ),
    ],
)
def test_medical_queries_preserve_evidence_roles(
    gap_id: str, description: str, expected: str
) -> None:
    result = refine_search_query(
        "multimodal medical image fusion classification evidence",
        gap_id=gap_id,
        gap_description=description,
        research_context="多模态医学影像融合分类",
    )
    assert result.query == expected
    assert result.reason is not None
    assert "role-specific task query" in result.reason


def test_parallel_medical_role_wins_over_limitation_words() -> None:
    result = refine_search_query(
        "multimodal medical image classification alternatives and limitations",
        gap_id="parallel_methods_evidence",
        gap_description="parallel methods, alternatives, and known limitations",
        research_context="多模态医学影像融合分类",
    )
    assert result.query == "multimodal medical image classification fusion techniques"


def test_medical_primary_roles_do_not_collapse_to_one_query() -> None:
    queries = {
        refine_search_query(
            "multimodal medical image fusion classification evidence",
            gap_id=gap_id,
            gap_description=description,
            research_context="多模态医学影像融合分类",
        ).query
        for gap_id, description in (
            ("baseline_methods", "reproducible baseline comparison"),
            ("failure_mechanism", "failure mechanism and limitations"),
            ("parallel_methods", "parallel alternatives"),
        )
    }
    assert len(queries) == 3


def test_camera_context_is_restored_to_action_queries() -> None:
    result = refine_search_query(
        "human action recognition baseline reproducible efficiency",
        gap_id="baseline_repro",
        gap_description="reproducible action recognition baseline",
        research_context="我想做一个基于摄像头的人体动作识别系统",
    )
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

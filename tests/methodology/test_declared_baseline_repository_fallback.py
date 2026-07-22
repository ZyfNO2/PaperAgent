from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from paperagent.method_design_draft import MethodDesignDraft, build_method_proposal
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery
from paperagent.state import PaperAgentState


def test_declared_baseline_miss_uses_repository_backed_direct_paper() -> None:
    baseline_gap = EvidenceGap(
        gap_id="baseline_comparison",
        description="accepted baseline evidence",
    )
    mechanism_gap = EvidenceGap(
        gap_id="failure_mechanism",
        description="accepted module evidence",
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="industrial time-series anomaly detection",
        scope="unsupervised industrial anomaly detection with bounded compute",
        evidence_gaps=[baseline_gap, mechanism_gap],
        search_queries=[
            SearchQuery(
                query_id="q-baseline",
                gap_id=baseline_gap.gap_id,
                query="industrial anomaly detection baseline repository",
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q-mechanism",
                gap_id=mechanism_gap.gap_id,
                query="industrial anomaly detection reconstruction mechanism",
                source_types=["paper"],
            ),
        ],
        success_criteria=["bind a reproducible baseline before the pilot"],
        risks=["the exact dataset split remains unresolved"],
        clarification_question="Which industrial dataset should be frozen for the pilot?",
    )
    baseline_paper_id = "ev-industrial-autoencoder"
    baseline_paper = EvidenceItem(
        evidence_id=baseline_paper_id,
        source_type="paper",
        title="Deep Autoencoder Monitoring for Industrial Anomaly Detection",
        locator="doi:10.1000/industrial-autoencoder",
        retrieved_at=datetime(2026, 7, 22, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[baseline_gap.gap_id],
        summary=(
            "A directly retrieved industrial anomaly-detection paper with an author-linked "
            "implementation repository."
        ),
        content_hash="sha256:industrial-autoencoder",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/industrial-autoencoder",
            "relation": "direct_query",
            "rank_score": "0.91",
            "license": "CC BY 4.0",
        },
    )
    repository_id = "repo-industrial-autoencoder"
    repository = EvidenceItem(
        evidence_id=repository_id,
        source_type="repository",
        title="Official industrial autoencoder implementation",
        locator="https://github.com/example/industrial-autoencoder",
        retrieved_at=datetime(2026, 7, 22, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[baseline_gap.gap_id],
        summary="Author-linked implementation for the verified direct paper.",
        content_hash="sha256:repo-industrial-autoencoder",
        provider="literature_retrieval",
        metadata={
            "relation": "author_linked_from_verified_paper",
            "parent_paper_id": baseline_paper_id.removeprefix("ev-"),
            "license": "Apache-2.0",
        },
    )
    module_paper_id = "ev-industrial-feature-module"
    module_paper = EvidenceItem(
        evidence_id=module_paper_id,
        source_type="paper",
        title="Temporal Feature Fusion for Industrial Monitoring",
        locator="doi:10.1000/industrial-feature-fusion",
        retrieved_at=datetime(2026, 7, 22, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[mechanism_gap.gap_id],
        summary="A directly retrieved feature-fusion module paper for industrial monitoring.",
        content_hash="sha256:industrial-feature-fusion",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/industrial-feature-fusion",
            "relation": "direct_query",
            "rank_score": "0.95",
            "license": "CC BY 4.0",
        },
    )
    state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(
                question="工业时间序列异常检测",
                user_material_refs=["USAD [declared role:baseline]"],
            ),
            "plan": plan,
            "evidence": EvidenceBundle(
                items=[baseline_paper, repository, module_paper],
                accepted_ids=[baseline_paper_id, repository_id, module_paper_id],
                identity_verified_ids=[baseline_paper_id, repository_id, module_paper_id],
                coverage_by_gap={baseline_gap.gap_id: 2, mechanism_gap.gap_id: 1},
            ),
        },
    )
    draft = MethodDesignDraft(
        problem_method_insight="Industrial anomalies can be missed by a fixed reconstruction path.",
        proposed_method_summary="Add one switchable temporal feature-fusion module.",
        condition="industrial signals contain multiscale temporal deviations",
        limitation="a fixed reconstruction path can suppress short anomaly signatures",
        mechanism="temporal feature fusion preserves short and long deviation evidence",
        intervention="insert one temporal feature-fusion module before reconstruction",
        predicted_metric_change="increase anomaly F1 under the same threshold protocol",
        guardrail="latency and memory remain within the frozen baseline budget",
        module_name="temporal_feature_fusion",
        module_original_role="multiscale temporal representation fusion",
        module_proposed_role="preserve anomaly evidence before reconstruction",
        input_semantics="encoded industrial time-series features",
        output_semantics="fused features for the reconstruction head",
        predicted_effect="improve anomaly F1 without increasing false positives",
        failure_mode="fusion may smooth short anomalies instead of preserving them",
        compute_cost="one bounded temporal fusion path",
        primary_metric="F1",
        resource_measures=["latency", "memory"],
        stopping_criteria="stop if the F1 gain disappears under matched seeds and thresholds",
    )

    proposal = build_method_proposal(state, draft)

    assert proposal.methodology_plan.baseline.name == baseline_paper.title
    assert proposal.methodology_plan.baseline.source_evidence_id == baseline_paper_id
    assert proposal.methodology_plan.modules[0].evidence_id == module_paper_id

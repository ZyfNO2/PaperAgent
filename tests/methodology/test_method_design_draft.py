from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from paperagent.academic_methodology import AuditVerdict, ExperimentArmType, audit_method_plan
from paperagent.method_design_draft import MethodDesignDraft, build_method_proposal
from paperagent.method_evidence import bind_method_evidence
from paperagent.schemas import (
    Claim,
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    EvidenceSynthesis,
    GapAssessment,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery
from paperagent.schemas.relevance import (
    EvidenceLedger,
    EvidenceLedgerEntry,
    GapSupportAssessment,
)
from paperagent.state import PaperAgentState

_EVIDENCE_ID = "ev-drone-detr"
_BASELINE_ID = "ev-rt-detr-baseline"
_SUMMARY = (
    "Drone-DETR is evaluated on the VisDrone2019 dataset for small object detection in UAV "
    "imagery. It uses lightweight feature fusion and reports mAP50 gains over RT-DETR-R18 "
    "while discussing complex backgrounds and occlusion."
)


def _support(
    gap_id: str,
    claim: str,
    *,
    evidence_id: str = _EVIDENCE_ID,
) -> GapSupportAssessment:
    return GapSupportAssessment(
        evidence_id=evidence_id,
        gap_id=gap_id,
        support_type="direct_support",
        supported_claim=claim,
        supporting_span_hash=f"sha256:{gap_id}",
        checklist_results={"semantic_gap_binding": True},
        limitations=("pilot reproduction remains required",),
        confidence=0.82,
        decision="accept",
    )


def _state() -> PaperAgentState:
    baseline_gap = EvidenceGap(
        gap_id="baseline_comparison",
        description="baseline and strong comparison evidence",
    )
    mechanism_gap = EvidenceGap(
        gap_id="failure_mechanism",
        description="failure mechanism and parallel method evidence",
    )
    plan = ResearchPlan(
        status="ready",
        problem_statement="lightweight UAV small object detection",
        scope="aerial visual detection under unresolved deployment constraints",
        evidence_gaps=[baseline_gap, mechanism_gap],
        search_queries=[
            SearchQuery(
                query_id="q-baseline",
                gap_id=baseline_gap.gap_id,
                query="lightweight UAV small object detection baseline VisDrone metrics",
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q-mechanism",
                gap_id=mechanism_gap.gap_id,
                query="UAV small object detection limitation feature fusion occlusion",
                source_types=["paper"],
            ),
        ],
        success_criteria=["bounded pilot with matched comparisons"],
        risks=["deployment device is unresolved", "dataset split is unresolved"],
        clarification_question=(
            "Which dataset, deployment device, and accuracy-latency priority should constrain "
            "the pilot?"
        ),
    )
    evidence_item = EvidenceItem(
        evidence_id=_EVIDENCE_ID,
        source_type="paper",
        title="Drone-DETR: Efficient Small Object Detection for Remote Sensing Image",
        locator="doi:10.3390/s24175496",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[baseline_gap.gap_id, mechanism_gap.gap_id],
        summary=_SUMMARY,
        content_hash="sha256:drone-detr",
        provider="literature_retrieval",
        metadata={
            "doi": "10.3390/s24175496",
            "candidate_gap_ids": "baseline_comparison,failure_mechanism",
            "license": "CC BY 4.0",
            "module_candidate": "inferred",
            "relation": "module_role_query",
            "rank_score": "0.90",
            "relevance_score": "0.90",
        },
    )
    baseline_item = EvidenceItem(
        evidence_id=_BASELINE_ID,
        source_type="paper",
        title="RT-DETR-R18 baseline for small object detection",
        locator="doi:10.1000/rt-detr-baseline",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[baseline_gap.gap_id],
        summary="RT-DETR-R18 is a task-matched detector baseline with a verified paper identity.",
        content_hash="sha256:rt-detr-baseline",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/rt-detr-baseline",
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
            "rank_score": "0.92",
            "relevance_score": "0.90",
            "license": "CC BY 4.0",
        },
    )
    support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
        _support(mechanism_gap.gap_id, mechanism_gap.description),
    )
    baseline_support = _support(
        baseline_gap.gap_id,
        "RT-DETR-R18 supplies the independent baseline identity.",
        evidence_id=_BASELINE_ID,
    )
    ledger = EvidenceLedger(
        entries=(
            EvidenceLedgerEntry(
                evidence_id=_EVIDENCE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=support,
                supported_claims=tuple(item.supported_claim or "" for item in support),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
            EvidenceLedgerEntry(
                evidence_id=_BASELINE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=(baseline_support,),
                supported_claims=(baseline_support.supported_claim or "",),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
        ),
        accepted_ids=(_EVIDENCE_ID, _BASELINE_ID),
        rejected_ids=(),
        coverage_by_gap={baseline_gap.gap_id: 2, mechanism_gap.gap_id: 1},
    )
    synthesis = EvidenceSynthesis(
        gap_assessments=[
            GapAssessment(
                gap_id=baseline_gap.gap_id,
                status="supported",
                evidence_ids=[_EVIDENCE_ID],
                summary="A task-matched UAV detector and comparator are available.",
                limitations=["pilot reproduction remains required"],
            ),
            GapAssessment(
                gap_id=mechanism_gap.gap_id,
                status="supported",
                evidence_ids=[_EVIDENCE_ID],
                summary="Feature fusion is linked to small-object localization limits.",
                limitations=["causal contribution remains unverified"],
            ),
        ],
        verified_findings=[
            Claim(
                claim_id="claim-drone-detr",
                text=(
                    "Drone-DETR reports lightweight feature fusion for small-object detection "
                    "on VisDrone2019."
                ),
                evidence_ids=[_EVIDENCE_ID],
            )
        ],
        conflicts=[],
        feasibility="partially_feasible",
        limitations=["baseline reproduction remains pending"],
    )
    return cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="轻量化无人机小目标检测"),
            "plan": plan,
            "evidence": EvidenceBundle(
                items=[evidence_item, baseline_item],
                accepted_ids=[_EVIDENCE_ID, _BASELINE_ID],
                identity_verified_ids=[_EVIDENCE_ID, _BASELINE_ID],
                coverage_by_gap={baseline_gap.gap_id: 2, mechanism_gap.gap_id: 1},
            ),
            "evidence_ledger": ledger,
            "synthesis": synthesis,
        },
    )


def _draft(**updates: object) -> MethodDesignDraft:
    payload: dict[str, object] = {
        "problem_method_insight": (
            "Small aerial targets lose spatial evidence under aggressive downsampling."
        ),
        "proposed_method_summary": (
            "Add one switchable shallow feature-fusion module and test it under matched compute."
        ),
        "condition": "small targets occupy few pixels in UAV imagery",
        "limitation": "deep downsampling weakens localization cues in complex backgrounds",
        "mechanism": "shape-preserving shallow feature fusion retains fine spatial evidence",
        "intervention": "insert one lightweight fusion module before the detection head",
        "predicted_metric_change": "increase AP_small without violating the latency guardrail",
        "guardrail": "latency and memory must remain within the selected device budget",
        "module_name": "shallow_feature_fusion",
        "module_original_role": "feature enhancement in the accepted paper",
        "module_proposed_role": "single causal small-object feature intervention",
        "input_semantics": "a shallow backbone feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline neck",
        "input_shape": "[B, C3, H/8, W/8] shallow backbone feature map",
        "output_shape": "[B, C3, H/8, W/8] enhanced feature map",
        "insertion_point": "between the stride-8 backbone feature and the first neck fusion block",
        "normalization_contract": "apply source-paper channel normalization before neck fusion",
        "masking_contract": "preserve target-validity masks without adding padding-mask semantics",
        "gradient_path": "detection losses backpropagate through the neck into fusion parameters",
        "trainable_parameters": "feature-fusion convolution and channel-gating parameters",
        "frozen_parameters": "none during the matched end-to-end detector pilot",
        "loss_terms": ["classification loss", "box regression loss"],
        "loss_weighting": "classification weight 1.0 and box regression weight 5.0",
        "predicted_effect": "improve small-object recall and AP_small",
        "failure_mode": "extra high-resolution computation may erase the latency benefit",
        "compute_cost": "one bounded feature-fusion path with measured parameter and latency delta",
        "primary_metric": "AP_small",
        "resource_measures": ["latency", "memory", "parameters"],
        "stopping_criteria": (
            "stop if AP_small gain disappears under matched resolution and training budget"
        ),
        "reported_dataset": "VisDrone2019",
        "reported_comparator": "RT-DETR-R18",
    }
    payload.update(updates)
    return MethodDesignDraft.model_validate(payload)


def _bound_proposal(state: PaperAgentState, draft: MethodDesignDraft):
    proposal = build_method_proposal(state, draft)
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    assert evidence is not None
    assert synthesis is not None
    return bind_method_evidence(proposal, evidence, synthesis)


def test_flat_draft_builds_aligned_canonical_method_proposal() -> None:
    state = _state()
    proposal = _bound_proposal(state, _draft())

    assert proposal.methodology_plan.baseline.name == proposal.baseline.name
    assert proposal.methodology_plan.baseline.dataset == "VisDrone2019"
    assert proposal.methodology_plan.modules[0].name == "shallow_feature_fusion"
    assert proposal.modules[0].module_id == "shallow_feature_fusion"
    assert proposal.stop_conditions == list(proposal.methodology_plan.stop_conditions)
    assert set(proposal.evidence_ids) == {_EVIDENCE_ID, _BASELINE_ID}

    arm_types = {experiment.arm_type for experiment in proposal.methodology_plan.experiments}
    assert arm_types == {
        ExperimentArmType.BASELINE,
        ExperimentArmType.SINGLE_MODULE,
        ExperimentArmType.FULL,
    }
    audit = audit_method_plan(proposal.methodology_plan)
    assert audit.verdict is AuditVerdict.REVISE
    assert audit.verdict is not AuditVerdict.NO_GO


def test_ungrounded_dataset_and_comparator_are_not_promoted_to_facts() -> None:
    proposal = _bound_proposal(
        _state(),
        _draft(
            reported_dataset="InventedDroneBench",
            reported_comparator="ImaginaryDetector-X",
        ),
    )

    baseline = proposal.methodology_plan.baseline
    assert baseline.dataset is not None
    assert "unresolved task-matched" in baseline.dataset
    strong_comparisons = [
        item
        for item in proposal.methodology_plan.experiments
        if item.arm_type is ExperimentArmType.STRONG_COMPARISON
    ]
    assert "InventedDroneBench" not in baseline.dataset
    assert strong_comparisons == []


def test_non_vision_task_does_not_inherit_detector_specific_contracts() -> None:
    state = _state()
    plan = state["plan"]
    evidence = state["evidence"]
    synthesis = state["synthesis"]
    ledger = state["evidence_ledger"]
    assert plan is not None
    assert evidence is not None
    assert synthesis is not None
    assert ledger is not None

    medical_item = evidence.items[0].model_copy(
        update={
            "title": "MultiFusionNet for chest X-ray image classification",
            "summary": (
                "MultiFusionNet fuses chest X-ray representations for multimodal medical image "
                "classification and reports AUC on a public dataset."
            ),
            "locator": "doi:10.1007/s00500-024-09901-x",
            "metadata": {
                "doi": "10.1007/s00500-024-09901-x",
                "candidate_gap_ids": "baseline_comparison,failure_mechanism",
                "module_candidate": "inferred",
                "relation": "module_role_query",
                "rank_score": "0.91",
                "relevance_score": "0.88",
            },
        }
    )
    medical_state = cast(
        PaperAgentState,
        {
            "request": ResearchRequest(question="多模态医学影像融合分类"),
            "plan": plan.model_copy(
                update={
                    "problem_statement": "multimodal medical image classification",
                    "scope": "paired medical image representations with unresolved modalities",
                }
            ),
            "evidence": evidence.model_copy(update={"items": [medical_item, evidence.items[1]]}),
            "evidence_ledger": ledger,
            "synthesis": synthesis,
        },
    )
    proposal = build_method_proposal(
        medical_state,
        _draft(
            primary_metric="AUC",
            reported_dataset="InventedMedicalBench",
            reported_comparator=None,
            module_name="gated_multimodal_fusion",
            module_original_role="medical representation fusion",
            module_proposed_role="single causal fusion intervention",
            input_semantics="paired modality representations",
            output_semantics="fused representation for the classification head",
        ),
    )

    baseline = proposal.methodology_plan.baseline
    module = proposal.methodology_plan.modules[0]
    assert baseline.dataset is not None
    assert "UAV" not in baseline.dataset
    assert "detector" not in (module.input_shape or "").casefold()
    assert "detector" not in " ".join(module.loss_terms).casefold()
    metrics = {
        metric
        for experiment in proposal.methodology_plan.experiments
        for metric in experiment.metrics
    }
    assert "AUC" in metrics
    assert "AP_small" not in metrics


def _audit_with_bound_license(license_value: str | None):
    proposal = _bound_proposal(_state(), _draft())
    plan = proposal.methodology_plan
    evidence = tuple(item.model_copy(update={"license": license_value}) for item in plan.evidence)
    baseline = plan.baseline.model_copy(update={"license": license_value})
    modules = tuple(item.model_copy(update={"license": license_value}) for item in plan.modules)
    return audit_method_plan(
        plan.model_copy(update={"evidence": evidence, "baseline": baseline, "modules": modules})
    )


def test_missing_license_requires_revision_without_forcing_no_go() -> None:
    audit = _audit_with_bound_license(None)
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.REVISE
    assert failed["baseline-license"].severity.value == "warning"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "warning"


def test_explicitly_incompatible_license_remains_no_go() -> None:
    audit = _audit_with_bound_license("proprietary-no-reuse")
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.NO_GO
    assert failed["baseline-license"].severity.value == "critical"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "critical"


def test_unqualified_direct_paper_does_not_become_baseline() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    direct_item = evidence.items[1].model_copy(
        update={
            "metadata": {
                "doi": "10.3390/s24175496",
                "relation": "direct_query",
                "rank_score": "0.99",
                "license": "CC BY 4.0",
            }
        }
    )
    direct_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(update={"items": [evidence.items[0], direct_item]}),
        },
    )
    proposal = build_method_proposal(
        direct_state,
        _draft(
            baseline_readiness_confirmed=True,
            evaluation_protocol_validated=True,
            module_validation_confirmed=True,
        ),
    )
    plan = proposal.methodology_plan
    assert plan.baseline.source_evidence_id is None
    assert plan.baseline.reproduced is False
    assert plan.baseline.baseline_parity_verified is False
    assert "unresolved task-matched baseline" in plan.baseline.name
    assert plan.research.baseline_readiness_confirmed is False
    assert plan.modules[0].evidence_id == _EVIDENCE_ID
    experiments = {experiment.name: experiment for experiment in plan.experiments}
    assert experiments["E0-frozen-baseline"].source_evidence_id is None
    assert experiments["E1-single-module"].source_evidence_id == _EVIDENCE_ID
    assert experiments["E2-full-method"].source_evidence_id == _EVIDENCE_ID


def test_reported_comparator_requires_independent_paper_identity() -> None:
    state = _state()
    proposal = build_method_proposal(
        state,
        _draft(comparison_readiness_confirmed=True),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )


def test_independent_comparator_paper_creates_strong_comparison_arm() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    comparator_id = "ev-rt-detr-r18"
    comparator_item = EvidenceItem(
        evidence_id=comparator_id,
        source_type="paper",
        title="RT-DETR-R18",
        locator="doi:10.1000/rt-detr-r18",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary=(
            "RT-DETR-R18 is a task-matched detector comparison with a documented paper identity."
        ),
        content_hash="sha256:rt-detr-r18",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/rt-detr-r18",
            "comparator_candidate": "inferred",
            "relation": "comparator_role_query",
            "rank_score": "0.95",
        },
    )
    comparator_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, comparator_item],
                    "accepted_ids": [*evidence.accepted_ids, comparator_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        comparator_id,
                    ],
                    "coverage_by_gap": {
                        **evidence.coverage_by_gap,
                        "baseline_comparison": (
                            evidence.coverage_by_gap.get("baseline_comparison", 0) + 1
                        ),
                    },
                }
            ),
        },
    )
    proposal = build_method_proposal(
        comparator_state,
        _draft(comparison_readiness_confirmed=True),
    )
    strong = [
        experiment
        for experiment in proposal.methodology_plan.experiments
        if experiment.arm_type is ExperimentArmType.STRONG_COMPARISON
    ]
    assert len(strong) == 1
    assert strong[0].comparator == "RT-DETR-R18"
    assert strong[0].source_evidence_id == comparator_id


def test_baseline_or_module_evidence_cannot_be_reused_as_comparator() -> None:
    state = _state()
    proposal = build_method_proposal(
        state,
        _draft(
            comparison_readiness_confirmed=True,
            reported_comparator=(
                "Drone-DETR: Efficient Small Object Detection for Remote Sensing Image"
            ),
        ),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )


def test_unmarked_neighbor_paper_is_not_used_as_comparator_fallback() -> None:
    state = _state()
    evidence = state["evidence"]
    assert evidence is not None
    neighbor_id = "ev-unmarked-neighbor"
    neighbor = EvidenceItem(
        evidence_id=neighbor_id,
        source_type="paper",
        title="A Related Detection Study",
        locator="doi:10.1000/related-detection",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary="A related study without an explicit comparator retrieval role.",
        content_hash="sha256:related-detection",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/related-detection",
            "relation": "direct_query",
            "rank_score": "0.99",
        },
    )
    neighbor_state = cast(
        PaperAgentState,
        {
            **state,
            "evidence": evidence.model_copy(
                update={
                    "items": [*evidence.items, neighbor],
                    "accepted_ids": [*evidence.accepted_ids, neighbor_id],
                    "identity_verified_ids": [
                        *evidence.identity_verified_ids,
                        neighbor_id,
                    ],
                    "coverage_by_gap": {
                        **evidence.coverage_by_gap,
                        "baseline_comparison": (
                            evidence.coverage_by_gap.get("baseline_comparison", 0) + 1
                        ),
                    },
                }
            ),
        },
    )
    proposal = build_method_proposal(
        neighbor_state,
        _draft(comparison_readiness_confirmed=True),
    )
    assert all(
        experiment.arm_type is not ExperimentArmType.STRONG_COMPARISON
        for experiment in proposal.methodology_plan.experiments
    )

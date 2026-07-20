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
_SUMMARY = (
    "Drone-DETR is evaluated on the VisDrone2019 dataset for small object detection in UAV "
    "imagery. It uses lightweight feature fusion and reports mAP50 gains over RT-DETR-R18 "
    "while discussing complex backgrounds and occlusion."
)


def _support(gap_id: str, claim: str) -> GapSupportAssessment:
    return GapSupportAssessment(
        evidence_id=_EVIDENCE_ID,
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
        },
    )
    support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
        _support(mechanism_gap.gap_id, mechanism_gap.description),
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
        ),
        accepted_ids=(_EVIDENCE_ID,),
        rejected_ids=(),
        coverage_by_gap={baseline_gap.gap_id: 1, mechanism_gap.gap_id: 1},
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
                items=[evidence_item],
                accepted_ids=[_EVIDENCE_ID],
                identity_verified_ids=[_EVIDENCE_ID],
                coverage_by_gap={baseline_gap.gap_id: 1, mechanism_gap.gap_id: 1},
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
        "input_semantics": "a shallow detector feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
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
    assert set(proposal.evidence_ids) == {_EVIDENCE_ID}

    arm_types = {experiment.arm_type for experiment in proposal.methodology_plan.experiments}
    assert arm_types == {
        ExperimentArmType.BASELINE,
        ExperimentArmType.SINGLE_MODULE,
        ExperimentArmType.FULL,
        ExperimentArmType.STRONG_COMPARISON,
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
    strong_comparison = next(
        item
        for item in proposal.methodology_plan.experiments
        if item.arm_type is ExperimentArmType.STRONG_COMPARISON
    )
    assert strong_comparison.comparator == (
        "strong comparison selected from the accepted evidence set before the pilot"
    )
    assert "InventedDroneBench" not in baseline.dataset
    assert strong_comparison.comparator is not None
    assert "ImaginaryDetector-X" not in strong_comparison.comparator


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
            "evidence": evidence.model_copy(update={"items": [medical_item]}),
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
    assert failed["baseline-license"].severity.value == "error"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "error"


def test_explicitly_incompatible_license_remains_no_go() -> None:
    audit = _audit_with_bound_license("proprietary-no-reuse")
    failed = {item.check_id: item for item in audit.checks if not item.passed}

    assert audit.verdict is AuditVerdict.NO_GO
    assert failed["baseline-license"].severity.value == "critical"
    assert failed["module-license:shallow_feature_fusion"].severity.value == "critical"

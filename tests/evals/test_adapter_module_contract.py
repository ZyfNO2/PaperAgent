from __future__ import annotations

from datetime import UTC, datetime

from paperagent.academic_methodology import ModuleCard
from paperagent.method_design_draft import _select_module_evidence
from paperagent.module_compatibility import evaluate_module_compatibility
from paperagent.schemas import EvidenceItem


def _evidence(
    *,
    evidence_id: str = "ev-module",
    relation: str = "module_role_query",
    title: str = "Feature Gate Module",
    summary: str = "The feature_gate module improves anomaly detection.",
    relevance: str = "0.90",
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["module-gap"],
        summary=summary,
        content_hash=f"sha256:{evidence_id}",
        provider="literature_retrieval",
        metadata={
            "relation": relation,
            "module_candidate": "inferred",
            "module_aliases": "feature_gate",
            "rank_score": "0.90",
            "relevance_score": relevance,
        },
    )


def _module(**updates: object) -> ModuleCard:
    payload: dict[str, object] = {
        "name": "feature_gate",
        "evidence_id": "ev-module",
        "original_role": "feature gating",
        "proposed_role": "anomaly detection feature gating",
        "input_semantics": "encoded time-series features",
        "output_semantics": "gated time-series features",
        "insertion_point": "after the temporal encoder",
        "input_shape": "rank 3 [batch, time, channels]",
        "output_shape": "rank 3 [batch, time, channels]",
        "normalization_contract": "layer normalization over channels",
        "masking_contract": "preserve the temporal validity mask",
        "gradient_path": "gradients flow through gate and encoder",
        "trainable_parameters": "gate projection weights",
        "frozen_parameters": "frozen input embedding",
        "loss_terms": ("binary cross-entropy",),
        "loss_weighting": "binary cross-entropy coefficient 1.0",
    }
    payload.update(updates)
    return ModuleCard.model_validate(payload)


def test_only_independent_module_lane_is_selected() -> None:
    direct = _evidence(evidence_id="ev-direct", relation="direct_query")
    module = _evidence()

    assert _select_module_evidence((direct, module), baseline=None) == module
    assert _select_module_evidence((direct,), baseline=None) is None


def test_baseline_review_and_low_relevance_module_evidence_are_rejected() -> None:
    baseline = _evidence(evidence_id="ev-baseline")
    review = _evidence(title="A Survey of Feature Gate Modules")
    low_relevance = _evidence(relevance="0.24")

    assert _select_module_evidence((baseline,), baseline=baseline) is None
    assert _select_module_evidence((review,), baseline=None) is None
    assert _select_module_evidence((low_relevance,), baseline=None) is None


def test_validator_accepts_specific_independent_contract() -> None:
    evidence = _evidence()
    assessment = evaluate_module_compatibility(
        _module(),
        module_evidence=evidence,
        accepted_evidence_ids=(evidence.evidence_id,),
        baseline_evidence_id="ev-baseline",
        task="time-series anomaly detection",
    )

    assert assessment.compatible
    assert assessment.reasons == ()


def test_validator_rejects_generic_contract_and_shape_rank_mismatch() -> None:
    evidence = _evidence()
    assessment = evaluate_module_compatibility(
        _module(
            insertion_point="selected insertion point",
            output_shape="rank 2 [batch, channels]",
        ),
        module_evidence=evidence,
        accepted_evidence_ids=(evidence.evidence_id,),
        baseline_evidence_id="ev-baseline",
        task="time-series anomaly detection",
    )

    assert not assessment.compatible
    assert "generic_insertion_point" in assessment.reasons
    assert "shape_rank_not_explicit_or_projected" in assessment.reasons

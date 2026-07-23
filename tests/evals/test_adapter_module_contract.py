from __future__ import annotations

from datetime import UTC, datetime

from paperagent.academic_methodology import ModuleCard
from paperagent.module_compatibility import evaluate_module_compatibility
from paperagent.schemas import EvidenceItem


def _module(**updates: object) -> ModuleCard:
    payload: dict[str, object] = {
        "name": "LoRA query value adapters",
        "evidence_id": "ev-lora",
        "original_role": "low-rank adaptation of transformer attention projections",
        "proposed_role": "adapt BERT attention for intent classification",
        "insertion_point": "BERT encoder layers 0-11 query and value projections",
        "input_semantics": "hidden states entering query and value linear projections",
        "output_semantics": "rank-eight low-rank residual added to each projection output",
        "input_shape": "[B, T, 768] hidden-state tensor",
        "output_shape": "[B, T, 768] adapted projection tensor",
        "normalization_contract": "preserve the pre-trained LayerNorm order and scale",
        "masking_contract": "reuse the BERT attention mask before softmax",
        "gradient_path": "classification loss flows through LoRA A/B matrices only",
        "trainable_parameters": "LoRA A and B matrices on query/value projections",
        "frozen_parameters": "all original BERT and classifier parameters",
        "loss_terms": ("intent cross-entropy",),
        "loss_weighting": "intent cross-entropy weight 1.0 with no auxiliary loss",
        "normalization": "preserve the pre-trained LayerNorm order and scale",
        "masks": "reuse the BERT attention mask before softmax",
        "ordering": "BERT encoder layers 0-11 query and value projections",
        "gradient_expectation": "classification loss flows through LoRA A/B matrices only",
        "parameter_update_scope": "train LoRA matrices and freeze the base model",
        "loss_scale": "intent cross-entropy weight 1.0 with no auxiliary loss",
        "failure_mode": "rank-eight adapters may underfit domain-specific intents",
        "compute_cost": "two rank-eight matrices per query/value projection",
        "implementation_switch": "enable_lora",
    }
    payload.update(updates)
    return ModuleCard.model_validate(payload)


def _evidence(**metadata_updates: str) -> EvidenceItem:
    metadata = {
        "relation": "module_role_query",
        "module_candidate": "inferred",
        "rank_score": "0.91",
        "relevance_score": "0.88",
    }
    metadata.update(metadata_updates)
    return EvidenceItem(
        evidence_id="ev-lora",
        source_type="paper",
        title="LoRA: Low-Rank Adaptation of Large Language Models",
        locator="https://arxiv.org/abs/2106.09685",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["module-gap"],
        summary="LoRA inserts low-rank trainable matrices into transformer projection layers.",
        content_hash="sha256:lora",
        metadata=metadata,
    )


def test_specific_independent_module_contract_is_compatible() -> None:
    result = evaluate_module_compatibility(
        module=_module(),
        evidence=_evidence(),
        accepted_ids=("ev-lora",),
        baseline_evidence_id="ev-bert",
        target_text="BERT intent classification with transformer attention adaptation",
    )
    assert result.compatible is True
    assert result.reasons == ()


def test_baseline_reuse_and_generic_contract_return_reason_codes() -> None:
    result = evaluate_module_compatibility(
        module=_module(
            insertion_point="selected representation stage",
            ordering="selected representation stage",
        ),
        evidence=_evidence(),
        accepted_ids=("ev-lora",),
        baseline_evidence_id="ev-lora",
        target_text="BERT intent classification",
    )
    assert result.compatible is False
    assert "module_evidence_reuses_baseline" in result.reasons
    assert "generic_insertion_point" in result.reasons


def test_direct_query_without_marker_is_not_independent_module_evidence() -> None:
    result = evaluate_module_compatibility(
        module=_module(),
        evidence=_evidence(relation="direct_query", module_candidate=""),
        accepted_ids=("ev-lora",),
        baseline_evidence_id="ev-bert",
        target_text="BERT intent classification",
    )
    assert result.compatible is False
    assert "module_relation_not_independent" in result.reasons
    assert "module_candidate_marker_missing" in result.reasons

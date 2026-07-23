from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from paperagent.claw_benchmark_adapter import _module_compatibility_by_evidence
from paperagent.schemas import EvidenceBundle, EvidenceItem
from paperagent.state import PaperAgentState


def _item(evidence_id: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=evidence_id,
        locator=f"https://example.test/{evidence_id}",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="verified evidence",
        content_hash=f"sha256:{evidence_id}",
    )


def _state(evidence_id: str, baseline_id: str) -> PaperAgentState:
    module = SimpleNamespace(
        evidence_id=evidence_id,
        original_role="low-rank query and value adaptation",
        proposed_role="parameter-efficient attention adaptation",
        input_semantics="token hidden states entering query and value projections",
        output_semantics="adapted projections preserving token order",
        input_shape="batch x sequence_length x hidden_size",
        output_shape="batch x sequence_length x hidden_size",
        gradient_expectation="gradients update low-rank matrices and classifier only",
        parameter_update_scope="freeze encoder; train low-rank matrices and classifier",
        loss_scale="unit-weight classification objective",
        failure_mode="rank bottleneck can underfit rare intents",
        implementation_switch="enable_lora_qv",
        loss_terms=("classification objective",),
    )
    ids = list(dict.fromkeys((baseline_id, evidence_id)))
    return cast(
        PaperAgentState,
        {
            "method": SimpleNamespace(
                methodology_plan=SimpleNamespace(
                    baseline=SimpleNamespace(source_evidence_id=baseline_id),
                    modules=(module,),
                )
            ),
            "evidence": EvidenceBundle(
                items=[_item(item_id) for item_id in ids],
                accepted_ids=ids,
                identity_verified_ids=ids,
                coverage_by_gap={"g1": len(ids)},
            ),
        },
    )


def test_specific_independent_module_contract_is_compatible() -> None:
    assert _module_compatibility_by_evidence(_state("ev-module", "ev-baseline")) == {
        "ev-module": True
    }


def test_baseline_reuse_is_never_module_compatible() -> None:
    assert _module_compatibility_by_evidence(_state("ev-baseline", "ev-baseline")) == {
        "ev-baseline": False
    }

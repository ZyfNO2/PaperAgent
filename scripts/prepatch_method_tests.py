from __future__ import annotations

from pathlib import Path

PATH = Path("tests/methodology/test_method_design_draft.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '_EVIDENCE_ID = "ev-drone-detr"\n',
        '_EVIDENCE_ID = "ev-drone-detr"\n_MODULE_EVIDENCE_ID = "ev-shallow-feature-fusion"\n',
        "method test module evidence constant",
    )
    text = replace_once(
        text,
        '            "relation": "parallel_via_dataset",\n            "rank_score": "0.90",\n',
        '            "relation": "baseline_role_query",\n            "rank_score": "0.90",\n            "relevance_score": "0.90",\n',
        "method test baseline metadata",
    )
    text = replace_once(
        text,
        "        supports_gap_ids=[baseline_gap.gap_id, mechanism_gap.gap_id],\n",
        "        supports_gap_ids=[baseline_gap.gap_id],\n",
        "method test baseline gap coverage",
    )
    insertion = """    module_item = EvidenceItem(
        evidence_id=_MODULE_EVIDENCE_ID,
        source_type="paper",
        title="Shallow Feature Fusion for Small Object Detection",
        locator="doi:10.1000/shallow-feature-fusion",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[mechanism_gap.gap_id],
        summary=(
            "Shallow feature fusion enhances fine spatial evidence before detector neck fusion "
            "for small-object localization."
        ),
        content_hash="sha256:shallow-feature-fusion",
        provider="literature_retrieval",
        metadata={
            "doi": "10.1000/shallow-feature-fusion",
            "candidate_gap_ids": "failure_mechanism",
            "license": "CC BY 4.0",
            "module_candidate": "inferred",
            "relation": "module_role_query",
            "rank_score": "0.92",
            "relevance_score": "0.92",
        },
    )
"""
    text = replace_once(
        text,
        """    )
    support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
        _support(mechanism_gap.gap_id, mechanism_gap.description),
    )
    ledger = EvidenceLedger(
""",
        """    )
""" + insertion + """    baseline_support = (
        _support(baseline_gap.gap_id, baseline_gap.description),
    )
    module_support = (
        _support(mechanism_gap.gap_id, mechanism_gap.description).model_copy(
            update={"evidence_id": _MODULE_EVIDENCE_ID}
        ),
    )
    ledger = EvidenceLedger(
""",
        "method test module evidence insertion",
    )
    old_ledger = """        entries=(
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
"""
    new_ledger = """        entries=(
            EvidenceLedgerEntry(
                evidence_id=_EVIDENCE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=baseline_support,
                supported_claims=tuple(
                    item.supported_claim or "" for item in baseline_support
                ),
                limitations=("pilot reproduction remains required",),
                accepted=True,
                rejection_reasons=(),
            ),
            EvidenceLedgerEntry(
                evidence_id=_MODULE_EVIDENCE_ID,
                identity_verified=True,
                relevance_scope="direct",
                gap_supports=module_support,
                supported_claims=tuple(
                    item.supported_claim or "" for item in module_support
                ),
                limitations=("causal contribution remains unverified",),
                accepted=True,
                rejection_reasons=(),
            ),
        ),
        accepted_ids=(_EVIDENCE_ID, _MODULE_EVIDENCE_ID),
        rejected_ids=(),
        coverage_by_gap={baseline_gap.gap_id: 1, mechanism_gap.gap_id: 1},
"""
    text = replace_once(text, old_ledger, new_ledger, "method test evidence ledger")
    text = replace_once(
        text,
        """                evidence_ids=[_EVIDENCE_ID],
                summary="Feature fusion is linked to small-object localization limits.",
""",
        """                evidence_ids=[_MODULE_EVIDENCE_ID],
                summary="Feature fusion is linked to small-object localization limits.",
""",
        "method test mechanism evidence binding",
    )
    text = replace_once(
        text,
        """            "evidence": EvidenceBundle(
                items=[evidence_item],
                accepted_ids=[_EVIDENCE_ID],
                identity_verified_ids=[_EVIDENCE_ID],
""",
        """            "evidence": EvidenceBundle(
                items=[evidence_item, module_item],
                accepted_ids=[_EVIDENCE_ID, _MODULE_EVIDENCE_ID],
                identity_verified_ids=[_EVIDENCE_ID, _MODULE_EVIDENCE_ID],
""",
        "method test evidence bundle",
    )
    text = replace_once(
        text,
        """        "input_semantics": "a shallow detector feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
        "predicted_effect": "improve small-object recall and AP_small",
""",
        """        "input_semantics": "a shallow detector feature map containing fine spatial cues",
        "output_semantics": "a shape-compatible enhanced feature map for the baseline head",
        "input_shape": "[B, C3, H/8, W/8] shallow detector feature map",
        "output_shape": "[B, C3, H/8, W/8] enhanced feature map",
        "insertion_point": "between the stride-8 backbone feature and first neck fusion block",
        "normalization_contract": "apply source module normalization before neck fusion",
        "masking_contract": "preserve detector target-validity masks without new padding masks",
        "gradient_path": "detection losses backpropagate through neck fusion into this module",
        "trainable_parameters": "feature-fusion convolution and channel-gating parameters",
        "frozen_parameters": "none during the matched end-to-end detector pilot",
        "loss_terms": ["classification loss", "box regression loss"],
        "loss_weighting": "use frozen baseline classification and box-loss weights",
        "predicted_effect": "improve small-object recall and AP_small",
""",
        "method test draft contracts",
    )
    text = replace_once(
        text,
        "    assert set(proposal.evidence_ids) == {_EVIDENCE_ID}\n",
        "    assert set(proposal.evidence_ids) == {_EVIDENCE_ID, _MODULE_EVIDENCE_ID}\n",
        "method test evidence assertion",
    )
    text = replace_once(
        text,
        '            "evidence": evidence.model_copy(update={"items": [direct_item]}),\n',
        '            "evidence": evidence.model_copy(\n                update={"items": [direct_item, evidence.items[1]]}\n            ),\n',
        "method test direct baseline preserves module",
    )
    text = replace_once(
        text,
        "    assert plan.modules[0].evidence_id == _EVIDENCE_ID\n",
        "    assert plan.modules[0].evidence_id == _MODULE_EVIDENCE_ID\n",
        "method test direct module evidence assertion",
    )
    text = replace_once(
        text,
        '    assert experiments["E1-single-module"].source_evidence_id == _EVIDENCE_ID\n'
        '    assert experiments["E2-full-method"].source_evidence_id == _EVIDENCE_ID\n',
        '    assert experiments["E1-single-module"].source_evidence_id == _MODULE_EVIDENCE_ID\n'
        '    assert experiments["E2-full-method"].source_evidence_id == _MODULE_EVIDENCE_ID\n',
        "method test experiment module evidence assertions",
    )
    medical_module = """    medical_module_item = evidence.items[1].model_copy(
        update={
            "title": "Gated Multimodal Fusion for Medical Image Classification",
            "summary": (
                "Gated multimodal fusion combines paired medical modality representations "
                "before a classification head."
            ),
            "locator": "doi:10.1000/gated-medical-fusion",
            "metadata": {
                "doi": "10.1000/gated-medical-fusion",
                "candidate_gap_ids": "failure_mechanism",
                "license": "CC BY 4.0",
                "module_candidate": "inferred",
                "relation": "module_role_query",
                "rank_score": "0.92",
                "relevance_score": "0.92",
            },
        }
    )
"""
    text = replace_once(
        text,
        """    )
    medical_state = cast(
""",
        """    )
""" + medical_module + """    medical_state = cast(
""",
        "method test medical module evidence",
    )
    text = replace_once(
        text,
        '            "evidence": evidence.model_copy(update={"items": [medical_item]}),\n',
        '            "evidence": evidence.model_copy(\n                update={"items": [medical_item, medical_module_item]}\n            ),\n',
        "method test medical evidence bundle",
    )
    text = replace_once(
        text,
        """                "candidate_gap_ids": "baseline_comparison,failure_mechanism",
            },
""",
        """                "candidate_gap_ids": "baseline_comparison",
                "license": "CC BY 4.0",
                "baseline_candidate": "inferred",
                "relation": "baseline_role_query",
                "rank_score": "0.90",
                "relevance_score": "0.90",
            },
""",
        "method test medical baseline metadata",
    )
    text = replace_once(
        text,
        """            input_semantics="paired modality representations",
            output_semantics="fused representation for the classification head",
""",
        """            input_semantics="paired modality representations",
            output_semantics="fused representation for the classification head",
            input_shape="[B, M, D] paired modality embeddings",
            output_shape="[B, D] projected fused representation",
            insertion_point="after modality encoders and before the classification head",
            normalization_contract="apply per-modality layer normalization before fusion",
            masking_contract="apply the observed-modality availability mask at the fusion gate",
            gradient_path="classification loss flows through the fusion gate and projections",
            trainable_parameters="fusion gate and modality projection parameters",
            frozen_parameters="modality encoder backbones during the first pilot",
            loss_terms=["binary cross-entropy classification loss"],
            loss_weighting="classification loss weight 1.0 with no auxiliary term",
""",
        "method test medical optimization contracts",
    )
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

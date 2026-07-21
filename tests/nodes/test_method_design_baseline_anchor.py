from __future__ import annotations

from datetime import UTC, datetime

from paperagent.method_design_draft import _select_primary_evidence
from paperagent.schemas import EvidenceItem


def _item(evidence_id: str, title: str) -> EvidenceItem:
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"doi:10.1000/{evidence_id}",
        retrieved_at=datetime(2026, 7, 21, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["g1"],
        summary="Verified method paper with an experimental comparison.",
        content_hash=f"sha256:{evidence_id}",
    )


def test_declared_baseline_is_anchored_even_when_not_first_evidence() -> None:
    distracting = _item("distracting", "An Evaluation of Large Language Models for Sarcasm")
    bert = _item(
        "bert",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
    )

    selected = _select_primary_evidence(
        [
            "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding "
            "[declared role: baseline]"
        ],
        (distracting, bert),
    )

    assert selected.evidence_id == "bert"


def test_similar_prefixed_paper_does_not_replace_declared_baseline() -> None:
    variant = _item(
        "variant",
        "Multispectral-oriented R-CNN for object detection in remote sensing images",
    )
    exact = _item("exact", "Oriented R-CNN for Object Detection")

    selected = _select_primary_evidence(
        ["Oriented R-CNN for Object Detection [declared role: reproduced baseline]"],
        (variant, exact),
    )

    assert selected.evidence_id == "exact"

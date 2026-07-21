from __future__ import annotations

from datetime import UTC, datetime

from paperagent.method_design_draft import (
    _dataset_plan_value,
    _select_dataset_evidence,
    _select_declared_baseline_evidence,
    _select_inferred_baseline_evidence,
    _select_module_evidence,
    _select_primary_evidence,
)
from paperagent.schemas import EvidenceItem


def _item(
    evidence_id: str,
    title: str,
    *,
    metadata: dict[str, str] | None = None,
) -> EvidenceItem:
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
        metadata=metadata or {},
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


def test_missing_declared_baseline_does_not_substitute_neighbor_paper() -> None:
    neighbor = _item("neighbor", "A Different Paper About the Same Task")
    selected = _select_declared_baseline_evidence(
        [
            "PANNs: Large-Scale Pretrained Audio Neural Networks for Audio Pattern "
            "Recognition [declared role: baseline]"
        ],
        (neighbor,),
    )
    assert selected is None


def test_dataset_evidence_prefers_name_present_in_user_question() -> None:
    unrelated = _item("other", "OtherData")
    target = unrelated.model_copy(
        update={"evidence_id": "mimii", "source_type": "dataset", "title": "MIMII"}
    )
    selected = _select_dataset_evidence(
        "Evaluate PANNs on MIMII under low SNR", (unrelated, target)
    )
    assert selected is not None
    assert selected.evidence_id == "mimii"


def test_inferred_baseline_prefers_dataset_linked_parallel_paper() -> None:
    direct = _item(
        "direct",
        "A Broad Survey-like Method Candidate",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "direct_query",
            "rank_score": "0.91",
        },
    )
    linked = _item(
        "linked",
        "A Task-Matched Parallel Baseline",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.72",
        },
    )
    selected = _select_primary_evidence([], (direct, linked))
    assert selected.evidence_id == "linked"


def test_niche_task_can_defer_public_dataset_selection() -> None:
    value = _dataset_plan_value(
        "Design a method for a rare proprietary sensor failure mode",
        readiness_confirmed=False,
    )
    assert "no public dataset is required at discovery time" in value
    assert "freeze provenance" in value


def test_explicit_dataset_request_remains_a_verification_gate() -> None:
    value = _dataset_plan_value(
        "Evaluate the method on the MIMII dataset",
        readiness_confirmed=False,
    )
    assert "declared dataset identity unresolved" in value


def test_dataset_selection_prefers_explicit_question_anchor() -> None:
    audio_set = _item(
        "audioset",
        "AudioSet",
        metadata={
            "relation": "dataset_named_in_verified_paper",
            "rank_score": "0.95",
        },
    ).model_copy(update={"source_type": "dataset"})
    mimii = _item(
        "mimii",
        "MIMII",
        metadata={
            "relation": "dataset_linked_by_focused_retrieval",
            "rank_score": "0.60",
        },
    ).model_copy(update={"source_type": "dataset"})
    selected = _select_dataset_evidence(
        "Evaluate the method on MIMII under low SNR",
        (audio_set, mimii),
    )
    assert selected is not None
    assert selected.title == "MIMII"


def test_dataset_selection_does_not_promote_arbitrary_paper_mention() -> None:
    audio_set = _item(
        "audioset",
        "AudioSet",
        metadata={
            "relation": "dataset_named_in_verified_paper",
            "rank_score": "0.95",
        },
    ).model_copy(update={"source_type": "dataset"})
    selected = _select_dataset_evidence(
        "Design a method for a proprietary rare sensor task",
        (audio_set,),
    )
    assert selected is None


def test_direct_query_neighbor_is_module_evidence_not_baseline() -> None:
    direct = _item(
        "direct-only",
        "A Relevant Mechanism Paper",
        metadata={
            "relation": "direct_query",
            "rank_score": "0.95",
        },
    )
    assert _select_inferred_baseline_evidence((direct,)) is None
    module = _select_module_evidence((direct,), baseline=None)
    assert module is not None
    assert module.evidence_id == "direct-only"


def test_direct_query_cannot_self_declare_inferred_baseline() -> None:
    direct = _item(
        "direct-marker",
        "A Direct Query Paper",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "direct_query",
            "rank_score": "0.99",
        },
    )
    assert _select_inferred_baseline_evidence((direct,)) is None


def test_explicit_baseline_role_query_outranks_dataset_parallel_candidate() -> None:
    role_query = _item(
        "role-query",
        "A Reproducible Baseline Returned by a Baseline Query",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "baseline_role_query",
            "rank_score": "0.70",
        },
    )
    dataset_parallel = _item(
        "dataset-parallel",
        "A Higher Scoring Dataset-Parallel Method",
        metadata={
            "baseline_candidate": "inferred",
            "relation": "parallel_via_dataset",
            "rank_score": "0.95",
        },
    )
    selected = _select_inferred_baseline_evidence((dataset_parallel, role_query))
    assert selected is not None
    assert selected.evidence_id == "role-query"

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paperagent.schemas import EvidenceBundle, EvidenceItem, ResearchRequest
from paperagent.strict_method_design import _prepare_role_bound_state


def _paper(
    evidence_id: str,
    title: str,
    *,
    relation: str,
    baseline_candidate: str | None = None,
) -> EvidenceItem:
    metadata = {"relation": relation, "rank_score": "0.9"}
    if baseline_candidate is not None:
        metadata["baseline_candidate"] = baseline_candidate
    return EvidenceItem(
        evidence_id=evidence_id,
        source_type="paper",
        title=title,
        locator=f"arxiv:{evidence_id}",
        retrieved_at=datetime(2026, 7, 23, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=["baseline_comparison"],
        summary=f"Verified evidence for {title}.",
        content_hash=f"sha256:{evidence_id}",
        metadata=metadata,
    )


def _state(
    references: list[str],
    papers: list[EvidenceItem],
) -> dict[str, object]:
    accepted_ids = [item.evidence_id for item in papers]
    return {
        "request": ResearchRequest(
            question="Design an evidence-backed incremental method.",
            user_material_refs=references,
        ),
        "evidence": EvidenceBundle(
            items=papers,
            accepted_ids=accepted_ids,
            identity_verified_ids=accepted_ids,
            coverage_by_gap={"baseline_comparison": len(papers)},
        ),
    }


def test_declared_patchtst_miss_does_not_fall_through_to_time_machine() -> None:
    patchtst = "A Time Series is Worth 64 Words: Long-term Forecasting with Transformers"
    time_machine = _paper(
        "time-machine",
        "TimeMachine: A Time Series is Worth 4 Mambas for Long-Term Forecasting",
        relation="baseline_role_query",
        baseline_candidate="inferred",
    )
    state = _state([f"{patchtst} [declared role:baseline]"], [time_machine])

    with pytest.raises(ValueError, match="declared baseline identity unresolved"):
        _prepare_role_bound_state(state)  # type: ignore[arg-type]


def test_declared_bert_does_not_match_beit_visual_transformer() -> None:
    bert = "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
    beit = _paper(
        "beit",
        "BEiT: BERT Pre-Training of Image Transformers",
        relation="baseline_role_query",
        baseline_candidate="inferred",
    )
    state = _state([f"{bert} [declared role:baseline]"], [beit])

    with pytest.raises(ValueError, match="declared baseline identity unresolved"):
        _prepare_role_bound_state(state)  # type: ignore[arg-type]


def test_declared_parallel_module_is_re_ranked_independently_from_baseline() -> None:
    bert = _paper(
        "bert",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        relation="declared_identity",
        baseline_candidate="declared",
    )
    lora = _paper(
        "lora",
        "LoRA: Low-Rank Adaptation of Large Language Models",
        relation="declared_identity",
    )
    unrelated = _paper(
        "unrelated",
        "A Generic Direct Query Paper",
        relation="direct_query",
    )
    references = [
        f"{bert.title} [declared role:baseline]",
        f"{lora.title} [declared role:parallel_module_source]",
    ]

    prepared = _prepare_role_bound_state(
        _state(references, [bert, lora, unrelated])  # type: ignore[arg-type]
    )
    evidence = prepared["evidence"]
    selected = next(item for item in evidence.items if item.evidence_id == "lora")

    assert selected.metadata["relation"] == "direct_query"
    assert selected.metadata["role_binding"] == "declared_parallel_method"
    assert selected.metadata["rank_score"] == "1000000"
    assert (
        next(item for item in evidence.items if item.evidence_id == "bert").metadata[
            "baseline_candidate"
        ]
        == "declared"
    )


def test_declared_module_miss_is_not_replaced_by_unattributed_mechanism() -> None:
    bert = _paper(
        "bert",
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        relation="declared_identity",
        baseline_candidate="declared",
    )
    references = [
        f"{bert.title} [declared role:baseline]",
        "LoRA: Low-Rank Adaptation of Large Language Models [declared role:parallel_module_source]",
    ]

    with pytest.raises(ValueError, match="declared parallel/module source unresolved"):
        _prepare_role_bound_state(_state(references, [bert]))  # type: ignore[arg-type]

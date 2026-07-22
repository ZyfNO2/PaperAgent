from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from paperagent.method_design_draft import _select_repository_backed_direct_baseline
from paperagent.schemas.evidence import EvidenceItem


def _item(**values: object) -> EvidenceItem:
    return cast(EvidenceItem, SimpleNamespace(**values))


def test_repo_backed_direct_paper_can_anchor_title_only_baseline() -> None:
    paper = _item(
        evidence_id="ev-paper-deepgo",
        source_type="paper",
        title="DeepGO: predicting protein functions",
        summary="Sequence-based protein function prediction.",
        metadata={"relation": "direct_query", "rank_score": "0.87"},
    )
    higher_rank_without_repo = _item(
        evidence_id="ev-paper-unbound",
        source_type="paper",
        title="Unbound Candidate",
        summary="A task paper without linked implementation.",
        metadata={"relation": "direct_query", "rank_score": "0.99"},
    )
    repository = _item(
        evidence_id="ev-repository-deepgo",
        source_type="repository",
        title="bio-ontology-research-group/deepgo",
        summary="Author-linked implementation.",
        metadata={
            "relation": "author_linked_from_verified_paper",
            "parent_paper_id": "paper-deepgo",
        },
    )
    selected = _select_repository_backed_direct_baseline(
        (paper, higher_rank_without_repo, repository)
    )
    assert selected is paper


def test_repo_backed_review_is_not_selected_as_baseline() -> None:
    review = _item(
        evidence_id="ev-paper-review",
        source_type="paper",
        title="A survey of protein function prediction",
        summary="Review and taxonomy.",
        metadata={"relation": "direct_query", "rank_score": "1.0"},
    )
    repository = _item(
        evidence_id="ev-repository-review",
        source_type="repository",
        title="example/review",
        summary="Linked repository.",
        metadata={
            "relation": "author_linked_from_verified_paper",
            "parent_paper_id": "paper-review",
        },
    )
    assert _select_repository_backed_direct_baseline((review, repository)) is None

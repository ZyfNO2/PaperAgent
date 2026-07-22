from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperagent.schemas import PreparedQuery


def test_non_family_refinement_requires_reason_but_not_removed_families() -> None:
    prepared = PreparedQuery(
        query_id="q1",
        gap_id="g1",
        query="remote sensing small object detection",
        original_query=(
            "remote sensing small object detection benchmark dataset evaluation metrics survey"
        ),
        refinement_reason="removed low-information query terms to preserve provider recall",
        source_types=["paper"],
        round=1,
    )

    assert prepared.removed_families == []
    assert prepared.original_query is not None


def test_family_refinement_keeps_removed_family_audit() -> None:
    prepared = PreparedQuery(
        query_id="q2",
        gap_id="g2",
        query="remote sensing small object detection mechanism",
        original_query=(
            "remote sensing small object detection attention super-resolution "
            "multi-scale feature fusion mechanism"
        ),
        refinement_reason="removed unverified method families",
        removed_families=["attention", "super-resolution", "multi-scale feature fusion"],
        source_types=["paper"],
        round=1,
    )

    assert len(prepared.removed_families) == 3


def test_unmodified_query_cannot_claim_removed_families() -> None:
    with pytest.raises(ValidationError, match="unmodified query"):
        PreparedQuery(
            query_id="q3",
            gap_id="g3",
            query="small object detection",
            removed_families=["attention"],
            source_types=["paper"],
            round=1,
        )

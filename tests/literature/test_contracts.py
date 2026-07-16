from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from paperagent.schemas.literature import (
    LiteratureQueryPlan,
    ProviderPaper,
    ProviderResult,
    QueryLane,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_query_plan_requires_every_required_gap_to_have_lane() -> None:
    with pytest.raises(ValidationError, match="required gaps have no query lane"):
        LiteratureQueryPlan(
            question="How should retrieval work?",
            scope="literature",
            required_gap_ids=["g1", "g2"],
            query_lanes=[
                QueryLane(
                    lane_id="l1",
                    purpose="method",
                    query="retrieval methods",
                    gap_ids=["g1"],
                )
            ],
        )


def test_provider_result_distinguishes_empty_from_failure() -> None:
    empty = ProviderResult(
        provider="openalex",
        request_id="r1",
        status="empty",
        started_at=NOW,
        finished_at=NOW,
    )
    assert empty.status == "empty"

    with pytest.raises(ValidationError, match="failure result requires error_code"):
        ProviderResult(
            provider="openalex",
            request_id="r2",
            status="timeout",
            started_at=NOW,
            finished_at=NOW,
        )


def test_provider_failure_cannot_smuggle_papers() -> None:
    paper = ProviderPaper(provider_record_id="p1", title="Paper")
    with pytest.raises(ValidationError, match="failed provider result cannot contain papers"):
        ProviderResult(
            provider="openalex",
            request_id="r3",
            status="failed",
            papers=[paper],
            started_at=NOW,
            finished_at=NOW,
            error_code="BROKEN",
        )

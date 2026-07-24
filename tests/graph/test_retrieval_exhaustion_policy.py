from __future__ import annotations

from datetime import UTC, datetime

from paperagent.graph import _retrieval_exhaustion_quality
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    RetrievalState,
    SearchQuery,
)


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="held-out task",
        scope="bounded evaluation",
        evidence_gaps=[
            EvidenceGap(gap_id="baseline", description="baseline evidence"),
            EvidenceGap(gap_id="risk", description="negative evidence"),
        ],
        search_queries=[
            SearchQuery(
                query_id="q-baseline",
                gap_id="baseline",
                query="held-out baseline method",
                source_types=["paper"],
            ),
            SearchQuery(
                query_id="q-risk",
                gap_id="risk",
                query="held-out failure evidence",
                source_types=["paper"],
            ),
        ],
    )


def _partial_evidence() -> EvidenceBundle:
    return EvidenceBundle(
        items=[
            EvidenceItem(
                evidence_id="ev-baseline",
                source_type="paper",
                title="Held-out baseline",
                locator="https://example.invalid/baseline",
                retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
                verification_status="accepted",
                supports_gap_ids=["baseline"],
                summary="Verified baseline evidence.",
                content_hash="sha256:baseline",
            )
        ],
        accepted_ids=["ev-baseline"],
        identity_verified_ids=["ev-baseline"],
        coverage_by_gap={"baseline": 1},
    )


def test_partial_verified_evidence_continues_to_provisional_method() -> None:
    quality = _retrieval_exhaustion_quality(
        _plan(),
        _partial_evidence(),
        RetrievalState(round=2, max_rounds=2, budget_exhausted=True),
    )

    assert quality is not None
    assert quality.verdict == "repair_retrieval"
    assert quality.repair_target == "retrieval"
    assert quality.missing_gap_ids == ["risk"]
    assert "Q_PARTIAL_EVIDENCE_COVERAGE" in quality.reason_codes


def test_zero_evidence_still_fails_closed() -> None:
    quality = _retrieval_exhaustion_quality(
        _plan(),
        EvidenceBundle(),
        RetrievalState(round=2, max_rounds=2, budget_exhausted=True),
    )

    assert quality is not None
    assert quality.verdict == "blocked"
    assert set(quality.missing_gap_ids) == {"baseline", "risk"}
    assert "Q_INSUFFICIENT_COVERAGE" in quality.reason_codes

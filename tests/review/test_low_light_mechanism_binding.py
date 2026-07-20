from __future__ import annotations

from datetime import UTC, datetime

from paperagent.evidence_gap_binding import build_evidence_ledger
from paperagent.schemas import (
    EvidenceBundle,
    EvidenceGap,
    EvidenceItem,
    ResearchPlan,
    ResearchRequest,
)
from paperagent.schemas.plan import SearchQuery

_GAP = EvidenceGap(
    gap_id="failure_mechanism_limitations_low_light_pedestrian",
    description=("低光照行人检测的失败机制、固有局限性及可独立验证的并行改进方法证据。"),
)
_QUERY = "low-light pedestrian detection failure limitations mechanism nighttime detection"
_RELEVANT_SUMMARY = (
    "Visible cameras are much less effective at nighttime. Infrared images have drawbacks "
    "including low-resolution, noise, and weather-dependent thermal characteristics. To "
    "overcome these drawbacks, we propose an attention-guided encoder-decoder network. "
    "Multi-scale features and attention highlight pedestrians while reducing background "
    "interference, and experiments report improved precision on two pedestrian datasets."
)


def _plan() -> ResearchPlan:
    return ResearchPlan(
        status="ready",
        problem_statement="低光照行人检测机制分析",
        scope="夜间与弱光行人检测",
        evidence_gaps=[_GAP],
        search_queries=[
            SearchQuery(
                query_id="q-mechanism",
                gap_id=_GAP.gap_id,
                query=_QUERY,
                source_types=["paper"],
            )
        ],
        success_criteria=["找到直接机制证据"],
        risks=["低光定义尚未冻结"],
    )


def _bundle(*, title: str, summary: str) -> EvidenceBundle:
    item = EvidenceItem(
        evidence_id="ev-paper",
        source_type="paper",
        title=title,
        locator="doi:10.3390/app10030809",
        retrieved_at=datetime(2026, 7, 20, tzinfo=UTC),
        verification_status="accepted",
        supports_gap_ids=[_GAP.gap_id],
        summary=summary,
        content_hash="sha256:low-light-test",
        provider="literature_retrieval",
        metadata={"candidate_gap_ids": _GAP.gap_id},
    )
    return EvidenceBundle(
        items=[item],
        accepted_ids=[item.evidence_id],
        identity_verified_ids=[item.evidence_id],
        coverage_by_gap={_GAP.gap_id: 1},
    )


def test_low_light_degradation_and_attention_form_mechanism_evidence() -> None:
    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="低光照行人检测"),
        plan=_plan(),
        evidence=_bundle(
            title=(
                "Pedestrian Detection at Night in Infrared Images Using an "
                "Attention-Guided Encoder-Decoder Network"
            ),
            summary=_RELEVANT_SUMMARY,
        ),
    )

    assert ledger.accepted_ids == ["ev-paper"]
    assert ledger.coverage_by_gap == {_GAP.gap_id: 1}
    binding = next(item for item in supports if item.gap_id == _GAP.gap_id)
    assert binding.decision == "accept"
    assert binding.checklist_results["role_evidence_present"] is True
    assert binding.checklist_results["semantic_gap_binding"] is True


def test_generic_low_light_enhancement_does_not_bind_to_pedestrian_gap() -> None:
    _, _, _, supports, ledger = build_evidence_ledger(
        request=ResearchRequest(question="低光照行人检测"),
        plan=_plan(),
        evidence=_bundle(
            title="Learning Degradation for Low-Light Image Enhancement",
            summary=(
                "A low-light image enhancement network estimates illumination degradation and "
                "refines image color. Experiments evaluate image naturalness."
            ),
        ),
    )

    assert ledger.accepted_ids == []
    binding = next(item for item in supports if item.gap_id == _GAP.gap_id)
    assert binding.decision == "reject"
    assert binding.checklist_results["required_concepts_match"] is False

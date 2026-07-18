from __future__ import annotations

from typing import Literal

from langchain_core.runnables import RunnableConfig

from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.schemas import EvidenceBundle, EvidenceItem, SearchCandidate
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import hash_payload, make_event

NODE = "verify_evidence_node"
_ALLOWED_LOCATOR_PREFIXES = ("fixture://", "https://", "http://", "doi:", "github://")
_STATUS_PRIORITY = {
    "failed_verification": 0,
    "rejected": 1,
    "pending": 2,
    "accepted": 3,
}


def _candidate_status(
    candidate: SearchCandidate,
) -> Literal["accepted", "rejected", "pending", "failed_verification"]:
    external = candidate.metadata.get("verification_status")
    if external == "verified":
        return "accepted"
    if external in {"pending", "suspicious"}:
        return "pending"
    if external == "rejected":
        return "rejected"
    if external == "failed":
        return "failed_verification"
    return (
        "accepted"
        if candidate.locator.startswith(_ALLOWED_LOCATOR_PREFIXES)
        else "failed_verification"
    )


async def verify_evidence_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    retrieval = state.get("retrieval")
    if retrieval is None:
        raise ValueError("retrieval state is required")
    existing = state.get("evidence", EvidenceBundle())
    by_id = {item.evidence_id: item for item in existing.items}
    for candidate in retrieval.raw_candidates:
        evidence_id = f"ev-{candidate.candidate_id}"
        status = _candidate_status(candidate)
        previous = by_id.get(evidence_id)
        supports = sorted(
            set(previous.supports_gap_ids if previous else []) | {candidate.gap_id}
        )
        if (
            previous is not None
            and _STATUS_PRIORITY[previous.verification_status] > _STATUS_PRIORITY[status]
        ):
            status = previous.verification_status
        metadata = dict(previous.metadata) if previous else {}
        metadata.update(candidate.metadata)
        by_id[evidence_id] = EvidenceItem(
            evidence_id=evidence_id,
            source_type=candidate.source_type,
            title=candidate.title,
            locator=candidate.locator,
            retrieved_at=previous.retrieved_at if previous else services.clock.now(),
            verification_status=status,
            supports_gap_ids=supports,
            summary=candidate.snippet,
            content_hash=hash_payload(candidate),
            provider=candidate.provider,
            metadata=metadata,
        )
    items = list(by_id.values())
    accepted = [
        item.evidence_id for item in items if item.verification_status == "accepted"
    ]
    rejected = [
        item.evidence_id for item in items if item.verification_status == "rejected"
    ]
    pending = [
        item.evidence_id for item in items if item.verification_status == "pending"
    ]
    failed = [
        item.evidence_id
        for item in items
        if item.verification_status == "failed_verification"
    ]
    coverage: dict[str, int] = {}
    for item in items:
        if item.verification_status == "accepted":
            for gap_id in item.supports_gap_ids:
                coverage[gap_id] = coverage.get(gap_id, 0) + 1
    plan = state.get("plan")
    exhausted = retrieval.budget_exhausted
    if plan is not None and retrieval.round >= retrieval.max_rounds:
        exhausted = any(
            coverage.get(gap.gap_id, 0) < gap.minimum_accepted_items
            for gap in plan.evidence_gaps
            if gap.required
        )
    if exhausted != retrieval.budget_exhausted:
        retrieval = retrieval.model_copy(update={"budget_exhausted": exhausted})

    bundle = EvidenceBundle(
        items=items,
        accepted_ids=accepted,
        rejected_ids=rejected,
        pending_ids=pending,
        failed_verification_ids=failed,
        coverage_by_gap=coverage,
        conflicts=existing.conflicts,
    )
    trace = [
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.started",
            status="started",
        ),
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.completed",
            status="completed",
            output_payload=bundle,
        ),
    ]
    return {
        "evidence": bundle,
        "retrieval": retrieval,
        "execution": execution_with(state, node=NODE),
        "trace": trace,
    }

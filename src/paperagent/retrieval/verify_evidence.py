from __future__ import annotations

from typing import Literal

from langchain_core.runnables import RunnableConfig

from paperagent.evidence_relevance import apply_ledger_to_bundle, build_evidence_ledger
from paperagent.nodes._shared import execution_with
from paperagent.runtime import get_services
from paperagent.schemas import EvidenceBundle, EvidenceConflict, EvidenceItem, SearchCandidate
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import hash_payload, make_event

NODE = "verify_evidence_node"
_ALLOWED_LOCATOR_PREFIXES = ("fixture://", "https://", "http://", "doi:", "github://")
_TRUSTED_VERIFICATION_PROVIDERS = frozenset({"literature_retrieval"})
_CONTENT_HASH_VERSION = "content-v1"
_DETERMINISTIC_FIXTURE_PROVIDERS = frozenset({"fake_search"})
_STATUS_PRIORITY = {
    "failed_verification": 0,
    "pending": 1,
    "accepted": 2,
    "rejected": 3,
}


def _candidate_status(
    candidate: SearchCandidate,
) -> Literal["accepted", "rejected", "pending", "failed_verification"]:
    external = candidate.metadata.get("verification_status")

    # Negative verification signals are always fail-closed, even when they come
    # from a provider that is not permitted to assert positive verification.
    if external == "rejected":
        return "rejected"
    if external == "failed":
        return "failed_verification"
    if external in {"pending", "suspicious"}:
        return "pending"

    # Positive verification is trusted only from the retrieval service that owns
    # the Crossref/DataCite verification pipeline.
    if candidate.provider in _TRUSTED_VERIFICATION_PROVIDERS:
        return "accepted" if external == "verified" else "pending"

    # Deterministic fixtures are the only non-network exception. A fake provider
    # must still use the explicit fixture scheme; arbitrary HTTPS strings are not
    # accepted merely because they look like locators.
    if candidate.provider in _DETERMINISTIC_FIXTURE_PROVIDERS and candidate.locator.startswith(
        "fixture://"
    ):
        return "accepted"

    if not candidate.locator.startswith(_ALLOWED_LOCATOR_PREFIXES):
        return "failed_verification"
    return "pending"


def _candidate_content_hash(candidate: SearchCandidate) -> str:
    return hash_payload(
        {
            "source_type": candidate.source_type,
            "title": candidate.title,
            "locator": candidate.locator,
            "snippet": candidate.snippet,
        }
    )


def _content_conflict(
    previous: EvidenceItem,
    candidate: SearchCandidate,
    content_hash: str,
) -> bool:
    if previous.source_type != candidate.source_type or previous.locator != candidate.locator:
        return True
    return (
        previous.metadata.get("content_hash_version") == _CONTENT_HASH_VERSION
        and previous.content_hash != content_hash
    )


def _merge_candidate_gap_ids(
    previous: EvidenceItem | None,
    candidate: SearchCandidate,
) -> str:
    gap_ids = {candidate.gap_id}
    if previous is not None:
        gap_ids.update(previous.supports_gap_ids)
        gap_ids.update(
            value.strip()
            for value in previous.metadata.get("candidate_gap_ids", "").split(",")
            if value.strip()
        )
    return ",".join(sorted(gap_ids))


async def verify_evidence_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    services = get_services(config)
    retrieval = state.get("retrieval")
    if retrieval is None:
        raise ValueError("retrieval state is required")
    existing = state.get("evidence", EvidenceBundle())
    by_id = {item.evidence_id: item for item in existing.items}
    conflicts = list(existing.conflicts)
    conflict_ids = {item.conflict_id for item in conflicts}
    for candidate in retrieval.raw_candidates:
        evidence_id = f"ev-{candidate.candidate_id}"
        status = _candidate_status(candidate)
        content_hash = _candidate_content_hash(candidate)
        previous = by_id.get(evidence_id)
        provisional_supports = sorted(
            set(previous.supports_gap_ids if previous else []) | {candidate.gap_id}
        )
        if previous is not None and _content_conflict(previous, candidate, content_hash):
            conflict_id = f"identity-{evidence_id}"
            if conflict_id not in conflict_ids:
                conflicts.append(
                    EvidenceConflict(
                        conflict_id=conflict_id,
                        evidence_ids=[evidence_id],
                        description=(
                            "the same evidence ID resolved to different source identity or content"
                        ),
                    )
                )
                conflict_ids.add(conflict_id)
            by_id[evidence_id] = previous.model_copy(
                update={
                    "verification_status": "rejected",
                    "supports_gap_ids": provisional_supports,
                }
            )
            continue
        if (
            previous is not None
            and _STATUS_PRIORITY[previous.verification_status] > _STATUS_PRIORITY[status]
        ):
            status = previous.verification_status
        metadata = dict(previous.metadata) if previous else {}
        metadata.update(candidate.metadata)
        metadata["content_hash_version"] = _CONTENT_HASH_VERSION
        metadata["candidate_gap_ids"] = _merge_candidate_gap_ids(previous, candidate)
        by_id[evidence_id] = EvidenceItem(
            evidence_id=evidence_id,
            source_type=candidate.source_type,
            title=candidate.title,
            locator=candidate.locator,
            retrieved_at=previous.retrieved_at if previous else services.clock.now(),
            verification_status=status,
            supports_gap_ids=provisional_supports,
            summary=candidate.snippet,
            content_hash=content_hash,
            provider=candidate.provider,
            metadata=metadata,
        )
    items = list(by_id.values())
    identity_verified = [
        item.evidence_id for item in items if item.verification_status == "accepted"
    ]
    rejected = [item.evidence_id for item in items if item.verification_status == "rejected"]
    pending = [item.evidence_id for item in items if item.verification_status == "pending"]
    failed = [
        item.evidence_id for item in items if item.verification_status == "failed_verification"
    ]
    provisional_coverage: dict[str, int] = {}
    for item in items:
        if item.evidence_id in identity_verified:
            for gap_id in item.supports_gap_ids:
                provisional_coverage[gap_id] = provisional_coverage.get(gap_id, 0) + 1
    identity_bundle = EvidenceBundle(
        items=items,
        accepted_ids=identity_verified,
        identity_verified_ids=identity_verified,
        relevance_rejected_ids=[],
        rejected_ids=rejected,
        pending_ids=pending,
        failed_verification_ids=failed,
        coverage_by_gap=provisional_coverage,
        conflicts=conflicts,
    )
    contract, lexical, relevance, gap_support, ledger = build_evidence_ledger(
        request=state.get("request"),
        plan=state.get("plan"),
        evidence=identity_bundle,
    )
    bundle = apply_ledger_to_bundle(identity_bundle, ledger)

    plan = state.get("plan")
    exhausted = retrieval.budget_exhausted
    if plan is not None and retrieval.round >= retrieval.max_rounds:
        exhausted = any(
            bundle.coverage_by_gap.get(gap.gap_id, 0) < gap.minimum_accepted_items
            for gap in plan.evidence_gaps
            if gap.required
        )
    if exhausted != retrieval.budget_exhausted:
        retrieval = retrieval.model_copy(update={"budget_exhausted": exhausted})

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
            output_payload={
                "evidence": bundle,
                "contract": contract,
                "ledger": ledger,
            },
        ),
    ]
    return {
        "research_contract": contract,
        "lexical_assessments": lexical,
        "relevance_assessments": relevance,
        "gap_support_assessments": gap_support,
        "evidence_ledger": ledger,
        "evidence": bundle,
        "retrieval": retrieval,
        "execution": execution_with(state, node=NODE),
        "trace": trace,
    }

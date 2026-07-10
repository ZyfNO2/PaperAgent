"""Re6.4 Novelty Evolution Log — append-only versioning of novelty candidates.

Key invariant: evolution log is append-only. New versions are added,
never overwritten. Each revision captures the full candidate snapshot
at that point in time.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from apps.api.app.services.agents.graph.schemas.novelty_schema import NoveltyRevision, NoveltyCandidate

logger = logging.getLogger(__name__)

EVOLUTION_LOG_KEY = "novelty_evolution_log"


def init_evolution_log(state: dict[str, Any]) -> None:
    """Initialize the evolution log in state if not present."""
    if EVOLUTION_LOG_KEY not in state:
        state[EVOLUTION_LOG_KEY] = []


def get_evolution_log(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Get the current evolution log from state."""
    return state.get(EVOLUTION_LOG_KEY, [])


def append_revision(
    state: dict[str, Any],
    candidate: NoveltyCandidate,
    reason: str,
    evidence_delta: list[str] | None = None,
    next_falsification_test: str | None = None,
) -> NoveltyRevision:
    """Append a new revision to the evolution log.

    Args:
        state: The research state dict
        candidate: The current NoveltyCandidate snapshot
        reason: Why this revision was created
        evidence_delta: Evidence IDs added/removed
        next_falsification_test: Next planned test

    Returns:
        The created NoveltyRevision
    """
    init_evolution_log(state)
    log = state[EVOLUTION_LOG_KEY]

    # Find parent
    parent = None
    if log:
        last = log[-1]
        if last.get("candidate_id") == candidate.candidate_id:
            parent = last.get("revision_id")

    # Determine version
    existing_versions = [
        r.get("version", 0)
        for r in log
        if r.get("candidate_id") == candidate.candidate_id
    ]
    version = max(existing_versions) + 1 if existing_versions else 1

    revision = NoveltyRevision(
        parent_revision_id=parent,
        version=version,
        reason=reason,
        evidence_delta=evidence_delta or [],
        next_falsification_test=next_falsification_test,
        candidate_snapshot=candidate,
    )

    log.append(revision.model_dump())
    state[EVOLUTION_LOG_KEY] = log

    logger.info(
        "evolution_log: candidate=%s v%d reason=%s",
        candidate.candidate_id, version, reason,
    )
    return revision


def get_candidate_history(
    state: dict[str, Any],
    candidate_id: str,
) -> list[dict[str, Any]]:
    """Get all revisions for a specific candidate, ordered by version."""
    log = state.get(EVOLUTION_LOG_KEY, [])
    result = []
    for r in log:
        cid = r.get("candidate_id") or (
            r.get("candidate_snapshot", {}).get("candidate_id", "")
            if isinstance(r.get("candidate_snapshot"), dict) else ""
        )
        if cid == candidate_id:
            result.append(r)
    return sorted(result, key=lambda r: r.get("version", 0))


def get_latest_version(
    state: dict[str, Any],
    candidate_id: str,
) -> dict[str, Any] | None:
    """Get the latest revision for a candidate."""
    history = get_candidate_history(state, candidate_id)
    return history[-1] if history else None


def export_evolution_log(state: dict[str, Any]) -> str:
    """Export the evolution log as formatted JSON string."""
    log = state.get(EVOLUTION_LOG_KEY, [])
    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "total_revisions": len(log),
        "revisions": log,
    }
    return json.dumps(export, ensure_ascii=False, indent=2, default=str)


def mark_innovation_status(
    state: dict[str, Any],
    candidate_id: str,
    new_status: str,
    reason: str,
) -> bool:
    """Update an innovation point's status and log the change.

    Returns True if found and updated.
    """
    innovation_points = state.get("innovation_points", [])
    for ip in innovation_points:
        if not isinstance(ip, dict):
            continue
        if ip.get("candidate_id") == candidate_id or str(ip.get("id")) == candidate_id:
            old_status = ip.get("status", "unknown")
            ip["status"] = new_status
            ip["status_reason"] = reason

            # Log the status change
            init_evolution_log(state)
            state[EVOLUTION_LOG_KEY].append({
                "type": "status_change",
                "candidate_id": candidate_id,
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
    return False

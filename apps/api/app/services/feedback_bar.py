"""Re7.6: FeedbackBar integration for RAG answers and final recommendations.

Endpoints:
  POST /api/v1/feedback/ — existing (feedback.py)
  GET  /api/v1/rag/answer/{case_id} — RAG answer with feedback metadata

Re7.6 additions:
  - Every RAG answer includes a feedback_bar with `idempotency_key` + `artifact_id`
  - Final recommendation includes a feedback_bar
  - Feedback submission binds to `case_id + artifact_type + artifact_id + idempotency_key`
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any


def make_feedback_key(case_id: str, artifact_type: str, artifact_id: str) -> str:
    """Generate a deterministic idempotency key for a feedback target."""
    raw = f"{case_id}:{artifact_type}:{artifact_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def make_feedback_bar(case_id: str, artifact_type: str, artifact_id: str) -> dict[str, Any]:
    """Return a feedback bar payload that the frontend can render."""
    return {
        "artifact_type": artifact_type,
        "artifact_id": artifact_id,
        "idempotency_key": make_feedback_key(case_id, artifact_type, artifact_id),
        "options": ["useful", "incorrect", "unsupported", "needs_more_evidence"],
    }


def make_feedback_bar_for_final_recommendation(
    case_id: str, recommendation: dict[str, Any]
) -> dict[str, Any]:
    """Build a feedback bar for a final recommendation artifact."""
    artifact_id = recommendation.get("artifact_id") or _generate_artifact_id("rec")
    bar = make_feedback_bar(case_id, "final_recommendation", artifact_id)
    bar["options"] = ["useful", "incorrect", "unsupported", "needs_more_evidence"]
    return bar


def _generate_artifact_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"

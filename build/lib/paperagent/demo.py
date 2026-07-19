from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from paperagent.api.executor import (
    CancellationProbe,
    EventEmitter,
    TaskCancelledError,
)
from paperagent.api.models import JsonObject
from paperagent.schemas.request import ResearchRequest


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class DemoTaskExecutor:
    """Deterministic credential-free executor for release and UI verification.

    The output is intentionally synthetic. It exercises the durable task, review, export, and PWA
    contracts without making scientific or provider-quality claims.
    """

    delay_seconds: float = 0.02

    async def execute(
        self,
        *,
        task_id: str,
        request: ResearchRequest,
        emit: EventEmitter,
        should_cancel: CancellationProbe,
    ) -> JsonObject:
        phases = (
            "normalize_request",
            "plan_demo_retrieval",
            "assemble_demo_evidence",
            "render_demo_report",
        )
        for index, phase in enumerate(phases, start=1):
            if should_cancel():
                raise TaskCancelledError("demo task cancelled at a workflow boundary")
            await emit(
                "workflow.progress",
                {
                    "phase": phase,
                    "step": index,
                    "total_steps": len(phases),
                    "demo": True,
                },
            )
            if self.delay_seconds > 0:
                await asyncio.sleep(self.delay_seconds)

        retrieved_at = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        items: list[JsonObject] = [
            {
                "evidence_id": "demo-attention-2017",
                "source_type": "paper",
                "title": "Attention Is All You Need",
                "locator": "https://arxiv.org/abs/1706.03762",
                "retrieved_at": retrieved_at,
                "verification_status": "accepted",
                "supports_gap_ids": ["baseline", "architecture"],
                "summary": (
                    "Synthetic demo card representing a canonical Transformer baseline. "
                    "Use live providers before relying on bibliographic metadata."
                ),
                "content_hash": _content_hash("demo-attention-2017"),
            },
            {
                "evidence_id": "demo-deep-learning-2015",
                "source_type": "paper",
                "title": "Deep learning",
                "locator": "doi:10.1038/nature14539",
                "retrieved_at": retrieved_at,
                "verification_status": "accepted",
                "supports_gap_ids": ["background"],
                "summary": (
                    "Synthetic demo card used to verify DOI rendering, review persistence, "
                    "and deterministic export behavior."
                ),
                "content_hash": _content_hash("demo-deep-learning-2015"),
            },
            {
                "evidence_id": "demo-failed-verification",
                "source_type": "paper",
                "title": "Unverified synthetic candidate",
                "locator": "literature://demo/unverified",
                "retrieved_at": retrieved_at,
                "verification_status": "failed_verification",
                "supports_gap_ids": ["limitations"],
                "summary": (
                    "Synthetic negative-path card. The v0.4 review contract must prevent "
                    "accepting this item."
                ),
                "content_hash": _content_hash("demo-failed-verification"),
            },
        ]
        return {
            "request": request.model_dump(mode="json"),
            "execution": {
                "status": "completed",
                "task_id": task_id,
                "mode": "deterministic_demo",
            },
            "evidence": {
                "items": items,
                "accepted_ids": ["demo-attention-2017", "demo-deep-learning-2015"],
                "rejected_ids": [],
                "pending_ids": [],
                "failed_verification_ids": ["demo-failed-verification"],
                "coverage_by_gap": {
                    "architecture": 1,
                    "background": 1,
                    "baseline": 1,
                },
                "conflicts": [],
            },
            "report": {
                "status": "completed",
                "title": "PaperAgent deterministic demo report",
                "question": request.question,
                "notice": (
                    "This result is synthetic and exists only to validate product contracts. "
                    "It is not a literature review or scientific answer."
                ),
            },
        }

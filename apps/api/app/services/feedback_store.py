"""Re7.4 User Feedback Closed Loop — feedback data model and API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


ArtifactType = Literal[
    "paper", "repo", "dataset", "report",
    "rag_answer", "final_recommendation", "innovation_card",
]
FeedbackVerdict = Literal["supported", "unsupported", "incorrect", "incomplete", "unclear"]


class FeedbackCreate(BaseModel):
    case_id: str = ""
    idempotency_key: str = ""
    artifact_type: ArtifactType = "paper"
    artifact_id: str = ""
    verdict: FeedbackVerdict = "unclear"
    comment: str = Field(default="", max_length=1000)
    selected_citation_ids: list[str] = Field(default_factory=list)
    client_version: str = ""


class FeedbackRecord(BaseModel):
    feedback_id: str = Field(default_factory=lambda: _uuid())
    case_id: str = ""
    idempotency_key: str = ""
    artifact_type: ArtifactType = "paper"
    artifact_id: str = ""
    verdict: FeedbackVerdict = "unclear"
    comment: str = ""
    selected_citation_ids: list[str] = Field(default_factory=list)
    client_version: str = ""
    created_at: str = Field(default_factory=lambda: _utcnow())


class FeedbackSummary(BaseModel):
    total: int = 0
    by_verdict: dict[str, int] = Field(default_factory=dict)
    by_artifact: dict[str, int] = Field(default_factory=dict)
    by_domain: dict[str, int] = Field(default_factory=dict)
    unsupported_incorrect: int = 0


def _uuid() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class FeedbackStore:
    """Append-only JSONL feedback store."""

    def __init__(self, path: str = "tmp_feedback/feedback.jsonl"):
        self._path = path
        import os
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def save(self, feedback: FeedbackCreate) -> FeedbackRecord:
        record = FeedbackRecord(**feedback.model_dump())

        # Check idempotency
        existing = self._find_by_idempotency(feedback.idempotency_key)
        if existing:
            return existing

        import json
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.model_dump(), ensure_ascii=False, default=str) + "\n")
        return record

    def list_by_case(self, case_id: str) -> list[FeedbackRecord]:
        results = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    import json
                    data = json.loads(line)
                    if data.get("case_id") == case_id:
                        results.append(FeedbackRecord(**data))
        except FileNotFoundError:
            pass
        return results

    def list_by_artifact(
        self, case_id: str, artifact_type: str, artifact_id: str
    ) -> list[FeedbackRecord]:
        """Return all feedback for a specific artifact binding."""
        results = []
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    import json
                    data = json.loads(line)
                    if (
                        data.get("case_id") == case_id
                        and data.get("artifact_type") == artifact_type
                        and data.get("artifact_id") == artifact_id
                    ):
                        results.append(FeedbackRecord(**data))
        except FileNotFoundError:
            pass
        return results

    def get_summary(self, from_date: str = "", to_date: str = "") -> FeedbackSummary:
        import json
        summary = FeedbackSummary()
        verdicts: dict[str, int] = {}
        artifacts: dict[str, int] = {}
        unsupported_incorrect = 0

        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    created = data.get("created_at", "")
                    if from_date and created < from_date:
                        continue
                    if to_date and created > to_date:
                        continue

                    verdicts[data.get("verdict", "unclear")] = \
                        verdicts.get(data.get("verdict", "unclear"), 0) + 1
                    artifacts[data.get("artifact_type", "paper")] = \
                        artifacts.get(data.get("artifact_type", "paper"), 0) + 1
                    if data.get("verdict") in ("unsupported", "incorrect"):
                        unsupported_incorrect += 1
                    summary.total += 1
        except FileNotFoundError:
            pass

        summary.by_verdict = verdicts
        summary.by_artifact = artifacts
        summary.unsupported_incorrect = unsupported_incorrect
        return summary

    def delete_by_case(self, case_id: str) -> int:
        """Remove all feedback for a case. Returns count deleted."""
        lines = []
        deleted = 0
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    import json
                    data = json.loads(line.strip())
                    if data.get("case_id") == case_id:
                        deleted += 1
                    else:
                        lines.append(line.strip())
        except FileNotFoundError:
            return 0

        with open(self._path, "w", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        return deleted

    def _find_by_idempotency(self, key: str) -> FeedbackRecord | None:
        import json
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("idempotency_key") == key:
                        return FeedbackRecord(**data)
        except FileNotFoundError:
            pass
        return None

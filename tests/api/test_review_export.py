from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from paperagent.api import (
    PaperReviewUpdate,
    ReviewDecision,
    ReviewExportService,
    SQLiteReviewRepository,
    SQLiteTaskRepository,
    TaskCreateRequest,
    create_app,
)
from paperagent.api.review import (
    ReviewConflictError,
    ReviewTaskNotReadyError,
    ReviewValidationError,
)
from paperagent.schemas import ResearchRequest


class NeverCalledExecutor:
    async def execute(self, **kwargs):
        raise AssertionError(f"executor must not be called: {kwargs}")


def _result() -> dict:
    return {
        "evidence": {
            "items": [
                {
                    "evidence_id": "paper-a",
                    "source_type": "paper",
                    "title": "Alpha {Method}",
                    "locator": "doi:10.1000/alpha",
                    "retrieved_at": "2026-01-01T00:00:00Z",
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-method"],
                    "summary": "Alpha evidence.",
                    "content_hash": "sha256:alpha",
                },
                {
                    "evidence_id": "paper-b",
                    "source_type": "paper",
                    "title": "Beta Preprint",
                    "locator": "https://arxiv.org/abs/2601.00001",
                    "retrieved_at": "2026-01-01T00:00:01Z",
                    "verification_status": "pending",
                    "supports_gap_ids": ["gap-baseline"],
                    "summary": "Beta evidence.",
                    "content_hash": "sha256:beta",
                },
                {
                    "evidence_id": "paper-failed",
                    "source_type": "paper",
                    "title": "Failed Identity",
                    "locator": "https://example.test/failed",
                    "retrieved_at": "2026-01-01T00:00:02Z",
                    "verification_status": "failed_verification",
                    "supports_gap_ids": ["gap-risk"],
                    "summary": "Must not be accepted.",
                    "content_hash": "sha256:failed",
                },
                {
                    "evidence_id": "web-note",
                    "source_type": "web",
                    "title": "Not a paper",
                    "locator": "https://example.test/web",
                    "retrieved_at": "2026-01-01T00:00:03Z",
                    "verification_status": "accepted",
                    "supports_gap_ids": [],
                    "summary": "Excluded from paper cards.",
                    "content_hash": "sha256:web",
                },
            ]
        }
    }


def _succeeded_task(repository: SQLiteTaskRepository, task_id: str = "task-review") -> None:
    repository.create_task(
        task_id=task_id,
        idempotency_key=f"idem-{task_id}",
        payload=TaskCreateRequest(
            request=ResearchRequest(question="Review retrieved academic evidence")
        ),
    )
    assert repository.claim_next_task() is not None
    repository.complete_task(task_id, _result())


def test_review_repository__stable_pagination_and_durable_decisions(tmp_path) -> None:
    tasks = SQLiteTaskRepository(tmp_path / "tasks.db")
    _succeeded_task(tasks)
    reviews = SQLiteReviewRepository(tasks)

    first = reviews.list_cards("task-review", limit=1)
    second = reviews.list_cards("task-review", limit=1, cursor=first.next_cursor)
    assert [item.paper_id for item in first.items] == ["paper-a"]
    assert [item.paper_id for item in second.items] == ["paper-b"]
    assert first.next_cursor is not None

    accepted = reviews.update_review(
        "task-review",
        "paper-a",
        PaperReviewUpdate(
            decision=ReviewDecision.ACCEPTED,
            favorite=True,
            expected_version=0,
        ),
    )
    replayed = reviews.update_review(
        "task-review",
        "paper-a",
        PaperReviewUpdate(
            decision=ReviewDecision.ACCEPTED,
            favorite=True,
            expected_version=1,
        ),
    )
    assert accepted.version == replayed.version == 1

    reopened = SQLiteReviewRepository(SQLiteTaskRepository(tmp_path / "tasks.db"))
    card = reopened.list_cards("task-review", decision=ReviewDecision.ACCEPTED).items[0]
    assert card.paper_id == "paper-a"
    assert card.favorite is True
    assert card.review_version == 1


def test_review_repository__conflict_validation_and_task_readiness(tmp_path) -> None:
    tasks = SQLiteTaskRepository(tmp_path / "tasks.db")
    _succeeded_task(tasks)
    reviews = SQLiteReviewRepository(tasks)
    reviews.update_review(
        "task-review",
        "paper-b",
        PaperReviewUpdate(
            decision=ReviewDecision.REJECTED,
            expected_version=0,
        ),
    )

    with pytest.raises(ReviewConflictError):
        reviews.update_review(
            "task-review",
            "paper-b",
            PaperReviewUpdate(
                decision=ReviewDecision.ACCEPTED,
                expected_version=0,
            ),
        )
    with pytest.raises(ReviewValidationError, match="cannot be accepted"):
        reviews.update_review(
            "task-review",
            "paper-failed",
            PaperReviewUpdate(
                decision=ReviewDecision.ACCEPTED,
                expected_version=0,
            ),
        )
    with pytest.raises(ReviewValidationError, match="invalid paper cursor"):
        reviews.list_cards("task-review", cursor="a")
    with pytest.raises(ReviewValidationError, match="limit"):
        reviews.list_cards("task-review", limit=101)

    tasks.create_task(
        task_id="queued",
        idempotency_key="queued",
        payload=TaskCreateRequest(request=ResearchRequest(question="Queued review task")),
    )
    with pytest.raises(ReviewTaskNotReadyError):
        reviews.list_cards("queued")


def test_review_export__is_deterministic_and_selection_scoped(tmp_path) -> None:
    tasks = SQLiteTaskRepository(tmp_path / "tasks.db")
    _succeeded_task(tasks)
    reviews = SQLiteReviewRepository(tasks)
    reviews.update_review(
        "task-review",
        "paper-a",
        PaperReviewUpdate(
            decision=ReviewDecision.ACCEPTED,
            favorite=True,
            expected_version=0,
        ),
    )
    reviews.update_review(
        "task-review",
        "paper-b",
        PaperReviewUpdate(
            decision=ReviewDecision.REJECTED,
            favorite=True,
            expected_version=0,
        ),
    )
    exporter = ReviewExportService(reviews)

    json_one = exporter.export("task-review", format="json", selection="accepted")
    json_two = exporter.export("task-review", format="json", selection="accepted")
    assert json_one == json_two
    assert json_one.manifest.item_count == 1
    assert json_one.manifest.sha256 == hashlib.sha256(json_one.content.encode()).hexdigest()
    assert [paper["paper_id"] for paper in json.loads(json_one.content)["papers"]] == ["paper-a"]

    markdown = exporter.export("task-review", format="markdown", selection="favorite")
    assert "Alpha {Method}" in markdown.content
    assert "Beta Preprint" in markdown.content
    bibtex = exporter.export("task-review", format="bibtex", selection="all")
    assert "doi = {10.1000/alpha}" in bibtex.content
    assert "archivePrefix = {arXiv}" in bibtex.content
    assert "title = {Alpha \\{Method\\}}" in bibtex.content


def test_review_api__updates_filters_and_downloads_exports(tmp_path) -> None:
    tasks = SQLiteTaskRepository(tmp_path / "tasks.db")
    _succeeded_task(tasks)
    app = create_app(executor=NeverCalledExecutor(), repository=tasks)

    with TestClient(app) as client:
        page = client.get("/v1/tasks/task-review/papers?limit=2")
        assert page.status_code == 200
        assert [item["paper_id"] for item in page.json()["items"]] == [
            "paper-a",
            "paper-b",
        ]
        updated = client.put(
            "/v1/tasks/task-review/papers/paper-a/review",
            json={"decision": "accepted", "favorite": True, "expected_version": 0},
        )
        assert updated.status_code == 200
        assert updated.json()["version"] == 1
        stale = client.put(
            "/v1/tasks/task-review/papers/paper-a/review",
            json={"decision": "rejected", "favorite": False, "expected_version": 0},
        )
        assert stale.status_code == 409
        invalid = client.put(
            "/v1/tasks/task-review/papers/paper-failed/review",
            json={"decision": "accepted", "favorite": False, "expected_version": 0},
        )
        assert invalid.status_code == 422

        accepted = client.get("/v1/tasks/task-review/papers?decision=accepted")
        assert [item["paper_id"] for item in accepted.json()["items"]] == ["paper-a"]
        exported = client.get("/v1/tasks/task-review/exports/bibtex?selection=accepted")
        assert exported.status_code == 200
        assert exported.headers["x-paperagent-item-count"] == "1"
        assert len(exported.headers["x-paperagent-sha256"]) == 64
        assert "attachment;" in exported.headers["content-disposition"]
        assert "10.1000/alpha" in exported.text

        assert client.get("/v1/tasks/missing/papers").status_code == 404
        assert client.get("/v1/tasks/missing/exports/json").status_code == 404
        assert (
            client.put(
                "/v1/tasks/missing/papers/paper-a/review",
                json={"decision": "accepted", "expected_version": 0},
            ).status_code
            == 404
        )

        tasks.create_task(
            task_id="queued-for-review",
            idempotency_key="queued-review",
            payload=TaskCreateRequest(request=ResearchRequest(question="Queued task review API")),
        )
        assert client.get("/v1/tasks/queued-for-review/papers").status_code == 409
        assert (
            client.put(
                "/v1/tasks/queued-for-review/papers/paper-a/review",
                json={"decision": "accepted", "expected_version": 0},
            ).status_code
            == 409
        )
        assert client.get("/v1/tasks/queued-for-review/exports/json").status_code == 409

        assert client.get("/v1/tasks/task-review/papers?cursor=bad").status_code == 422

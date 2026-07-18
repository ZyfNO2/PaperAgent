from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from paperagent.api import SQLiteTaskRepository, TaskCreateRequest
from paperagent.schemas.request import ResearchRequest


def _payload() -> TaskCreateRequest:
    return TaskCreateRequest(
        request=ResearchRequest(question="How should concurrent agent tasks be claimed safely?")
    )


def test_concurrent_idempotent_creates_persist_one_task(tmp_path: Path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "paperagent.db")

    def create(index: int) -> tuple[str, bool]:
        record, reused = repository.create_task(
            task_id=f"task-{index}",
            idempotency_key="shared-idempotency-key",
            payload=_payload(),
        )
        return record.task_id, reused

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(create, range(24)))

    task_ids = {task_id for task_id, _ in results}
    assert len(task_ids) == 1
    assert sum(not reused for _, reused in results) == 1
    assert sum(reused for _, reused in results) == 23


def test_concurrent_claims_never_duplicate_a_task(tmp_path: Path) -> None:
    repository = SQLiteTaskRepository(tmp_path / "paperagent.db")
    for index in range(20):
        repository.create_task(
            task_id=f"task-{index:02d}",
            idempotency_key=f"claim-{index:02d}",
            payload=_payload(),
        )

    def claim(_: int) -> str | None:
        record = repository.claim_next_task()
        return record.task_id if record is not None else None

    with ThreadPoolExecutor(max_workers=10) as pool:
        claimed = [task_id for task_id in pool.map(claim, range(30)) if task_id is not None]

    assert len(claimed) == 20
    assert len(set(claimed)) == 20

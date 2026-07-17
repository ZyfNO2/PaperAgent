from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_memory_store__same_idempotency_key__does_not_duplicate_snapshot() -> None:
    from paperagent.persistence.memory import InMemoryStateStore

    store = InMemoryStateStore()
    first = await store.save("run-1:1", {"status": "completed"})
    second = await store.save("run-1:1", {"status": "completed"})
    assert first.sequence == second.sequence == 1
    assert len(store.snapshots) == 1
    assert await store.load("run-1:1") == {"status": "completed"}

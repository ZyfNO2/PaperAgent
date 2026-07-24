from __future__ import annotations

from copy import deepcopy
from typing import Any

from paperagent.persistence.base import SavedSnapshot


class InMemoryStateStore:
    def __init__(self) -> None:
        self.snapshots: dict[str, dict[str, Any]] = {}
        self._sequences: dict[str, int] = {}

    async def save(self, key: str, state: dict[str, Any]) -> SavedSnapshot:
        if key not in self.snapshots:
            self.snapshots[key] = deepcopy(state)
            self._sequences[key] = len(self.snapshots)
        return SavedSnapshot(key=key, sequence=self._sequences[key])

    async def load(self, key: str) -> dict[str, Any] | None:
        state = self.snapshots.get(key)
        return deepcopy(state) if state is not None else None

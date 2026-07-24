from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field

from paperagent.schemas.base import FrozenModel


class SavedSnapshot(FrozenModel):
    key: str
    sequence: int = Field(ge=1)


class StateStore(Protocol):
    async def save(self, key: str, state: dict[str, Any]) -> SavedSnapshot: ...

    async def load(self, key: str) -> dict[str, Any] | None: ...

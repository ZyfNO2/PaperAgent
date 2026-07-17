from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict

from paperagent.schemas import Message, SearchCandidate, SearchQuery

T = TypeVar("T", bound=BaseModel)


class FixtureKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: str
    scenario: str
    call_index: int
    fixture_version: str = "v0.1"

    def as_path(self) -> str:
        return f"{self.task}/{self.scenario}/{self.call_index}/{self.fixture_version}"


class LLMProvider(Protocol):
    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T: ...


class SearchProvider(Protocol):
    async def search(
        self,
        *,
        query: SearchQuery,
        scenario: str,
        call_index: int,
        fixture_version: str,
        limit: int,
    ) -> list[SearchCandidate]: ...

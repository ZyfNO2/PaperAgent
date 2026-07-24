from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from paperagent.errors import FixtureNotFoundError
from paperagent.schemas import SearchCandidate, SearchQuery


class SearchFixtureKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    scenario: str
    query_id: str
    call_index: int
    fixture_version: str = "v0.1"

    def as_path(self) -> str:
        return f"{self.scenario}/{self.query_id}/{self.call_index}/{self.fixture_version}"


@dataclass(frozen=True)
class SearchCall:
    key: SearchFixtureKey
    query: str
    limit: int


class FakeSearchProvider:
    provider_name = "fake_search"

    def __init__(
        self,
        *,
        fixtures: dict[SearchFixtureKey | tuple[str, str, int, str], list[SearchCandidate]],
        failures: dict[SearchFixtureKey | tuple[str, str, int, str], Exception] | None = None,
    ) -> None:
        self._fixtures = {self._normalize_key(key): value for key, value in fixtures.items()}
        self._failures = {
            self._normalize_key(key): value for key, value in (failures or {}).items()
        }
        self.calls: list[SearchCall] = []

    @staticmethod
    def _normalize_key(
        key: SearchFixtureKey | tuple[str, str, int, str],
    ) -> SearchFixtureKey:
        if isinstance(key, SearchFixtureKey):
            return key
        return SearchFixtureKey(
            scenario=key[0], query_id=key[1], call_index=key[2], fixture_version=key[3]
        )

    async def search(
        self,
        *,
        query: SearchQuery,
        scenario: str,
        call_index: int,
        fixture_version: str,
        limit: int,
    ) -> list[SearchCandidate]:
        key = SearchFixtureKey(
            scenario=scenario,
            query_id=query.query_id,
            call_index=call_index,
            fixture_version=fixture_version,
        )
        self.calls.append(SearchCall(key=key, query=query.query, limit=limit))
        if key in self._failures:
            raise self._failures[key]
        try:
            return list(self._fixtures[key][:limit])
        except KeyError as exc:
            raise FixtureNotFoundError(key.as_path()) from exc

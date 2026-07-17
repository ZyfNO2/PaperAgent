"""Shared E2E utilities: fixture loaders, service factories, and assertion helpers.

Kept separate from ``conftest.py`` so test modules can import these names
without colliding with other ``conftest`` modules (e.g. ``tests/real_llm``)
when pytest collects across multiple directories. ``conftest.py`` retains only
pytest fixtures and re-exports from here for backwards compatibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paperagent.persistence import InMemoryStateStore
from paperagent.providers import (
    FakeLLMProvider,
    FakeSearchProvider,
    FixtureKey,
    SearchFixtureKey,
)
from paperagent.runtime import RuntimeServices
from paperagent.schemas import SearchCandidate
from paperagent.testing import FixedClock, SequenceIdFactory

FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "llm" / "v0_1"
FIXED_TIME = datetime(2026, 1, 1, tzinfo=UTC)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def load_llm_raw(task: str, scenario: str, call_index: int = 0) -> str:
    return (FIXTURE_ROOT / task / f"{scenario}__call_{call_index}.json").read_text(encoding="utf-8")


def happy_path_llm_fixtures() -> dict[FixtureKey, str]:
    return {
        FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
            "planning", "happy_path", 0
        ),
        FixtureKey(task="evidence_synthesis", scenario="happy_path", call_index=0): load_llm_raw(
            "evidence_synthesis", "happy_path", 0
        ),
        FixtureKey(task="method_design", scenario="happy_path", call_index=0): load_llm_raw(
            "method_design", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
        FixtureKey(task="report", scenario="blocked", call_index=0): load_llm_raw(
            "report", "blocked", 0
        ),
    }


def happy_path_search_fixtures() -> dict[SearchFixtureKey, list[SearchCandidate]]:
    return {
        SearchFixtureKey(scenario="happy_path", query_id="query-support-01", call_index=0): [
            SearchCandidate(
                candidate_id="support-001",
                query_id="query-support-01",
                gap_id="gap-support",
                source_type="user_material",
                title="Synthetic support note",
                locator="fixture://evidence/ev-support-001",
                snippet="Claim support can be measured.",
            )
        ],
        SearchFixtureKey(scenario="happy_path", query_id="query-ablation-01", call_index=0): [
            SearchCandidate(
                candidate_id="ablation-001",
                query_id="query-ablation-01",
                gap_id="gap-ablation",
                source_type="user_material",
                title="Synthetic ablation note",
                locator="fixture://evidence/ev-ablation-001",
                snippet="Context ablation separates errors.",
            )
        ],
    }


def build_services(
    *,
    llm_fixtures: dict[FixtureKey, str] | None = None,
    llm_failures: dict[FixtureKey, Exception] | None = None,
    search_fixtures: dict[SearchFixtureKey, list[SearchCandidate]] | None = None,
    prefix: str = "e2e",
) -> RuntimeServices:
    return RuntimeServices(
        FakeLLMProvider(
            fixtures=llm_fixtures or happy_path_llm_fixtures(),
            failures=llm_failures,
        ),
        FakeSearchProvider(fixtures=search_fixtures or happy_path_search_fixtures()),
        FixedClock(FIXED_TIME),
        SequenceIdFactory(prefix),
        InMemoryStateStore(),
    )


# ---------------------------------------------------------------------------
# Assertion helpers
# ---------------------------------------------------------------------------


def completed_nodes(result: dict[str, Any]) -> list[str]:
    return [
        event["node"]
        for event in result.get("trace", [])
        if event.get("event_type") == "node.completed"
    ]


def assert_completed_nodes(result: dict[str, Any], expected: list[str]) -> None:
    actual = completed_nodes(result)
    assert actual == expected, f"node completion order mismatch: {actual} != {expected}"


def event_types(page: dict[str, Any]) -> list[str]:
    return [event["event_type"] for event in page.get("events", [])]

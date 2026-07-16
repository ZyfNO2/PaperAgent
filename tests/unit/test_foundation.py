from __future__ import annotations

from datetime import UTC, datetime

import pytest


def test_package__import__exposes_v0_1_version() -> None:
    import paperagent

    assert paperagent.__version__ == "0.1.0"
    assert paperagent.ENGINE_VERSION == "v0.1"


def test_runtime_config__defaults__are_bounded() -> None:
    from paperagent.config import RuntimeConfig

    config = RuntimeConfig()
    assert config.max_llm_retries == 1
    assert config.recursion_limit == 32
    assert config.fixture_version == "v0.1"


def test_fixed_clock__now__is_deterministic() -> None:
    from paperagent.testing import FixedClock

    instant = datetime(2026, 1, 1, tzinfo=UTC)
    clock = FixedClock(instant)
    assert clock.now() is instant
    assert clock.now() is instant


def test_sequence_id_factory__new_id__is_stable_and_namespaced() -> None:
    from paperagent.testing import SequenceIdFactory

    ids = SequenceIdFactory(prefix="test")
    assert ids.new_id("run") == "test-run-0001"
    assert ids.new_id("run") == "test-run-0002"
    assert ids.new_id("span") == "test-span-0001"


def test_fixture_key__unknown_key__fails_loudly() -> None:
    from paperagent.errors import FixtureNotFoundError
    from paperagent.providers.base import FixtureKey
    from paperagent.providers.fake_llm import FakeLLMProvider

    provider = FakeLLMProvider(fixtures={})
    key = FixtureKey(task="planning", scenario="missing", call_index=0)
    with pytest.raises(FixtureNotFoundError, match="planning/missing/0/v0.1"):
        provider.raw_fixture(key)

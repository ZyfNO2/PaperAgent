"""Re4.1: SourcePolicy tests."""
from __future__ import annotations


import pytest

from apps.api.app.services.source_policy import (
    SourcePolicy,
    get_source_policy,
    reset_source_policy,
)


@pytest.fixture(autouse=True)
def _reset_policy():
    """Reset singleton before and after each test."""
    reset_source_policy()
    yield
    reset_source_policy()


class TestSourcePolicy:
    def test_disabled_source_zero_requests(self) -> None:
        """When S2 is disabled, is_enabled returns False."""
        policy = get_source_policy()
        policy.skip("semantic_scholar")
        assert not policy.is_enabled("semantic_scholar")

    def test_sensitive_sources_disabled_in_test_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """In TEST_MODE, S2/OpenAlex should be disabled by default."""
        monkeypatch.setenv("TEST_MODE", "1")
        reset_source_policy()
        policy = get_source_policy()
        assert not policy.is_enabled("semantic_scholar")
        assert not policy.is_enabled("openalex")
        assert policy.is_enabled("arxiv")

    def test_env_override_enables_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SEMANTIC_SCHOLAR_ENABLED=1 overrides test mode."""
        monkeypatch.setenv("TEST_MODE", "1")
        monkeypatch.setenv("SEMANTIC_SCHOLAR_ENABLED", "1")
        reset_source_policy()
        policy = get_source_policy()
        assert policy.is_enabled("semantic_scholar")

    def test_rate_limited_sources_disabled_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """RATE_LIMITED_SOURCES_DISABLED=1 disables sensitive sources."""
        monkeypatch.setenv("RATE_LIMITED_SOURCES_DISABLED", "1")
        monkeypatch.delenv("TEST_MODE", raising=False)
        reset_source_policy()
        policy = get_source_policy()
        assert not policy.is_enabled("semantic_scholar")
        assert not policy.is_enabled("openalex")
        assert policy.is_enabled("arxiv")

    def test_status_tracking(self) -> None:
        """mark_rate_limited / mark_failed / mark_ok update status correctly."""
        policy = SourcePolicy()
        policy.mark_rate_limited("semantic_scholar")
        assert policy.status("semantic_scholar") == "rate_limited"
        policy.mark_failed("openalex")
        assert policy.status("openalex") == "failed"
        policy.mark_ok("semantic_scholar")
        assert policy.status("semantic_scholar") == "enabled"

    def test_skip_sets_skipped_status(self) -> None:
        """skip() sets status to 'skipped' and disables source."""
        policy = SourcePolicy()
        assert policy.is_enabled("arxiv")
        policy.skip("arxiv")
        assert not policy.is_enabled("arxiv")
        assert policy.status("arxiv") == "skipped"

    def test_summary_contains_all_sources(self) -> None:
        """summary() returns all default sources with full info."""
        policy = SourcePolicy()
        s = policy.summary()
        assert "arxiv" in s
        assert "semantic_scholar" in s
        assert "openalex" in s
        assert s["arxiv"]["concurrency"] == 5
        assert s["semantic_scholar"]["retries"] == 3

    def test_concurrency_and_timeout_defaults(self) -> None:
        """Per-source concurrency/timeout/retries return expected defaults."""
        policy = SourcePolicy()
        assert policy.concurrency("arxiv") == 5
        assert policy.timeout("openalex") == 20
        assert policy.retries("semantic_scholar") == 3
        # Unknown source returns safe defaults
        assert policy.concurrency("unknown_source") == 3
        assert policy.timeout("unknown_source") == 15

    def test_non_sensitive_sources_enabled_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without TEST_MODE or RATE_LIMITED_SOURCES_DISABLED, all sources enabled."""
        monkeypatch.delenv("TEST_MODE", raising=False)
        monkeypatch.delenv("RATE_LIMITED_SOURCES_DISABLED", raising=False)
        reset_source_policy()
        policy = get_source_policy()
        assert policy.is_enabled("semantic_scholar")
        assert policy.is_enabled("openalex")
        assert policy.is_enabled("arxiv")

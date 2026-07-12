"""Re8.0 P0-3: Global Network Policy Guard tests.

Verifies that ``NetworkPolicyGuard`` blocks HTTP calls from retrieval
adapters when ``network_policy=offline``, and allows them when ``online``
or unconfigured (backward compatible).
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from apps.api.app.services.network_guard import (
    NetworkPolicyGuard,
    NetworkPolicyViolation,
)
from apps.api.app.services.retrieval.adapters.arxiv_search import arxiv_search


@pytest.fixture(autouse=True)
def _reset_guard():
    """Reset the singleton guard between tests so state never leaks."""
    NetworkPolicyGuard._reset()
    yield
    NetworkPolicyGuard._reset()


# ---------------------------------------------------------------------------
# Guard unit tests
# ---------------------------------------------------------------------------

class TestNetworkPolicyGuard:
    """Direct tests of the guard singleton."""

    def test_offline_blocks_http(self):
        """configure('offline') → assert_online() raises NetworkPolicyViolation."""
        NetworkPolicyGuard.configure("offline")
        assert NetworkPolicyGuard.is_offline() is True
        with pytest.raises(NetworkPolicyViolation, match="offline"):
            NetworkPolicyGuard.assert_online("test")

    def test_online_allows_http(self):
        """configure('online') → assert_online() does NOT raise."""
        NetworkPolicyGuard.configure("online")
        assert NetworkPolicyGuard.is_offline() is False
        NetworkPolicyGuard.assert_online("test")  # no raise

    def test_default_unconfigured_is_online(self):
        """No configure() call → is_offline() returns False (backward compat)."""
        assert NetworkPolicyGuard.is_offline() is False
        NetworkPolicyGuard.assert_online("test")  # no raise

    def test_violation_message_contains_context(self):
        """The raised exception should name the adapter for debuggability."""
        NetworkPolicyGuard.configure("offline")
        with pytest.raises(NetworkPolicyViolation, match="arxiv"):
            NetworkPolicyGuard.assert_online("arxiv")


# ---------------------------------------------------------------------------
# Adapter integration tests
# ---------------------------------------------------------------------------

class TestArxivAdapterGuard:
    """The arxiv adapter must respect the guard — blocked before any HTTP."""

    @pytest.mark.asyncio
    async def test_offline_blocks_arxiv_adapter(self):
        """Guard offline → arxiv_search raises before fetch_with_timeout."""
        NetworkPolicyGuard.configure("offline")
        with patch(
            "apps.api.app.services.retrieval.adapters.arxiv_search.fetch_with_timeout",
            new_callable=AsyncMock,
        ) as mock_fetch:
            with pytest.raises(NetworkPolicyViolation, match="arxiv"):
                await arxiv_search(["transformer attention"])
            # Critical: the HTTP layer must never have been reached.
            mock_fetch.assert_not_called()

    @pytest.mark.asyncio
    async def test_online_allows_arxiv_adapter(self):
        """Guard online → arxiv_search proceeds to fetch (mocked, no real HTTP)."""
        NetworkPolicyGuard.configure("online")
        with patch(
            "apps.api.app.services.retrieval.adapters.arxiv_search._cache.get",
            return_value=None,
        ), patch(
            "apps.api.app.services.retrieval.adapters.arxiv_search.fetch_with_timeout",
            new_callable=AsyncMock,
            return_value="",  # empty body → parser returns []
        ) as mock_fetch:
            results = await arxiv_search(["transformer attention"])
        # fetch was called (guard did not block)
        mock_fetch.assert_called_once()
        # empty XML → no papers
        assert results == []

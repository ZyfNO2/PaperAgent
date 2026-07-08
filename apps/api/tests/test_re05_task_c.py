"""Re05 SOP §5 Task 4 acceptance — CORE adapter + OpenAlex backup + persistent cache.

No network required.  Uses mock httpx-style client to drive the adapter
endpoints, plus file-system cache tests against a tmp dir.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.agents.retrieval_orchestrator import FAMILY_TO_ADAPTER
from app.services.retrieval.adapters import _cache
from app.services.retrieval.adapters.core_search import core_search
from app.services.retrieval.adapters.openalex_search import (
    openalex_last_backup_empty,
    openalex_search,
)


class _MockClient:
    """Minimal mock satisfying core_search's contract: request -> (status, body)."""

    def __init__(self, response: Any, status: int = 200):
        self.response = response
        self.status = status
        self.last_url: str = ""
        self.last_headers: dict = {}
        self.call_count: int = 0

    async def request(self, method: str, url: str, headers: dict | None = None):
        self.last_url = url
        self.last_headers = headers or {}
        self.call_count += 1
        return (self.status, self.response)


# ---------------------------------------------------------------------------
# CORE adapter
# ---------------------------------------------------------------------------


def _core_hit(title: str, **kw) -> dict:
    base = {
        "title": title,
        "abstract": "An abstract for " + title,
        "yearPublished": 2023,
        "doi": "10.1234/" + title.replace(" ", "-").lower()[:20],
        "url": "https://core.ac.uk/works/123",
    }
    base.update(kw)
    return base


def test_core_adapter_mock_normalizes_fields():
    body = {"results": [_core_hit("Point cloud completion survey"),
                        _core_hit("PCN method paper", yearPublished=2022)]}
    client = _MockClient(body)
    out = asyncio.run(core_search(["point cloud completion"], top_k=5, client=client))
    assert len(out) == 2
    for h in out:
        assert h["source"] == "core"
        assert h["evidence_type"] == "paper"
        assert h["title"]
        assert isinstance(h["year"], int)
        assert h["doi"]
    # The query was passed to the URL.
    assert "point+cloud+completion" in client.last_url or "point%20cloud%20completion" in client.last_url


def test_core_adapter_handles_429_returns_empty_no_raise():
    client = _MockClient("rate limited", status=429)
    out = asyncio.run(core_search(["foo"], client=client))
    assert out == []


def test_core_adapter_handles_500_returns_empty_no_raise():
    client = _MockClient("boom", status=500)
    out = asyncio.run(core_search(["foo"], client=client))
    assert out == []


def test_core_adapter_401_falls_back_to_top_k_3():
    """401 should trigger one retry with limit=3, second 200 returns the results."""
    body = {"results": [_core_hit("retry hit")]}

    class _TwoStep:
        def __init__(self):
            self.call_count = 0
            self.last_url = ""

        async def request(self, method, url, headers=None):
            self.call_count += 1
            self.last_url = url
            if self.call_count == 1:
                return (401, "no key")
            return (200, body)

    two = _TwoStep()
    out = asyncio.run(core_search(["bar"], top_k=8, client=two))
    assert out, "retry should have returned the single hit"
    assert out[0]["title"] == "retry hit"
    assert two.call_count == 2
    # Retry should use limit=3.
    assert "limit=3" in two.last_url


def test_core_adapter_empty_queries_returns_empty():
    assert asyncio.run(core_search([])) == []
    assert asyncio.run(core_search(["", "  "])) == []
    assert asyncio.run(core_search(None)) == []


def test_core_adapter_handles_non_dict_body():
    client = _MockClient("not json")
    out = asyncio.run(core_search(["foo"], client=client))
    assert out == []


# ---------------------------------------------------------------------------
# Persistent cache
# ---------------------------------------------------------------------------


@pytest.fixture
def cache_env(monkeypatch, tmp_path):
    """Enable cache + point at tmp dir."""
    monkeypatch.setenv("PAPERAGENT_ADAPTER_CACHE", "1")
    monkeypatch.setenv("PAPERAGENT_ADAPTER_CACHE_DIR", str(tmp_path / "cache"))
    # Reload module-level constants in the cache module (they read env at import).
    monkeypatch.setattr(_cache, "CACHE_DIR", tmp_path / "cache", raising=False)
    _cache.CACHE_DIR = tmp_path / "cache"
    return tmp_path / "cache"


def test_adapter_cache_hit_returns_same_value(cache_env):
    _cache.put("fake_adapter", "q1", [{"title": "A", "year": 2020}])
    got = _cache.get("fake_adapter", "q1")
    assert got == [{"title": "A", "year": 2020}]


def test_adapter_cache_skips_empty(cache_env):
    _cache.put("fake_adapter", "q_empty", [])
    # Empty must NOT be cached → get returns None.
    assert _cache.get("fake_adapter", "q_empty") is None


def test_adapter_cache_disabled_by_default(monkeypatch, tmp_path):
    """Without PAPERAGENT_ADAPTER_CACHE=1, get always returns None."""
    monkeypatch.delenv("PAPERAGENT_ADAPTER_CACHE", raising=False)
    monkeypatch.setenv("PAPERAGENT_ADAPTER_CACHE_DIR", str(tmp_path / "cache"))
    _cache.CACHE_DIR = tmp_path / "cache"
    _cache.put("fake_adapter", "q_disabled", [{"x": 1}])
    assert _cache.get("fake_adapter", "q_disabled") is None


def test_adapter_cache_key_isolation(cache_env):
    _cache.put("adapter_a", "shared_query", [{"src": "a"}])
    _cache.put("adapter_b", "shared_query", [{"src": "b"}])
    assert _cache.get("adapter_a", "shared_query")[0]["src"] == "a"
    assert _cache.get("adapter_b", "shared_query")[0]["src"] == "b"


# ---------------------------------------------------------------------------
# OpenAlex backup flag (Re05 §5.2)
# ---------------------------------------------------------------------------


class _OAMockClient:
    def __init__(self, responses: list[tuple[int, Any]]):
        self.responses = list(responses)
        self.call_count = 0

    async def request(self, method, url, headers=None):
        self.call_count += 1
        if self.call_count - 1 < len(self.responses):
            return self.responses[self.call_count - 1]
        # default
        return (200, {"results": []})


def test_openalex_backup_empty_flag_set_when_both_attempts_empty():
    """Both primary + backup return 200 with empty results → flag True."""
    client = _OAMockClient([(200, {"results": []}), (200, {"results": []})])
    out = asyncio.run(openalex_search(["x"], top_k=3, client=client))
    assert out == []
    assert openalex_last_backup_empty() is True


def test_openalex_primary_results_skips_backup():
    """Primary returns hits → backup not called, flag False."""
    client = _OAMockClient([(200, {"results": [{"id": "W1", "title": "t"}]})])
    out = asyncio.run(openalex_search(["x"], top_k=3, client=client))
    assert out and out[0]["title"] == "t"
    assert openalex_last_backup_empty() is False
    assert client.call_count == 1


def test_openalex_503_triggers_backup_with_results():
    """Primary 503 → backup 200 with hits → returns backup, flag False."""
    client = _OAMockClient([
        (503, "service unavailable"),
        (200, {"results": [{"id": "W2", "title": "from-backup"}]}),
    ])
    out = asyncio.run(openalex_search(["x"], top_k=3, client=client))
    assert out and out[0]["title"] == "from-backup"
    assert openalex_last_backup_empty() is False
    # backup result tagged
    assert out[0].get("_openalex_source") == "backup"
    assert client.call_count == 2


def test_openalex_503_then_empty_sets_backup_empty_flag():
    client = _OAMockClient([(503, "x"), (200, {"results": []})])
    out = asyncio.run(openalex_search(["x"], top_k=3, client=client))
    assert out == []
    assert openalex_last_backup_empty() is True


# ---------------------------------------------------------------------------
# Orchestrator wiring
# ---------------------------------------------------------------------------


def test_core_in_family_to_adapter():
    """Re05 §5.1: core + dataset families must include 'core' adapter."""
    assert "core" in FAMILY_TO_ADAPTER["core"]
    assert "core" in FAMILY_TO_ADAPTER["dataset"]
    # Other family mappings preserved.
    assert "arxiv" in FAMILY_TO_ADAPTER["core"]
    assert "github" in FAMILY_TO_ADAPTER["repo"]


def test_core_adapter_importable_from_orchestrator_path():
    """Sanity: the import used by orchestrator must resolve."""
    from app.services.retrieval.adapters.core_search import core_search as cs
    assert cs is core_search


def test_core_adapter_uses_httpx_asyncclient(monkeypatch):
    """Verify core_search falls back to httpx.AsyncClient when no client injected.

    Patch httpx.AsyncClient so the test never hits the network.
    """
    import app.services.retrieval.adapters.core_search as core_mod

    captured = {}

    class _FakeAsyncClient:
        def __init__(self, *a, **kw):
            captured["ctor"] = (a, kw)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers
            r = type("R", (), {})()
            r.status_code = 200
            r.headers = {"content-type": "application/json"}
            r.json = lambda: {"results": [_core_hit("via httpx")]}
            return r

    import httpx  # type: ignore
    monkeypatch.setattr(httpx, "AsyncClient", _FakeAsyncClient)
    out = asyncio.run(core_search(["q"]))
    assert out and out[0]["title"] == "via httpx"
    assert captured["url"].startswith(core_mod.CORE_API)
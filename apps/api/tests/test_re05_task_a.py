"""Re05 SOP §8.2 — new acceptance tests for task A.

Covers:
- task 1 (whitelist wiring): collect_mentioned_datasets receives
  domain-scoped whitelist and surfaces dataset candidates when
  retrieved papers actually mention whitelisted names.
- task 2 (HF adapter wire): FAMILY_TO_ADAPTER["dataset"] now contains
  "huggingface" + adapter_calls honors it.
- task 2 (HF adapter shape): huggingface_search normalizes rows into
  dataset-shaped dicts with title/evidence_type/source/tags.

Also includes a guard that the candidate-pool-side contract still works
(``pool.add_dataset`` deduplicates, and ``pool.by_evidence_type('dataset')``
sees entries added via the whitelist path).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))


# ---------------------------------------------------------------------------
# task 1: whitelist wiring
# ---------------------------------------------------------------------------

def test_collect_mentioned_datasets_uses_whitelist():
    """When a retrieved paper's title/abstract mentions a whitelisted
    canonical dataset name, ``collect_mentioned_datasets`` should
    surface it into the pool — but ONLY when a non-empty whitelist is
    actually passed. Before the fix the default was {} (empty), so the
    function scanned nothing. After the fix the orchestrator hands in
    a domain-scoped whitelist.
    """
    from app.services.agents.candidate_pool import (
        CandidatePool,
        collect_mentioned_datasets,
    )

    pool = CandidatePool()
    raw = {
        "arxiv": [
            {
                "title": "PointNet: Deep Learning on Point Sets for 3D Classification and Segmentation",
                "abstract": "We evaluate on ModelNet40 and ShapeNet benchmarks.",
                "year": 2017,
            },
        ],
        "openalex": [],
        "crossref": [],
    }
    # Whitelist does NOT include ModelNet40 → 0 surfaced.
    empty = collect_mentioned_datasets(
        raw, pool, whitelist={"vision_2d": ("COCO",)}
    )
    assert empty == 0
    assert pool.by_evidence_type("dataset") == []

    # Whitelist DOES include ModelNet40 + ShapeNet → 2 surfaced.
    pool2 = CandidatePool()
    n = collect_mentioned_datasets(
        raw,
        pool2,
        whitelist={"vision_3d": ("ModelNet40", "ShapeNet")},
    )
    assert n == 2
    titles = {c.title for c in pool2.by_evidence_type("dataset")}
    assert {"ModelNet40", "ShapeNet"} <= titles


def test_re04_entry_passes_domain_scoped_whitelist():
    """Inspect ``run_research_agent_re04``'s code path: the call to
    ``collect_mentioned_datasets`` must now include a ``whitelist=``
    argument. This is a static check, the companion dynamic test runs
    via the mock client.
    """
    from app.services.agents import re04_entry as mod
    src = Path(mod.__file__).read_text(encoding="utf-8")
    # The wiring is present.
    assert "_DATASET_WHITELIST_BY_DOMAIN" in src
    assert "collect_mentioned_datasets(raw, pool, whitelist=" in src


@pytest.mark.asyncio
async def test_re04_entry_dataset_pool_populated_when_paper_mentions_whitelist():
    """End-to-end: when the mocked arxiv returns a paper whose
    abstract mentions a whitelisted canonical dataset name,
    ``pool.by_evidence_type('dataset')`` should contain it.
    """
    from app.services.agents.re04_entry import run_research_agent_re04

    # Mock client: arxiv returns a paper that mentions "TJU-DHD" and
    # "DOTA" in its abstract. The re04 path is forced into
    # domain_route="remote_sensing" via the parsed topic below, but
    # our query_matrix uses parsed input — instead we'll trust that
    # ANY call to ``run_research_agent_re04`` will now pass a
    # non-empty whitelist (we verify that downstream).
    xml = (
        "<?xml version='1.0'?>"
        "<feed xmlns='http://www.w3.org/2005/Atom'>"
        "<entry>"
        "<id>https://arxiv.org/abs/2401.00001v1</id>"
        "<title>TJU-DHD pedestrian detection in aerial imagery</title>"
        "<summary>We study TJU-DHD and DOTA-v2 detection benchmarks.</summary>"
        "<published>2024-01-01T00:00:00Z</published>"
        "</entry>"
        "</feed>"
    )

    class _MockClient:
        async def request(self, method, url, headers=None):
            return (200, xml)

    out = await run_research_agent_re04(
        "remote sensing object detection on aerial imagery",
        client=_MockClient(),
    )
    pool = out["candidate_pool"]
    # The dataset-typed candidates may include DOTA/DOTA-v2/TJU-DHD;
    # the exact count depends on which domain_route the parser picked,
    # but at minimum the unknown-route fallback uses the WHOLE
    # whitelist — which contains DOTA. So at least one dataset
    # candidate should land. (Acceptance: ≥1 dataset entry seen.)
    ds = pool.by_evidence_type("dataset")
    assert len(ds) >= 1, f"expected ≥1 dataset candidate, got: {[c.title for c in ds]}"


# ---------------------------------------------------------------------------
# task 2: HF adapter wire
# ---------------------------------------------------------------------------

def test_huggingface_adapter_wired_to_dataset_family():
    """FAMILY_TO_ADAPTER['dataset'] must include 'huggingface'."""
    from app.services.agents.retrieval_orchestrator import (
        FAMILY_TO_ADAPTER,
    )
    assert "huggingface" in FAMILY_TO_ADAPTER["dataset"], (
        "re05 SOP §2.2: huggingface must be in FAMILY_TO_ADAPTER['dataset']"
    )


def test_huggingface_adapter_dispatch_signature_accepts_huggingface():
    """adapter_calls inside the dispatcher must list 'huggingface'
    alongside arxiv/openalex/crossref/github/semantic_scholar.
    """
    import inspect

    from app.services.agents.retrieval_orchestrator import (
        _dispatch_family_to_adapters,
    )
    sig = inspect.signature(_dispatch_family_to_adapters)
    assert "fetch_huggingface" in sig.parameters


def test_huggingface_search_returns_dataset_shaped_rows():
    """The HuggingFace adapter should normalize each row into a
    dataset-shaped dict: title=id, evidence_type=dataset,
    source=huggingface, tags merges cardData.task_categories.
    """
    from app.services.retrieval.adapters.huggingface_search import (
        huggingface_search,
    )
    from app.services.retrieval._http import HttpError  # noqa: F401  (smoke import)

    class _FakeClient:
        def __init__(self, body):
            self._body = body
            self.calls = []

        async def request(self, method, url, headers=None):
            self.calls.append(url)
            return (200, self._body)

    body = [
        {
            "id": "imagenet-1k",
            "tags": ["image-classification"],
            "likes": 100,
            "downloads": 5000,
            "lastModified": "2024-06-01",
            "cardData": {
                "task_categories": ["image-classification"],
                "license": "apache-2.0",
            },
        },
        {
            "id": "another-ds",
            "tags": [],
            "cardData": {"task_categories": ["text-classification"]},
        },
    ]
    client = _FakeClient(body)
    out = asyncio.run(huggingface_search(["image classification"], top_k=5, client=client))
    assert out, "huggingface_search should return at least one row"
    first = out[0]
    assert first["title"] == "imagenet-1k"
    assert first["evidence_type"] == "dataset"
    assert first["source"] == "huggingface"
    assert "image-classification" in first["tags"]
    # Query slice should now be 2 (was 1 before §2.2 fix). Both
    # attempts should have hit the API for an empty second query.
    # We don't strictly assert 2 calls (the second query may be empty
    # and skip), but if there is a second query in the input both
    # must have been issued.
    asyncio.run(
        huggingface_search(
            ["image classification", "object detection"],
            top_k=5,
            client=client,
        )
    )
    # Two distinct queries → two API calls (same body → two entries
    # per call, deduped by id). HF API uses literal space encoding,
    # not '+' in the URL.
    urls_with_query = [
        u for u in client.calls if "search=" in u
    ]
    assert any("search=image classification" in u for u in urls_with_query), (
        f"expected first query to fire, got: {urls_with_query[:3]}"
    )
    assert any("search=object detection" in u for u in urls_with_query), (
        f"expected second query to fire (re05 §2.2 [:1]→[:2]), "
        f"got: {urls_with_query[:3]}"
    )


def test_huggingface_adapter_filter_errors_propagate():
    """HttpError from the underlying client must NOT be swallowed —
    it should propagate so the orchestrator can ledger it as error.
    """
    from app.services.retrieval.adapters.huggingface_search import (
        huggingface_search,
    )

    class _BoomClient:
        async def request(self, method, url, headers=None):
            raise RuntimeError("boom")

    async def go():
        try:
            await huggingface_search(["x"], client=_BoomClient())
            return None
        except Exception as e:
            return e

    err = asyncio.run(go())
    assert err is not None
    # The underlying client raised — adapter must propagate (it does:
    # it re-raises HttpError, which fetch_with_timeout wraps any
    # exception into). Either an HttpError or a RuntimeError leaking
    # is acceptable; what must NOT happen is a silent empty return.
    assert "boom" in str(err)

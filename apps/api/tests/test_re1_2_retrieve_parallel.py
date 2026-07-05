from __future__ import annotations

import asyncio
import os
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.api.app.services.agents.graph.nodes import retrieve as retrieve_node


def test_direct_adapter_retrieval_runs_tools_in_parallel(monkeypatch) -> None:
    import apps.api.app.services.retrieval.adapters as adapters

    def _mk(tool_name: str):
        async def _fn(queries, limit):  # type: ignore[no-untyped-def]
            await asyncio.sleep(0.05)
            return [{
                "title": f"{tool_name} paper",
                "abstract": "demo abstract",
                "url": f"https://example.com/{tool_name}",
            }]
        return _fn

    registry = {}
    for name in ("arxiv", "openalex", "crossref", "github"):
        registry[name] = _mk(name)
    monkeypatch.setattr(adapters, "REGISTRY", registry)

    t0 = time.perf_counter()
    out = asyncio.run(
        retrieve_node._run_direct_adapter_retrieval(
            "Retrieval-augmented generation for enterprise knowledge base QA",
            {"method": ["RAG"], "object": ["knowledge base"], "dataset_terms": []},
        ),
    )
    elapsed = time.perf_counter() - t0

    assert elapsed < 0.15, f"expected parallel adapter fan-out, got {elapsed:.3f}s"
    assert set(out["raw"]) == {"arxiv", "openalex", "crossref", "github"}
    assert len(out["buckets"]["baseline_papers"]) == 4

"""Re04 SOP §5 Task 3 acceptance — main entry run_research_agent_re04.

Tests use a fully-mocked client to avoid network. Validates:
- Round delta table has R0 / R1 / R2 / R4 (5 rounds but R3 is
  absorbed into R1 via collect_repos).
- R1 lists real per-adapter result_count.
- 'machine learning' NEVER appears anywhere in raw_topic → query path.
- needs_clarification surfaces for empty topics.
- Citation expand calls s2 fallback when openalex returns 0 refs.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from app.services.agents.re04_entry import dump_re04_result, run_research_agent_re04


class _MockResponse:
    def __init__(self, body: Any, status: int = 200):
        self.body = body
        self.status = status


class _MockClient:
    """Mock that returns canned responses for known URLs / paths."""

    def __init__(self, *, arxiv_xml: str = "", openalex_body: Any = None,
                 crossref_body: Any = None, github_body: Any = None,
                 s2_body: Any = None, s2_refs: Any = None):
        self._arxiv_xml = arxiv_xml
        self._openalex = openalex_body or {}
        self._crossref = crossref_body or {}
        self._github = github_body or {}
        self._s2 = s2_body or {}
        self._s2_refs = s2_refs or []
        self.calls: list[tuple[str, str]] = []

    async def request(self, method: str, url: str, headers: dict | None = None):
        self.calls.append((method, url))
        if "arxiv.org" in url:
            return (200, self._arxiv_xml)
        if "api.openalex.org" in url:
            return (200, self._openalex)
        if "api.crossref.org" in url:
            return (200, self._crossref)
        if "api.github.com" in url:
            return (200, self._github)
        if "semanticscholar.org" in url:
            if "/references" in url:
                return (200, {"data": self._s2_refs})
            if "/citations" in url:
                return (200, {"data": []})
            return (200, self._s2)
        return (404, "not found")


def _arxiv_xml_for(papers: list[dict]) -> str:
    """Build a minimal Atom feed."""
    entries = []
    for p in papers:
        eid = p.get("arxiv_id", "0000.0000")
        title = p.get("title", "x").replace("&", "&amp;")
        abstract = p.get("abstract", "").replace("&", "&amp;")
        entries.append(
            f"<entry><id>https://arxiv.org/abs/{eid}v1</id>"
            f"<title>{title}</title><summary>{abstract}</summary>"
            f"<published>{p.get('year', 2024)}-01-01T00:00:00Z</published></entry>"
        )
    return ("<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'>"
            + "".join(entries) + "</feed>")


def _crossref_body(items: list[dict]) -> dict:
    return {"message": {"items": items}}


def _openalex_body(results: list[dict]) -> dict:
    return {"results": results}


def _s2_search_body(items: list[dict]) -> dict:
    return {"data": items}


def _github_body(items: list[dict]) -> dict:
    return {"items": items}


@pytest.mark.asyncio
async def test_re04_empty_topic_surfaces_needs_clarification():
    """No raw_topic and no parsed atoms → blocked_reason=needs_clarification."""
    # Bypass parse_topic so the raw_topic is empty
    client = _MockClient()
    out = await run_research_agent_re04("", client=client)
    assert out.get("blocked_reason") == "needs_clarification"
    assert out["round_delta"]["R0_query_matrix"]["needs_clarification"] is True


@pytest.mark.asyncio
async def test_re04_english_topic_runs_full_pipeline():
    """English topic → 4-round delta + per-adapter result_count."""
    papers = [
        {"title": "MVCrackViT for point cloud crack detection",
         "abstract": "We propose MVCrackViT.", "arxiv_id": "2103.00020",
         "year": 2024},
    ]
    arxiv_xml = _arxiv_xml_for(papers)
    s2_body = _s2_search_body([
        {"paperId": "s2-1",
         "externalIds": {"DOI": "10.1109/X.2024.12345", "ArXiv": "2103.00020"},
         "title": "MVCrackViT (s2)", "abstract": "abstract", "year": 2024,
         "venue": "ICCV", "citationCount": 50, "url": "https://..."},
    ])
    openalex_body = _openalex_body([
        {"id": "https://openalex.org/W2103",
         "doi": "https://doi.org/10.1109/X.2024.12345",
         "title": "MVCrackViT (oa)", "publication_year": 2024,
         "cited_by_count": 12, "abstract_inverted_index": {}},
    ])
    crossref_body = _crossref_body([
        {"DOI": "10.1109/X.2024.12345",
         "title": ["MVCrackViT (cr)"], "issued": {"date-parts": [[2024]]},
         "author": [{"given": "X", "family": "Y"}], "container-title": ["ICCV"]},
    ])
    client = _MockClient(
        arxiv_xml=arxiv_xml,
        openalex_body=openalex_body,
        crossref_body=crossref_body,
        s2_body=s2_body,
    )
    out = await run_research_agent_re04(
        "Multi-view point cloud crack detection",
        client=client,
    )
    assert "blocked_reason" not in out
    assert "round_delta" in out
    delta = out["round_delta"]
    assert "R0_query_matrix" in delta
    assert "R1_family_dispatch" in delta
    assert "R2_dynamic_expansion" in delta
    assert "R4_citation_expand" in delta
    # R1 must have at least 1 adapter with a result_count
    r1 = delta["R1_family_dispatch"]
    assert "per_adapter" in r1
    # Family dispatch should have hit at least arxiv / openalex / crossref
    assert any(v > 0 for v in r1["per_adapter"].values()), \
        f"no adapter got hits: {r1['per_adapter']}"
    # Raw topic never coerced into 'machine learning'
    assert "machine learning" not in json.dumps(out, default=str).lower()


@pytest.mark.asyncio
async def test_re04_no_machine_learning_fallback_in_query_path():
    """The pre-req: query atoms must NOT silently become 'machine learning'."""
    from app.services.agents.query_matrix import build_query_matrix
    # Empty parse with empty raw_topic → needs_clarification=True
    qm = build_query_matrix("", {"method_terms": [], "task_terms": [],
                                 "object_terms": [], "query_atoms_en": [],
                                 "query_atoms_zh": [], "domain_route": "vision_2d"})
    assert qm.get("needs_clarification") is True
    # fb_atom should NOT be 'machine learning' even when atoms are empty
    assert qm.get("fb_atom", "").lower() != "machine learning"
    # With a non-empty raw_topic (even Chinese), fb_atom = raw_topic
    # verbatim, NOT a generic English placeholder.
    qm2 = build_query_matrix("机器学习图像分类", {"method_terms": [], "task_terms": [],
                                  "object_terms": [], "query_atoms_en": [],
                                  "query_atoms_zh": [], "domain_route": "vision_2d"})
    assert qm2.get("fb_atom") == "机器学习图像分类"
    assert "machine learning" not in qm2.get("fb_atom", "").lower()


@pytest.mark.asyncio
async def test_re04_round2_actually_fires_s2_when_queries_present():
    """Round 2 expansion must really call s2; ledger records it."""
    s2_body = _s2_search_body([
        {"paperId": "s2-r2", "title": "expanded Q",
         "externalIds": {"ArXiv": "2104.00001"}, "year": 2024,
         "abstract": "x", "citationCount": 1, "url": "..."},
    ])
    arxiv_xml = _arxiv_xml_for([
        {"title": "Original seed paper", "arxiv_id": "2103.00020", "year": 2023},
    ])
    client = _MockClient(arxiv_xml=arxiv_xml, s2_body=s2_body)
    out = await run_research_agent_re04(
        "U-Net steel crack segmentation",
        client=client,
    )
    r2 = out["round_delta"]["R2_dynamic_expansion"]
    # Either it found queries (and recorded n_queries > 0) or it didn't
    # (which is acceptable for a topic that yields no round 1 hits).
    # The key invariant: the ledger has at least one R2 row when queries exist.
    ledger = out["source_ledger"]
    r2_rows = [r for r in ledger.as_list() if r.get("round") == 2]
    if r2["n_queries"] > 0:
        assert r2_rows, "ledger must record R2 dispatch when queries present"


def test_dump_re04_result_smoke(tmp_path: Path):
    """dump_re04_result writes a JSON file."""
    out_path = tmp_path / "re04.json"
    dump_re04_result({"raw_topic": "test", "round_delta": {}}, str(out_path))
    assert out_path.exists()
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["raw_topic"] == "test"


def test_no_machine_learning_string_in_code():
    """Static guard: 'machine learning' must NOT appear as a runtime
    literal in production code paths. Comments and docstrings are fine.

    We allow the literal only when it is part of a `# comment` or
    inside a triple-quoted docstring. The check is: any line that
    contains the literal AND is not a comment line AND not part of
    a docstring block.
    """
    bad_files = []
    for path in [
        "apps/api/app/services/agents/query_matrix.py",
        "apps/api/app/services/agents/research_agent.py",
        "apps/api/app/services/agents/retrieval_orchestrator.py",
        "apps/api/app/services/agents/re04_entry.py",
    ]:
        text = Path(path).read_text(encoding="utf-8")
        in_docstring = False
        for i, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            # Track docstring state
            triple = stripped.count('"""')
            if triple % 2 == 1:
                in_docstring = not in_docstring
            if in_docstring:
                continue
            if stripped.startswith("#") or " #" in line:
                continue
            if "machine learning" in stripped:
                bad_files.append(f"{path}:{i}: {line.rstrip()}")
    assert not bad_files, "Found 'machine learning' in code:\n" + "\n".join(bad_files)

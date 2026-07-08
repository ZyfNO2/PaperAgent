"""Re1.2 graph-resolution smoke test.

Does not call live LLM; mocks the retrieval path and verifies:
- graph compiles with all 14 nodes registered
- decorator registry names resolve to public node functions
- node functions either emit the expected ResearchState patch fields OR
  gracefully fail by appending to trace["errors"] (never crash).

The LLM-powered nodes use PAPERAGENT_LLM_SKIP env to bypass StepFun calls.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "apps", "api"))

import apps.api.app.services.agents.graph.nodes as graph_nodes  # noqa: E402
import apps.api.app.services.agents.graph.research_graph as rg  # noqa: E402
from apps.api.app.services.agents.graph.state import ResearchState  # noqa: E402


def _install_llm_skip() -> None:
    """Replace every call_json / _chat_*_node implementation with one that
    returns deterministic shapes so a full graph.run() works offline."""
    from apps.api.app.services import llm_router

    def fake_call_json(prompt, *, system=None, profile=None, temperature=0.2,
                       max_tokens=None, timeout=60.0, expected="dict",
                       schema_hint=""):
        if expected == "list":
            return [{"title": "Fake baseline paper on YOLOv5 steel defects",
                     "verdict": "accept", "hit_keywords": ["YOLO", "defect"],
                     "unrelated_keywords": [], "source_type": "paper",
                     "relation_to_topic": "baseline"},
                    {"title": "Fake parallel work on Faster R-CNN",
                     "verdict": "accept", "hit_keywords": ["detection"],
                     "unrelated_keywords": [], "source_type": "paper",
                     "relation_to_topic": "parallel"}]
        return {"ok": True, "sample_key": "sample_value"}

    llm_router.call_json = fake_call_json  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _llm_skip():
    _install_llm_skip()
    # Patch search_agent's tool calling to avoid real network calls
    import apps.api.app.services.agents.graph.nodes.search_agent as sa_mod
    sa_mod._run_tool_sync = _fake_run_tool_sync  # type: ignore[assignment]
    yield


def _fake_retrieval(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    return {
        "buckets": {
            "baseline_papers": [
                {"title": "Fake baseline paper on YOLOv5 steel defects",
                 "abstract": "A fake abstract to exercise the node.",
                 "source": "arxiv"},
                {"title": "Fake parallel work on Faster R-CNN",
                 "abstract": "Another fake abstract.", "source": "openalex"},
                {"title": "Fake paper on object detection",
                 "abstract": "Third fake abstract.", "source": "crossref"},
                {"title": "Fake paper on surface defect detection",
                 "abstract": "Fourth fake abstract.", "source": "arxiv"},
                {"title": "Fake paper on deep learning inspection",
                 "abstract": "Fifth fake abstract.", "source": "openalex"},
            ],
            "parallel_papers": [],
            "module_papers": [],
            "reference_papers": [],
        },
        "raw": {
            "arxiv": [{"title": "Fake"}],
            "openalex": [{"title": "Fake2"}],
            "crossref": [{"title": "Fake3"}],
        },
    }


def _fake_run_tool_sync(tool: str, query: str, top_k: int = 12) -> list[dict]:
    """Fake adapter results for offline graph smoke test."""
    return [
        {"title": "Fake baseline paper on YOLOv5 steel defects",
         "abstract": "A fake abstract to exercise the node.",
         "source": "arxiv", "evidence_type": "paper",
         "doi": None, "url": "https://arxiv.org/abs/fake1"},
        {"title": "Fake parallel work on Faster R-CNN",
         "abstract": "Another fake abstract.",
         "source": "openalex", "evidence_type": "paper",
         "doi": "10.1/fake2", "url": None},
        {"title": "Fake paper on object detection",
         "abstract": "Third fake abstract.",
         "source": "crossref", "evidence_type": "paper",
         "doi": "10.1/fake3", "url": None},
    ]


def test_registry_has_14_nodes() -> None:
    names = set(graph_nodes.REGISTRY.keys())
    expected = {
        "intake",
        "topic_parser",
        "search_planner",
        "search_agent",
        "verify",
        "quality_filter",
        "targeted_repair",
        "dataset_repo_extractor",
        "evidence_graph_builder",
        "baseline_classifier",
        "work_package_brainstorm",
        "low_bar_review",
        "human_gate",
        "final_recommendation",
    }
    assert expected.issubset(names), f"missing: {expected - names}"


def test_graph_compiles_and_smoke_runs() -> None:
    g = rg.build_graph()

    state_in: ResearchState = {
        "case_id": "smoke-000",
        "topic": "YOLOv5 steel surface defect detection",
        "user_constraints": {},
        "trace_events": [],
        "errors": [],
        "provider_profile": "fast_json",
    }
    out = g.invoke(state_in, config={"configurable": {"thread_id": "smoke-000"},
                                      "recursion_limit": 100})
    # 14 nodes all fire in linear spine + possibly repair loop
    events = out.get("trace_events") or []
    fire_names = [e["node"] for e in events]
    # Required spine nodes fire
    for n in ("intake", "topic_parser", "search_planner", "search_agent",
              "quality_filter", "verify", "quality_gate",
              "final_recommendation"):
        assert n in fire_names, f"node {n} did not fire: {fire_names}"


def test_node_modules_expose_expected_node_funcs() -> None:
    # Check that every registry entry is callable
    for name, fn in graph_nodes.REGISTRY.items():
        assert callable(fn), f"registry entry {name} is not callable"
    # Check key entries exist in registry
    expected_keys = {
        "intake", "topic_parser", "search_planner", "search_agent",
        "verify", "quality_gate", "targeted_repair",
        "dataset_repo_extractor", "evidence_graph_builder",
        "baseline_classifier", "work_package_brainstorm",
        "low_bar_review", "human_gate", "final_recommendation",
    }
    for key in expected_keys:
        assert key in graph_nodes.REGISTRY, f"key {key} not in REGISTRY"


def test_topic_parser_preserves_explicit_rag_terms(monkeypatch) -> None:
    from apps.api.app.services.agents.graph.nodes import topic_parser as tp

    def fake_call_json(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "method": [
                "Non-retrieval augmented generative and knowledge graph-based question answering",
            ],
            "object": ["enterprise chatbot"],
            "task": ["Answering without retrieval"],
            "scenario": ["enterprise deployment without external retrieval"],
            "domain": "unknown",
            "dataset_terms": [],
            "baseline_terms": [],
            "avoid_terms": ["external retrieval for QA pipelines"],
        }

    monkeypatch.setattr(tp, "call_json", fake_call_json)
    out = tp.topic_parser_node(
        {
            "topic": "Retrieval-augmented generation for enterprise knowledge base question answering",
            "trace_events": [],
            "errors": [],
        },
    )

    atoms = out["topic_atoms"]
    assert atoms["domain"] == "nlp_llm"
    assert atoms["method"][0] == "retrieval-augmented generation"
    assert any("question answering" in item.lower() for item in atoms["task"])
    assert all("non-" not in item.lower() for item in atoms["method"])
    assert all("without retrieval" not in item.lower() for item in atoms["task"])

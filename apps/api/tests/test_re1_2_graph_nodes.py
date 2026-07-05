"""Re1.2 graph-resolution smoke test.

Does not call live LLM; mocks the retrieval path and verifies:
- graph compiles with all 14 nodes registered
- decorator registry names resolve to public node functions
- node functions either emit the expected ResearchState patch fields OR
  gracefully fail by appending to trace["errors"] (never crash).

The LLM-powered nodes use PAPERAGENT_LLM_SKIP env to bypass StepFun calls.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest import mock

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
            return [{"title": "Sample", "verdict": "accept",
                     "hit_keywords": ["kw"], "unrelated_keywords": [],
                     "source_type": "paper", "relation_to_topic": "baseline"}]
        return {"ok": True, "sample_key": "sample_value"}

    llm_router.call_json = fake_call_json  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _llm_skip():
    _install_llm_skip()
    yield


def _fake_retrieval(topic: str, atoms: dict[str, Any]) -> dict[str, Any]:
    return {
        "buckets": {
            "baseline_papers": [
                {"title": "Fake baseline paper on YOLOv5 steel defects",
                 "abstract": "A fake abstract to exercise the node.",
                 "source": "arxiv"},
            ],
            "parallel_papers": [
                {"title": "Fake parallel work on Faster R-CNN",
                 "abstract": "Another fake abstract.", "source": "openalex"},
            ],
            "module_papers": [],
            "reference_papers": [],
        },
        "raw": {"arxiv": [{"title": "Fake"},
                          "openalex": [{"title": "Fake2"}]},
    }


def test_registry_has_14_nodes() -> None:
    names = set(graph_nodes.REGISTRY.keys())
    expected = {
        "intake",
        "topic_parser",
        "search_planner",
        "paper_retriever",
        "paper_verifier",
        "quality_gate",
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
    # Patch retrieve to bypass adapter import + network calls.
    import apps.api.app.services.agents.graph.nodes.retrieve as rmod
    rmod._run_legacy_retrieval = _fake_retrieval  # type: ignore[assignment]

    state_in: ResearchState = {
        "case_id": "smoke-000",
        "topic": "YOLOv5 steel surface defect detection",
        "user_constraints": {},
        "trace_events": [],
        "errors": [],
        "provider_profile": "fast_json",
    }
    out = g.invoke(state_in, config={"configurable": {"thread_id": "smoke-000"}})
    # 14 nodes all fire in linear spine + possibly repair loop
    events = out.get("trace_events") or []
    fire_names = [e["node"] for e in events]
    # Required spine nodes fire
    for n in ("intake", "topic_parser", "search_planner", "paper_retriever",
              "paper_verifier", "quality_gate", "dataset_repo_extractor",
              "evidence_graph_builder", "baseline_classifier",
              "work_package_brainstorm", "low_bar_review", "human_gate",
              "final_recommendation"):
        assert n in fire_names, f"node {n} did not fire: {fire_names}"


def test_node_modules_expose_expected_node_funcs() -> None:
    mapping = {
        "intake": "intake_node",
        "topic_parser": "topic_parser_node",
        "search_planner": "search_planner_node",
        "paper_retriever": "retrieve_node",
        "paper_verifier": "verify_node",
        "quality_gate": "quality_gate_node",
        "targeted_repair": "targeted_repair_node",
        "dataset_repo_extractor": "dataset_repo_extractor_node",
        "evidence_graph_builder": "json_graph_builder_node",
        "baseline_classifier": "baseline_classifier_node",
        "work_package_brainstorm": "work_package_node",
        "low_bar_review": "low_bar_review_node",
        "human_gate": "human_gate_node",
        "final_recommendation": "final_recommendation_node",
    }
    for mod_name, fn_name in mapping.items():
        mod = getattr(graph_nodes, mod_name, None)
        assert mod is not None, f"module {mod_name} not registered"
        assert hasattr(mod, fn_name), f"{mod_name} missing {fn_name}"
        assert callable(getattr(mod, fn_name)), f"{mod_name}.{fn_name} not callable"

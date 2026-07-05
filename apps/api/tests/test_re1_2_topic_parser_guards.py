from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.api.app.services.agents.graph.nodes import topic_parser as tp


def test_topic_parser_preserves_explicit_rag_terms(monkeypatch) -> None:
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


def test_topic_parser_preserves_explicit_chinese_rag_terms(monkeypatch) -> None:
    def fake_call_json(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "method": ["生成式问答"],
            "object": [],
            "task": [],
            "scenario": [],
            "domain": "unknown",
            "dataset_terms": [],
            "baseline_terms": [],
            "avoid_terms": [],
        }

    monkeypatch.setattr(tp, "call_json", fake_call_json)
    out = tp.topic_parser_node(
        {
            "topic": "基于检索增强生成的企业知识库问答系统研究",
            "trace_events": [],
            "errors": [],
        },
    )

    atoms = out["topic_atoms"]
    assert atoms["domain"] == "nlp_llm"
    assert "retrieval-augmented generation" in [item.lower() for item in atoms["method"]]
    assert any("knowledge base" in item.lower() for item in atoms["object"] + atoms["scenario"])
    assert any("question answering" in item.lower() for item in atoms["task"])

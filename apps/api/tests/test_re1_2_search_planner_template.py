from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.api.app.services.agents.graph.nodes import search_planner as sp


def test_template_plan_boosts_rag_queries_for_unknown_domain() -> None:
    plan = sp._template_plan(
        "基于检索增强生成的企业知识库问答系统研究",
        {
            "method": ["retrieval-augmented generation"],
            "object": ["knowledge base"],
            "task": ["question answering"],
            "scenario": ["enterprise deployment"],
            "domain": "unknown",
            "dataset_terms": [],
            "baseline_terms": ["retrieval-augmented generation"],
            "avoid_terms": [],
        },
    )

    queries = [item["query"].lower() for item in plan["queries"]]
    assert any("retrieval-augmented generation" in query for query in queries)
    assert any("knowledge base question answering" in query for query in queries)
    assert all(len(query.split()) <= 8 or "retrieval-augmented generation enterprise knowledge base question answering" == query for query in queries)

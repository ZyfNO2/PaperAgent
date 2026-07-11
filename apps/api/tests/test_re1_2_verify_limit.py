from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apps.api.app.services.agents.graph.nodes import verify as verify_node


def test_verify_node_respects_max_verify_candidates(monkeypatch) -> None:
    called = {}

    def fake_call_verifier(topic, atoms, candidates):  # type: ignore[no-untyped-def]
        called["n"] = len(candidates)
        return [], {"total_input": len(candidates), "total_resolved": 0, "coverage": 0.0,
                    "unresolved_ids": [], "invalid_ids": [], "raw_lengths": [],
                    "parse_stages": [], "batch_results": [], "provider": "", "model": ""}

    monkeypatch.setattr(verify_node, "_call_verifier", fake_call_verifier)
    verify_node.verify_node(
        {
            "topic": "test topic",
            "topic_atoms": {},
            "paper_candidates": [{"title": f"paper-{i}"} for i in range(10)],
            "user_constraints": {"max_verify_candidates": 3},
            "trace_events": [],
            "errors": [],
        },
    )

    assert called["n"] == 3

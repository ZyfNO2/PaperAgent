"""Re1.1 dataset/repo-extraction audit — require found or not_found_in_paper,
never fabricated URL.

SOP §8.2 / §9.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import apps.api.app.services.llm_router as llm_router


def _install_fake_llm(monkeypatch, payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Patch llm_router.call_json; returns a call log."""
    log: list[dict[str, Any]] = []

    def fake(prompt, **kwargs):  # type: ignore[no-untyped-def]
        log.append({"prompt": prompt, **kwargs})
        return payload

    monkeypatch.setattr(llm_router, "call_json", fake)
    return log


def test_dataset_reports_found_when_paper_gives_data(monkeypatch) -> None:
    from apps.api.app.services.agents.graph.nodes import content as content_mod

    _install_fake_llm(monkeypatch, {
        "dataset_name": "NEU-DET",
        "official_code_url": "https://github.com/official/steel-defect",
        "status": "found",
        "paper_mentioned_repo": None,
        "paper_used_base": ["YOLOv5"],
        "missing": [],
    })

    state = {
        "case_id": "c1",
        "verified_papers": [
            {"title": "Steel Defect Detection via YOLOv5",
             "verdict": "accept",
             "source_type": "paper", "relation_to_topic": "baseline"},
        ],
        "trace_events": [],
    }
    out = content_mod.dataset_repo_node(state)
    assert any(d.get("from_paper") == "Steel Defect Detection via YOLOv5"
               for d in out["dataset_candidates"]), out
    assert any(r.get("url") == "https://github.com/official/steel-defect"
               for r in out["repo_candidates"]), out


def test_dataset_reports_notfound_when_paper_blank(monkeypatch) -> None:
    """SOP §8.2: must not fabricate URL when paper has none."""
    from apps.api.app.services.agents.graph.nodes import content as content_mod

    _install_fake_llm(monkeypatch, {
        "dataset_name": None, "official_code_url": None,
        "status": "not_found_in_paper",
        "missing": [],
    })

    state = {
        "case_id": "c2",
        "verified_papers": [
            {"title": "A survey of generic ML (no dataset)",
             "source_type": "paper", "relation_to_topic": "survey"},
        ],
        "trace_events": [],
    }
    out = content_mod.dataset_repo_node(state)
    # No concrete dataset/repo surface.
    assert out["dataset_candidates"] == [
        {"from_paper": "A survey of generic ML (no dataset)",
         "status": "not_found_in_paper"}
    ]
    # Critically: no fabricated URL.
    for r in out["repo_candidates"]:
        assert "http" not in str(r.get("url")) or r.get("status") == "found"


def test_dataset_node_caps_llm_calls(monkeypatch) -> None:
    """Even with 20 papers, LLM calls are capped to keep Re1.1 loop <120s."""
    from apps.api.app.services.agents.graph.nodes import content as content_mod

    log = _install_fake_llm(monkeypatch, {"status": "not_found_in_paper",
                                           "missing": []})
    state = {
        "case_id": "c3",
        "verified_papers": [
            {"title": f"Paper {i}", "source_type": "paper"} for i in range(20)
        ],
        "trace_events": [],
    }
    content_mod.dataset_repo_node(state)
    assert len(log) <= 8, f"too many LLM calls: {len(log)}"

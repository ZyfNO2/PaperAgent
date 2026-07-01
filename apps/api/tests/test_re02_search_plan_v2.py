"""Re02 search-plan v2 tests (apps/api/app/services/agents/research_agent.plan_tools_v2).

Covers:
1. always returns 3 rounds
2. each call has tool/query/target_role/why_call/expected_output keys
3. round 1 arxiv call, round 3 github call
4. github queries <= 4 words
5. legacy keys (arxiv_queries/github_queries) populated
6. deterministic fallback path works when LLM budget is 0
"""

from __future__ import annotations

import pytest

from app.services.agents.research_agent import (
    plan_tools_v2,
    reset_counter,
)


pytestmark = pytest.mark.re02


@pytest.fixture(autouse=True)
def _reset():
    reset_counter()
    yield
    reset_counter()


def _topic_json() -> dict:
    return {
        "raw_topic": "Underwater acoustic signal classification with deep learning",
        "query_atoms_en": [
            "underwater acoustic classification",
            "spectrogram CNN",
            "deep learning",
        ],
    }


def test_plan_tools_v2_returns_three_rounds():
    plan = plan_tools_v2(_topic_json())
    assert "rounds" in plan
    assert len(plan["rounds"]) == 3


def test_plan_tools_v2_each_call_has_required_keys():
    plan = plan_tools_v2(_topic_json())
    for r in plan["rounds"]:
        for call in r.get("calls") or []:
            assert {"tool", "query", "target_role", "why_call", "expected_output"} <= set(call.keys())


def test_plan_tools_v2_round1_has_arxiv_and_round3_has_github():
    plan = plan_tools_v2(_topic_json())
    r1 = plan["rounds"][0]["calls"]
    r3 = plan["rounds"][2]["calls"]
    assert any(c["tool"] == "search_arxiv" for c in r1)
    assert any(c["tool"] == "search_github" for c in r3)


def test_plan_tools_v2_github_queries_capped_to_four_words():
    plan = plan_tools_v2(_topic_json())
    for q in plan.get("github_queries") or []:
        assert len(q.split()) <= 4, f"github query too long: {q!r}"


def test_plan_tools_v2_legacy_keys_are_populated():
    plan = plan_tools_v2(_topic_json())
    assert "arxiv_queries" in plan and len(plan["arxiv_queries"]) >= 1
    assert "github_queries" in plan and len(plan["github_queries"]) >= 1


def test_plan_tools_v2_falls_back_to_atoms_when_llm_budget_zero(monkeypatch):
    import os
    monkeypatch.setenv("SESSION66_LLM_BUDGET", "0")
    plan = plan_tools_v2(_topic_json())
    assert len(plan["rounds"]) == 3
    names = [r["name"] for r in plan["rounds"]]
    assert names == ["broad_recall", "reference_expansion", "repo_dataset_followup"]
    monkeypatch.delenv("SESSION66_LLM_BUDGET", raising=False)

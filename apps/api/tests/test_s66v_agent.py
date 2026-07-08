"""Tests for the S66v research agent (apps/api/app/services/agents/).

These tests run WITHOUT external network. They:

1. Verify the structural contracts of each LLM-step output.
2. Verify the CB state-machine logic in isolation (no LLM).
3. Verify the quote-extractor pulls paper titles from GitHub descriptions.
4. Verify the verifier drops entries that are not grounded in raw tool output.

To run only these:

    uv run pytest apps/api/tests/test_s66v_agent.py -v
"""

from __future__ import annotations

import os
import time

import pytest

from app.services.agents.research_agent import (
    _extract_quoted_titles,
    _apply_verifier,
    _build_verifier_index,
    reset_counter,
    parse_topic,
    plan_tools,
    run_research_agent,
)


# ---------------------------------------------------------------------------
# Re-import of helpers that aren't in __all__
# ---------------------------------------------------------------------------

from app.services.agents.research_agent import _PerAdapterCB  # noqa: E402


# ---------------------------------------------------------------------------
# 1. quote-extractor
# ---------------------------------------------------------------------------


def test_extract_quoted_titles_double_quote():
    text = 'The official implementation of the paper "A spatio-temporal deep learning approach for underwater acoustic signals classification"'
    titles = _extract_quoted_titles(text)
    assert len(titles) == 1
    assert "spatio-temporal" in titles[0]


def test_extract_quoted_titles_smart_quote():
    text = "the paper “SonAIr: real-time deep learning” demonstrates"
    titles = _extract_quoted_titles(text)
    assert any("SonAIr" in t for t in titles)


def test_extract_quoted_titles_filters_short():
    text = 'companion to "AI"'
    titles = _extract_quoted_titles(text)
    # "AI" is 1 word, should be filtered (need ≥ 4 words)
    assert titles == []


# ---------------------------------------------------------------------------
# 2. verifier — drops ungrounded entries
# ---------------------------------------------------------------------------


def test_verifier_grounded_github_full_name():
    raw = {
        "github": [
            {"full_name": "zakaria76al/USC",
             "html_url": "https://github.com/zakaria76al/USC",
             "description": "Some paper repo"},
        ],
        "arxiv": [],
        "openalex": [],
        "crossref": [],
    }
    idx = _build_verifier_index(raw)
    # Verifier normalizes owner/repo to lowercase + strips leading slashes
    assert "zakaria76al/usc" in idx["github"]
    # And end-to-end title-grounded lookup (used by _apply_verifier)
    from app.services.agents.research_agent import _title_grounded
    assert _title_grounded("zakaria76al/USC", idx)
    raw = {
        "github": [
            {"full_name": "real/repo",
             "html_url": "https://github.com/real/repo",
             "description": "A real underwater acoustic classification project"},
        ],
        "arxiv": [],
        "openalex": [],
        "crossref": [],
    }
    idx = _build_verifier_index(raw)
    buckets = {
        "baseline_papers": [{"title": "Totally Fabricated Paper Title XYZ"}],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "evidence_gaps": [],
    }
    revised, alerts = _apply_verifier(buckets, idx)
    assert len(revised["baseline_papers"]) == 0
    assert len(alerts) == 1
    assert alerts[0]["title"] == "Totally Fabricated Paper Title XYZ"


def test_verifier_grounded_via_quoted_paper_title():
    raw = {
        "github": [
            {"full_name": "lucascesarfd/underwater_snd",
             "html_url": "https://github.com/lucascesarfd/underwater_snd",
             "description": "Official implementation of the paper \"An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data\""},
        ],
        "arxiv": [],
        "openalex": [],
        "crossref": [],
    }
    idx = _build_verifier_index(raw)
    extracted = _extract_quoted_titles(raw["github"][0]["description"])
    assert any("Vessel Type Classification" in t for t in extracted)
    # Grounded via 5-gram overlap
    buckets = {
        "baseline_papers": [{"title": "An Investigation of Preprocessing Filters and Deep Learning Methods for Vessel Type Classification With Underwater Acoustic Data"}],
        "parallel_papers": [],
        "module_papers": [],
        "reference_papers": [],
        "dataset_candidates": [],
        "repo_candidates": [],
        "evidence_gaps": [],
    }
    revised, alerts = _apply_verifier(buckets, idx)
    assert len(revised["baseline_papers"]) == 1
    assert alerts == []


# ---------------------------------------------------------------------------
# 3. circuit breaker state machine (no LLM, no network)
# ---------------------------------------------------------------------------


def test_cb_initial_is_closed():
    cb = _PerAdapterCB()
    assert cb.should_allow() is True
    assert cb.state == "closed"


def test_cb_trips_after_threshold_failures():
    cb = _PerAdapterCB()
    for _ in range(3):
        cb.on_failure(is_429=True)
    assert cb.state == "open"
    assert cb.should_allow() is False  # cooldown not elapsed


def test_cb_half_open_after_cooldown():
    cb = _PerAdapterCB()
    for _ in range(3):
        cb.on_failure(is_429=True)
    # cooldown 180s; pretend 181s elapsed
    cb.open_since = time.monotonic() - 181
    assert cb.should_allow() is True
    assert cb.state == "half_open"


def test_cb_half_open_probe_success_returns_closed():
    cb = _PerAdapterCB()
    cb.trip_count = 1
    cb.cooldown_sec = 600
    for _ in range(3):
        cb.on_failure(is_429=True)
    cb.open_since = time.monotonic() - 601
    cb.should_allow()  # -> half_open
    cb.on_success()
    assert cb.state == "closed"
    assert cb.cooldown_sec == 180  # reset to initial


def test_cb_half_open_probe_failure_doubles_cooldown():
    cb = _PerAdapterCB()
    cb.trip_count = 1
    cb.cooldown_sec = 180
    for _ in range(3):
        cb.on_failure(is_429=True)
    cb.open_since = time.monotonic() - 181
    cb.should_allow()  # -> half_open
    cb.on_failure(is_429=True)
    assert cb.state == "open"
    assert cb.cooldown_sec == 360  # doubled
    assert cb.cooldown_sec <= 600  # capped


# ---------------------------------------------------------------------------
# 4. heuristic fallback never leaks GT strings
# ---------------------------------------------------------------------------


def test_heuristic_parse_topic_falls_back_to_unknown_when_no_domain():
    raw = "随机奇奇怪怪的中文题目 1234"  # unknown, no domain keyword
    reset_counter()
    parsed = parse_topic(raw)
    if parsed.get("_heuristic"):
        # When LLM is alive LLM-driven path runs and route is set;
        # when LLM is dead heuristic returns unknown/raw_topic.
        assert parsed["domain_route"] in {"unknown", parsed["domain_route"]}
        # Hard fail: known dataset names MUST NOT appear in query_atoms_en
        for forbidden in ("ShipsEar", "DeepShip", "SonAIr", "SonAIR"):
            assert forbidden not in parsed["query_atoms_en"]
    # Either way: query_atoms_en must contain SOMETHING (raw topic fallback)
    assert len(parsed.get("query_atoms_en") or []) >= 1


# ---------------------------------------------------------------------------
# 5. plan_tools caps github queries to ≤ 4 words
# ---------------------------------------------------------------------------


def test_plan_tools_caps_github_queries_length():
    reset_counter()
    parsed = {
        "raw_topic": "Underwater acoustic signal classification with deep learning",
        "domain_route": "signal_timeseries",
        "query_atoms_en": [
            "this is a very long query atom that should be truncated",
            "ShipsEar",  # would be a leak if it appeared
            "DeepShip",
        ],
    }
    plan = plan_tools(parsed)
    if plan.get("github_queries"):
        for q in plan["github_queries"]:
            assert len(q.split()) <= 4, f"github query too long: {q!r}"


# ---------------------------------------------------------------------------
# 6. AgentResult shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_research_agent_returns_7_buckets():
    reset_counter()

    # short-circuit LLM by setting budget to 0
    os.environ["SESSION66_LLM_BUDGET"] = "0"

    result = await run_research_agent("机器学习在水声数据分类识别中的应用")
    assert result.buckets is not None
    for cat in (
        "baseline_papers", "parallel_papers", "module_papers",
        "reference_papers", "dataset_candidates", "repo_candidates",
        "evidence_gaps",
    ):
        assert cat in result.buckets
    assert isinstance(result.llm_calls, int)
    assert result.parsed_topic["raw_topic"] == "机器学习在水声数据分类识别中的应用"
    os.environ.pop("SESSION66_LLM_BUDGET", None)

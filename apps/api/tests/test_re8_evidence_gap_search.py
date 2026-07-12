"""Re8.0 WP4 Evidence Gap Driven Search Tests.

Tests that:
- search_planner produces gap-bound queries from Search Lanes
- search_agent records evidence_delta per gap
- early exit fires when all gaps are resolved
- 0 results mark gaps as unresolved
- the trace can answer "why did we search and what changed"

WP4 acceptance: "trace 能回答每次'为什么搜、结果改变了什么'"
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.api.app.services.agents.graph.nodes.search_agent import (
    _build_gap_lookup,
    _check_gap_resolved,
    search_agent_node,
)
from apps.api.app.services.agents.graph.nodes.search_planner import (
    _create_lane_gaps,
    _seeded_plan,
    search_planner_node,
)
from apps.api.app.services.agents.graph.re80_schema import (
    make_evidence_gap,
    make_seed_card,
    validate_evidence_gap,
)

PATCH_CATALOG = "apps.api.app.services.search_catalog.get_source_catalog"
PATCH_RUN_TOOL = "apps.api.app.services.agents.graph.nodes.search_agent._run_tool_sync"
PATCH_LLM_DECIDE = "apps.api.app.services.agents.graph.nodes.search_agent._llm_decide"


def _make_decide_fn(decisions: list[dict[str, Any]]):
    """Build a side_effect for _llm_decide that returns decisions in order,
    then returns 'stop' indefinitely to prevent StopIteration crashes."""
    decision_iter = iter(decisions)

    def _decide(*a, **k):
        try:
            return (next(decision_iter), "fast_json")
        except StopIteration:
            return ({"action": "stop", "reason": "exhausted"}, "fast_json")

    return _decide


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_catalog() -> MagicMock:
    catalog = MagicMock()
    catalog.allowed_source_names.return_value = [
        "arxiv", "openalex", "crossref", "github",
        "semantic_scholar", "huggingface",
    ]
    catalog.source_list_for_prompt.return_value = "- arxiv: arXiv\n- openalex: OpenAlex"
    catalog.is_available.return_value = True
    return catalog


def _make_lanes(seed_id: str = "s1") -> list[dict[str, Any]]:
    """Build five Search Lanes like WP3 would produce."""
    return [
        {
            "lane_id": "anchor_reference",
            "description": "Find the origin paper",
            "queries": ["YOLO original paper", "you only look once citation"],
            "gap_id": None,
        },
        {
            "lane_id": "competing_baseline",
            "description": "Same-task baselines",
            "queries": ["Faster R-CNN detection", "recent detection methods benchmark"],
            "gap_id": None,
        },
        {
            "lane_id": "mechanism_module",
            "description": "Mechanism modules",
            "queries": ["small object detection module"],
            "gap_id": None,
        },
        {
            "lane_id": "resource",
            "description": "Repos and datasets",
            "queries": ["YOLO github repository"],
            "gap_id": None,
        },
        {
            "lane_id": "counter_evidence",
            "description": "Counter-evidence",
            "queries": ["YOLO failure cases small objects"],
            "gap_id": None,
        },
    ]


def _make_gap_bound_plan(seed_id: str = "s1") -> dict[str, Any]:
    """Build a gap-bound search_plan like _seeded_plan would produce."""
    lanes = _make_lanes(seed_id)
    updated_lanes, _ = _create_lane_gaps(lanes, seed_id)
    return _seeded_plan(updated_lanes, seed_id)


# ---------------------------------------------------------------------------
# _create_lane_gaps
# ---------------------------------------------------------------------------

class TestCreateLaneGaps:
    def test_creates_gaps_for_all_five_lanes(self):
        lanes = _make_lanes()
        updated, new_gaps = _create_lane_gaps(lanes, seed_id="s1")
        assert len(new_gaps) == 5
        assert all(g["gap_id"].startswith("gap-s1-") for g in new_gaps)

    def test_updated_lanes_have_gap_ids(self):
        lanes = _make_lanes()
        updated, _ = _create_lane_gaps(lanes, seed_id="s1")
        for lane in updated:
            assert lane["gap_id"] is not None
            assert lane["gap_id"].startswith("gap-s1-")

    def test_preserves_existing_gap_ids(self):
        lanes = _make_lanes()
        lanes[0]["gap_id"] = "custom-gap-001"
        updated, new_gaps = _create_lane_gaps(lanes, seed_id="s1")
        assert updated[0]["gap_id"] == "custom-gap-001"
        # Only 4 new gaps (the one with existing gap_id is skipped)
        assert len(new_gaps) == 4

    def test_gaps_validate_against_schema(self):
        lanes = _make_lanes()
        _, new_gaps = _create_lane_gaps(lanes, seed_id="s1")
        for gap in new_gaps:
            assert validate_evidence_gap(gap) == [], f"gap {gap['gap_id']} invalid"

    def test_gap_types_match_lane(self):
        lanes = _make_lanes()
        _, new_gaps = _create_lane_gaps(lanes, seed_id="s1")
        gap_by_lane = {g["gap_id"].replace("gap-s1-", ""): g for g in new_gaps}
        assert gap_by_lane["anchor_reference"]["gap_type"] == "existence"
        assert gap_by_lane["competing_baseline"]["gap_type"] == "competing_method"
        assert gap_by_lane["mechanism_module"]["gap_type"] == "mechanism"
        assert gap_by_lane["resource"]["gap_type"] == "repo"
        assert gap_by_lane["counter_evidence"]["gap_type"] == "counter_evidence"


# ---------------------------------------------------------------------------
# _seeded_plan
# ---------------------------------------------------------------------------

class TestSeededPlan:
    def test_produces_gap_bound_flag(self):
        plan = _make_gap_bound_plan()
        assert plan.get("gap_bound") is True

    def test_each_query_has_gap_id(self):
        plan = _make_gap_bound_plan()
        for q in plan["queries"]:
            assert "gap_id" in q and q["gap_id"]
            assert "success_condition" in q and q["success_condition"]
            assert "lane_id" in q and q["lane_id"]

    def test_queries_capped_at_12(self):
        plan = _make_gap_bound_plan()
        assert len(plan["queries"]) <= 12

    def test_unknown_lane_skipped(self):
        lanes = [{"lane_id": "bogus_lane", "queries": ["test"], "gap_id": None}]
        plan = _seeded_plan(lanes, seed_id="s1")
        assert len(plan["queries"]) == 0

    def test_dedupes_repeated_queries(self):
        lanes = [
            {
                "lane_id": "anchor_reference",
                "description": "d",
                "queries": ["same query", "same query", "same query"],
                "gap_id": "gap-s1-anchor_reference",
            },
        ]
        plan = _seeded_plan(lanes, seed_id="s1")
        # openalex + crossref = 2 entries (one per tool), not 6
        assert len(plan["queries"]) == 2

    def test_rounds_include_broad_and_focused(self):
        plan = _make_gap_bound_plan()
        assert "broad" in plan["rounds"]
        assert "focused" in plan["rounds"]


# ---------------------------------------------------------------------------
# _build_gap_lookup
# ---------------------------------------------------------------------------

class TestBuildGapLookup:
    def test_builds_lookup_from_gap_bound_plan(self):
        plan = _make_gap_bound_plan()
        lookup = _build_gap_lookup(plan)
        assert len(lookup) > 0
        for (tool, query), meta in lookup.items():
            assert "gap_id" in meta
            assert "success_condition" in meta
            assert "lane_id" in meta

    def test_ignores_non_gap_queries(self):
        plan = {
            "queries": [
                {"tool": "arxiv", "query": "no gap", "why": ""},
                {"tool": "arxiv", "query": "with gap", "gap_id": "g1",
                 "success_condition": "find 1+", "lane_id": "anchor"},
            ],
        }
        lookup = _build_gap_lookup(plan)
        assert len(lookup) == 1
        assert ("arxiv", "with gap") in lookup
        assert ("arxiv", "no gap") not in lookup

    def test_empty_plan_returns_empty(self):
        assert _build_gap_lookup({}) == {}
        assert _build_gap_lookup({"queries": []}) == {}


# ---------------------------------------------------------------------------
# _check_gap_resolved
# ---------------------------------------------------------------------------

class TestCheckGapResolved:
    def test_find_1_plus_papers_resolved(self):
        assert _check_gap_resolved("find 1+ origin paper", 1, 0) is True

    def test_find_1_plus_papers_not_resolved(self):
        assert _check_gap_resolved("find 1+ origin paper", 0, 0) is False

    def test_find_2_plus_papers_resolved(self):
        assert _check_gap_resolved("find 2+ competing baseline papers", 2, 0) is True

    def test_find_2_plus_papers_not_resolved(self):
        assert _check_gap_resolved("find 2+ competing baseline papers", 1, 0) is False

    def test_find_1_plus_repo_resolved(self):
        assert _check_gap_resolved("find 1+ repo or dataset", 0, 1) is True

    def test_find_1_plus_repo_not_resolved(self):
        assert _check_gap_resolved("find 1+ repo or dataset", 5, 0) is False

    def test_empty_condition_defaults_to_1_paper(self):
        assert _check_gap_resolved("", 1, 0) is True
        assert _check_gap_resolved("", 0, 0) is False

    def test_unparsed_condition_defaults_to_1_paper(self):
        assert _check_gap_resolved("some weird condition", 1, 0) is True


# ---------------------------------------------------------------------------
# search_planner_node — seeded_research path
# ---------------------------------------------------------------------------

class TestSearchPlannerSeededPath:
    def test_seeded_research_produces_gap_bound_plan(self):
        lanes = _make_lanes()
        state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": lanes,
            "seed_cards": [make_seed_card(seed_id="s1", task_definition="detection")],
            "topic": "object detection",
            "topic_atoms": {},
        }
        result = search_planner_node(state)
        plan = result["search_plan"]
        assert plan.get("gap_bound") is True
        assert len(plan["queries"]) > 0
        for q in plan["queries"]:
            assert q.get("gap_id"), f"query missing gap_id: {q}"

    def test_topic_only_does_not_use_gap_bound(self):
        state: dict[str, Any] = {
            "entry_mode": "topic_only",
            "search_lanes": [],
            "topic": "object detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"]},
        }
        result = search_planner_node(state)
        plan = result["search_plan"]
        assert plan.get("gap_bound") is not True

    def test_seeded_research_emits_new_gaps(self):
        lanes = _make_lanes()
        state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": lanes,
            "seed_cards": [make_seed_card(seed_id="s1", task_definition="detection")],
            "topic": "detection",
            "topic_atoms": {},
        }
        result = search_planner_node(state)
        assert "evidence_gaps" in result
        assert len(result["evidence_gaps"]) == 5

    def test_seeded_research_updates_lanes_with_gap_ids(self):
        lanes = _make_lanes()
        state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": lanes,
            "seed_cards": [make_seed_card(seed_id="s1", task_definition="detection")],
            "topic": "detection",
            "topic_atoms": {},
        }
        result = search_planner_node(state)
        assert "search_lanes" in result
        updated = result["search_lanes"]
        for lane in updated:
            assert lane["gap_id"] is not None

    def test_seeded_research_trace_has_gap_bound_flag(self):
        lanes = _make_lanes()
        state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": lanes,
            "seed_cards": [make_seed_card(seed_id="s1")],
            "topic": "detection",
            "topic_atoms": {},
        }
        result = search_planner_node(state)
        trace = result["trace_events"][0]
        assert trace["output_summary"]["gap_bound"] is True
        assert trace["output_summary"]["n_new_gaps"] == 5

    def test_no_search_lanes_falls_through_to_template(self):
        """seeded_research but no lanes → uses template/LLM path."""
        state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": [],
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"]},
        }
        result = search_planner_node(state)
        plan = result["search_plan"]
        # Template plan does NOT have gap_bound
        assert "gap_bound" not in plan or plan["gap_bound"] is not True


# ---------------------------------------------------------------------------
# search_agent_node — gap tracking
# ---------------------------------------------------------------------------

class TestSearchAgentGapTracking:
    def test_gap_bound_step_records_evidence_delta(self, monkeypatch):
        """When a gap-bound query is executed, the step must include
        evidence_delta with n_new_papers and gap_resolved."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        plan = _make_gap_bound_plan()
        # Pick the first gap-bound query to execute
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "gap bound"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "object detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "Paper 1", "abstract": "abs"}]):
            result = search_agent_node(state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        assert len(tool_steps) >= 1
        step = tool_steps[0]
        assert "gap_id" in step
        assert "evidence_delta" in step
        assert step["evidence_delta"]["n_new_papers"] >= 1
        assert step["evidence_delta"]["gap_resolved"] is True

    def test_non_gap_bound_plan_no_evidence_delta(self, monkeypatch):
        """Non-gap-bound plans (topic_only) must not add evidence_delta."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        decisions = [
            {"action": "search", "tool": "arxiv", "query": "YOLO", "reason": "go"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": {
                "queries": [
                    {"tool": "arxiv", "query": "YOLO", "why": "test",
                     "expected_evidence": "papers", "stop_condition": "n>=5"},
                ],
                "rounds": ["broad"],
            },
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "P", "abstract": "a"}]):
            result = search_agent_node(state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        assert len(tool_steps) >= 1
        assert "evidence_delta" not in tool_steps[0]
        assert "gap_id" not in tool_steps[0]

    def test_zero_results_marks_gap_unresolved(self, monkeypatch):
        """When a gap-bound query returns 0 results, the gap is unresolved."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        plan = _make_gap_bound_plan()
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "gap"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[]):  # 0 results
            result = search_agent_node(state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        assert len(tool_steps) >= 1
        step = tool_steps[0]
        assert step["evidence_delta"]["gap_resolved"] is False
        assert step["evidence_delta"]["n_new_papers"] == 0

        # Trace gap_resolution should show unresolved gaps
        trace = result["trace_events"][0]
        gap_res = trace["output_summary"].get("gap_resolution", {})
        assert gap_res.get("n_unresolved", 0) >= 1

    def test_trace_has_gap_resolution_summary(self, monkeypatch):
        """The trace output_summary must include gap_resolution for
        gap-bound plans."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        plan = _make_gap_bound_plan()
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "gap"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "P", "abstract": "a"}]):
            result = search_agent_node(state)

        trace = result["trace_events"][0]
        assert "gap_resolution" in trace["output_summary"]
        gr = trace["output_summary"]["gap_resolution"]
        assert gr["gap_bound"] is True
        assert gr["n_bound_gaps"] > 0
        assert "resolved_gap_ids" in gr
        assert "unresolved_gap_ids" in gr

    def test_partial_results_counted_as_unresolved(self, monkeypatch):
        """P2-1 regression: a gap with partial results (n>0 but below
        threshold) must appear in unresolved_gap_ids, not vanish.

        competing_baseline needs 2+ papers. We return only 1, so the
        gap should be unresolved in the trace summary.
        """
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        # Build plan with only competing_baseline (needs 2+ papers)
        lanes = [
            {
                "lane_id": "competing_baseline",
                "description": "baselines",
                "queries": ["Faster R-CNN detection"],
                "gap_id": None,
            },
        ]
        updated_lanes, _ = _create_lane_gaps(lanes, seed_id="s1")
        plan = _seeded_plan(updated_lanes, seed_id="s1")
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "partial"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "Only 1 paper", "abstract": "a"}]):
            result = search_agent_node(state)

        trace = result["trace_events"][0]
        gr = trace["output_summary"]["gap_resolution"]
        # The gap needs 2+ papers but only got 1 → unresolved
        assert gr["n_resolved"] == 0
        assert gr["n_unresolved"] == gr["n_bound_gaps"]
        # Invariant: n_resolved + n_unresolved == n_bound_gaps
        assert gr["n_resolved"] + gr["n_unresolved"] == gr["n_bound_gaps"]


# ---------------------------------------------------------------------------
# WP4 acceptance: trace answers "why search + what changed"
# ---------------------------------------------------------------------------

class TestWP4Acceptance:
    def test_trace_answers_why_and_what_changed(self, monkeypatch):
        """WP4 acceptance: trace can answer each 'why did we search'
        and 'what did the results change'.

        For every tool_call step, there must be:
        - a 'reason' (why we searched)
        - an 'evidence_delta' (what the results changed)
        - a 'gap_id' (which gap this search was motivated by)
        """
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        plan = _make_gap_bound_plan()
        # Execute first 2 gap-bound queries, then stop
        q0 = plan["queries"][0]
        q1 = plan["queries"][1]
        decisions = [
            {"action": "search", "tool": q0["tool"], "query": q0["query"], "reason": "gap: anchor"},
            {"action": "search", "tool": q1["tool"], "query": q1["query"], "reason": "gap: baseline"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "P", "abstract": "a"}]):
            result = search_agent_node(state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        assert len(tool_steps) >= 2

        for step in tool_steps:
            # "why did we search" → reason + gap_id + lane_id
            assert step.get("reason"), f"step {step.get('step')} missing reason"
            assert step.get("gap_id"), f"step {step.get('step')} missing gap_id"
            assert step.get("lane_id"), f"step {step.get('step')} missing lane_id"
            # "what changed" → evidence_delta
            delta = step.get("evidence_delta")
            assert delta is not None, f"step {step.get('step')} missing evidence_delta"
            assert "n_new_papers" in delta
            assert "gap_resolved" in delta

        # The trace summary must include gap_resolution
        trace = result["trace_events"][0]
        assert "gap_resolution" in trace["output_summary"]

    def test_resource_lane_checks_repos_not_papers(self, monkeypatch):
        """The resource lane's success_condition checks repos, not papers.
        A github search returning 0 papers but 1 repo should resolve."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        # Build a plan with only the resource lane
        lanes = [
            {
                "lane_id": "resource",
                "description": "repos",
                "queries": ["YOLO github"],
                "gap_id": None,
            },
        ]
        updated_lanes, _ = _create_lane_gaps(lanes, seed_id="s1")
        plan = _seeded_plan(updated_lanes, seed_id="s1")
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "resource"},
            {"action": "stop", "reason": "done"},
        ]

        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        # github returns a repo (not a paper)
        def _fake_run_tool(tool, query, top_k=12):
            if tool == "github":
                return [{"full_name": "ultralytics/yolov5", "html_url": "https://github.com/ultralytics/yolov5"}]
            return []

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, side_effect=_fake_run_tool):
            result = search_agent_node(state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        github_step = next(s for s in tool_steps if s["tool"] == "github")
        assert github_step["evidence_delta"]["n_new_repos"] >= 1
        assert github_step["evidence_delta"]["gap_resolved"] is True


# ---------------------------------------------------------------------------
# Integration: planner → agent
# ---------------------------------------------------------------------------

class TestIntegrationPlannerToAgent:
    def test_planner_output_feeds_agent(self, monkeypatch):
        """End-to-end: search_planner produces a gap-bound plan, and
        search_agent uses it to record evidence_delta."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        # Step 1: planner produces gap-bound plan
        lanes = _make_lanes()
        planner_state: dict[str, Any] = {
            "entry_mode": "seeded_research",
            "search_lanes": lanes,
            "seed_cards": [make_seed_card(seed_id="s1", task_definition="detection")],
            "topic": "object detection",
            "topic_atoms": {},
        }
        planner_result = search_planner_node(planner_state)
        plan = planner_result["search_plan"]
        assert plan.get("gap_bound") is True

        # Step 2: agent uses the plan
        first_q = plan["queries"][0]
        decisions = [
            {"action": "search", "tool": first_q["tool"],
             "query": first_q["query"], "reason": "gap"},
            {"action": "stop", "reason": "done"},
        ]

        agent_state: dict[str, Any] = {
            "topic": "object detection",
            "topic_atoms": {"method": ["YOLO"], "object": ["detection"], "domain": "cv"},
            "search_plan": plan,
            "trace_events": [],
        }

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "P", "abstract": "a"}]):
            result = search_agent_node(agent_state)

        tool_steps = [s for s in result["search_steps"] if s.get("type") == "tool_call"]
        assert len(tool_steps) >= 1
        assert tool_steps[0].get("gap_id") == first_q["gap_id"]


# ---------------------------------------------------------------------------
# P1-7b: gap_lookup miss fallback (search_agent.py lines 1007-1025)
# ---------------------------------------------------------------------------

class TestP17bGapLookupMissFallback:
    """P1-7b: gap_lookup miss fallback.

    When the LLM-driven ReAct loop uses queries that don't exactly match
    the gap-bound plan queries (gap_lookup miss), step_entry won't carry
    gap_id and the per-gap partial_gaps set stays empty. In that case,
    if search_agent DID find papers/repos, mark all "open" gaps as
    "partially_satisfied".

    Covers search_agent.py lines 1007-1025:
        if not resolved_gaps and not partial_gaps and (paper_candidates or unique_repos):
            for gap in existing_gaps:
                gid = gap.get("gap_id", "")
                current_status = gap.get("status", "open")
                if gid and current_status == "open":
                    partial_gaps.add(gid)
    """

    def _make_state_with_open_gaps(
        self, *, n_gaps: int = 2, gap_status: str = "open",
    ) -> dict[str, Any]:
        """Build state with n gaps (default open) + gap-bound plan."""
        plan = _make_gap_bound_plan(seed_id="s1")
        gaps = [
            make_evidence_gap(
                gap_id=f"G-{gap_status}-{i}",
                question=f"q{i}",
                status=gap_status,
            )
            for i in range(n_gaps)
        ]
        return {
            "topic": "detection",
            "topic_atoms": {
                "method": ["YOLO"], "object": ["detection"], "domain": "cv",
            },
            "search_plan": plan,
            "trace_events": [],
            "evidence_gaps": gaps,
        }

    def test_p1_7b_gap_lookup_miss_with_papers_marks_partial(self, monkeypatch):
        """gap_lookup miss + paper_candidates 非空 → open gaps 被标记为 partially_satisfied."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        state = self._make_state_with_open_gaps(n_gaps=2, gap_status="open")
        # LLM uses a query NOT in the plan → gap_lookup miss
        decisions = [
            {"action": "search", "tool": "arxiv",
             "query": "TOTALLY DIFFERENT QUERY NOT IN PLAN",
             "reason": "llm reformulated"},
            {"action": "stop", "reason": "done"},
        ]

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "Paper One", "abstract": "a"}]):
            result = search_agent_node(state)

        # All open gaps should be marked partially_satisfied
        for gap in result["evidence_gaps"]:
            assert gap["status"] == "partially_satisfied", (
                f"gap {gap['gap_id']} status={gap['status']}"
            )
        # Sanity: papers were indeed found
        assert len(result["paper_candidates"]) >= 1

    def test_p1_7b_gap_lookup_miss_with_repos_only_triggers(self, monkeypatch):
        """gap_lookup miss + unique_repos 非空但 paper_candidates 为空 → fallback 触发."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        state = self._make_state_with_open_gaps(n_gaps=2, gap_status="open")
        # LLM uses github + a query NOT in plan → gap_lookup miss + repo result
        decisions = [
            {"action": "search", "tool": "github",
             "query": "TOTALLY DIFFERENT REPO QUERY NOT IN PLAN",
             "reason": "llm reformulated"},
            {"action": "stop", "reason": "done"},
        ]

        def _fake_run_tool(tool, query, top_k=12):
            if tool == "github":
                return [{
                    "full_name": "owner/repo",
                    "html_url": "https://github.com/owner/repo",
                }]
            return []

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, side_effect=_fake_run_tool):
            result = search_agent_node(state)

        for gap in result["evidence_gaps"]:
            assert gap["status"] == "partially_satisfied", (
                f"gap {gap['gap_id']} status={gap['status']}"
            )
        # paper_candidates empty, repo_candidates non-empty
        assert len(result["paper_candidates"]) == 0
        assert len(result["repo_candidates"]) >= 1

    def test_p1_7b_empty_existing_gaps_safe_skip(self, monkeypatch):
        """gap_lookup miss + existing_gaps 为空 → fallback 安全跳过,不报错."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        plan = _make_gap_bound_plan(seed_id="s1")
        state: dict[str, Any] = {
            "topic": "detection",
            "topic_atoms": {
                "method": ["YOLO"], "object": ["detection"], "domain": "cv",
            },
            "search_plan": plan,
            "trace_events": [],
            "evidence_gaps": [],  # empty — fallback should skip safely
        }
        decisions = [
            {"action": "search", "tool": "arxiv",
             "query": "NOT IN PLAN", "reason": "go"},
            {"action": "stop", "reason": "done"},
        ]

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "Paper One", "abstract": "a"}]):
            result = search_agent_node(state)

        # No error, evidence_gaps still empty
        assert result["evidence_gaps"] == []
        # Sanity: papers were found (fallback condition met but no gaps to mark)
        assert len(result["paper_candidates"]) >= 1

    def test_p1_7b_no_open_gaps_no_change(self, monkeypatch):
        """gap_lookup miss + 所有 gap status 不是 "open" → 不标记任何 gap."""
        monkeypatch.setenv("SEARCH_AGENT_USE_UNIFIED_ROUTER", "0")
        state = self._make_state_with_open_gaps(n_gaps=2, gap_status="blocked")
        decisions = [
            {"action": "search", "tool": "arxiv",
             "query": "NOT IN PLAN", "reason": "go"},
            {"action": "stop", "reason": "done"},
        ]

        with patch(PATCH_CATALOG, return_value=_make_catalog()), \
             patch(PATCH_LLM_DECIDE, side_effect=_make_decide_fn(decisions)), \
             patch(PATCH_RUN_TOOL, return_value=[{"title": "Paper One", "abstract": "a"}]):
            result = search_agent_node(state)

        # Gaps should remain "blocked" (P1-7b only touches "open" gaps)
        for gap in result["evidence_gaps"]:
            assert gap["status"] == "blocked", (
                f"gap {gap['gap_id']} status={gap['status']} "
                f"(should remain blocked — P1-7b only marks open gaps)"
            )
        # Sanity: papers were found (fallback condition met but no open gaps)
        assert len(result["paper_candidates"]) >= 1

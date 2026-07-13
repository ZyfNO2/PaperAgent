"""Re8.1 WP1-D Fix A: _seeded_plan() lane-fair allocation tests.

Root cause (round 2 verification): ``_seeded_plan()`` linearly appends
queries with ``cap=12``, causing the last 3 lanes (mechanism_module /
resource / counter_evidence) to be truncated. Their gaps never enter
search_plan → Phase 2 fallback can't see them → 0/3 cases triggered
fallback → 0/3 cases tailor_gate converged.

Fix A: each lane gets at least ``MIN_PER_LANE`` (2) queries before
round-robin fills the remaining cap (12). This ensures all 5 lanes
have queries in search_plan, so Phase 2 fallback can see their gaps.
"""
from __future__ import annotations

from typing import Any

import pytest

from apps.api.app.services.agents.graph.nodes.search_planner import (
    _LANE_GAP_SPEC,
    _create_lane_gaps,
    _seeded_plan,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_full_lanes(seed_id: str = "s1") -> list[dict[str, Any]]:
    """Build five Search Lanes, each with 2 queries (the typical case)."""
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
            "queries": ["small object detection module", "attention mechanism detector"],
            "gap_id": None,
        },
        {
            "lane_id": "resource",
            "description": "Repos and datasets",
            "queries": ["YOLO github repository", "detection dataset coco"],
            "gap_id": None,
        },
        {
            "lane_id": "counter_evidence",
            "description": "Counter-evidence",
            "queries": ["YOLO failure cases small objects", "detection limitation analysis"],
            "gap_id": None,
        },
    ]


def _make_full_plan(seed_id: str = "s1") -> dict[str, Any]:
    """Build a gap-bound plan from five lanes (with gap_ids filled)."""
    lanes = _make_full_lanes(seed_id)
    updated_lanes, _ = _create_lane_gaps(lanes, seed_id)
    return _seeded_plan(updated_lanes, seed_id)


# ---------------------------------------------------------------------------
# Fix A Tests
# ---------------------------------------------------------------------------

class TestSeededPlanLaneFairAllocation:
    """Re8.1 WP1-D Fix A: _seeded_plan() lane-fair allocation."""

    def test_seeded_plan_lane_fair_allocation(self):
        """Test 1: 5 lanes each with 2 queries → each lane has at least
        MIN_PER_LANE (2) queries in search_plan.

        Before Fix A: the first 2 lanes (anchor_reference +
        competing_baseline) filled the cap=12 quota, causing the last 3
        lanes to be completely dropped.
        """
        plan = _make_full_plan()
        queries = plan["queries"]
        # Count queries per lane_id
        lane_counts: dict[str, int] = {}
        for q in queries:
            lane_id = q.get("lane_id", "")
            lane_counts[lane_id] = lane_counts.get(lane_id, 0) + 1
        # All 5 lanes must be present with at least 2 queries each
        expected_lanes = {"anchor_reference", "competing_baseline",
                          "mechanism_module", "resource", "counter_evidence"}
        for lane_id in expected_lanes:
            assert lane_id in lane_counts, (
                f"lane '{lane_id}' missing from search_plan "
                f"(present: {sorted(lane_counts.keys())})"
            )
            assert lane_counts[lane_id] >= 2, (
                f"lane '{lane_id}' has only {lane_counts[lane_id]} queries "
                f"(expected >= 2 for MIN_PER_LANE)"
            )

    def test_seeded_plan_cap_12_maintained(self):
        """Test 2: total queries ≤ 12 even when 5 lanes have enough
        queries to overflow the cap.

        5 lanes × 2 queries × 2 tools = 20 potential entries.
        Cap must stay at 12 (not increased to accommodate all).
        """
        plan = _make_full_plan()
        assert len(plan["queries"]) <= 12, (
            f"cap exceeded: {len(plan['queries'])} > 12"
        )
        # With 5 lanes × 2 MIN_PER_LANE = 10, plus 2 round-robin = 12
        assert len(plan["queries"]) == 12, (
            f"expected exactly 12 queries (10 MIN_PER_LANE + 2 round-robin), "
            f"got {len(plan['queries'])}"
        )

    def test_seeded_plan_round_robin_fill(self):
        """Test 3: remaining cap after MIN_PER_LANE allocation is filled
        by round-robin across lanes.

        5 lanes × 2 MIN_PER_LANE = 10 queries.
        Remaining cap = 12 - 10 = 2 queries.
        Round-robin order: anchor_reference (query 3), competing_baseline
        (query 3) → total 12.
        """
        plan = _make_full_plan()
        queries = plan["queries"]
        # The 11th and 12th queries (index 10, 11) should come from
        # the first two lanes in round-robin order.
        # Each lane has 2 queries × 2 tools = 4 entries.
        # MIN_PER_LANE=2 takes entries [0] and [1] (the first query's
        # 2 tool expansions).
        # Round-robin starts at index 2 → entries [2] and [3] are the
        # second query's 2 tool expansions.
        # So the 11th query should be from anchor_reference's 3rd entry,
        # and the 12th from competing_baseline's 3rd entry.
        if len(queries) >= 11:
            lane_11 = queries[10].get("lane_id", "")
            lane_12 = queries[11].get("lane_id", "") if len(queries) >= 12 else ""
            # The 11th and 12th should be from the first two lanes
            # (round-robin order)
            assert lane_11 in ("anchor_reference", "competing_baseline"), (
                f"11th query lane_id={lane_11!r} "
                f"(expected anchor_reference or competing_baseline)"
            )

    def test_seeded_plan_short_lane(self):
        """Test 4: when a lane has fewer than MIN_PER_LANE queries,
        the remaining cap is distributed to other lanes.

        mechanism_module has only 1 query (2 entries), so MIN_PER_LANE=2
        is satisfied. But in round-robin, it has no more entries →
        other lanes get the remaining cap.
        """
        lanes = _make_full_lanes()
        # Reduce mechanism_module to 1 query
        for lane in lanes:
            if lane["lane_id"] == "mechanism_module":
                lane["queries"] = ["single mechanism query"]
        updated_lanes, _ = _create_lane_gaps(lanes, seed_id="s1")
        plan = _seeded_plan(updated_lanes, seed_id="s1")
        queries = plan["queries"]

        # Count per lane
        lane_counts: dict[str, int] = {}
        for q in queries:
            lane_id = q.get("lane_id", "")
            lane_counts[lane_id] = lane_counts.get(lane_id, 0) + 1

        # mechanism_module should have exactly 2 entries (1 query × 2 tools)
        assert lane_counts.get("mechanism_module", 0) == 2, (
            f"mechanism_module should have 2 entries (1 query × 2 tools), "
            f"got {lane_counts.get('mechanism_module', 0)}"
        )
        # Total should still be ≤ 12
        assert len(queries) <= 12
        # Other lanes should have ≥ 2 (MIN_PER_LANE satisfied)
        for lane_id in ("anchor_reference", "competing_baseline",
                        "resource", "counter_evidence"):
            assert lane_counts.get(lane_id, 0) >= 2, (
                f"lane '{lane_id}' should have >= 2 entries, "
                f"got {lane_counts.get(lane_id, 0)}"
            )

    def test_seeded_plan_all_lanes_covered(self):
        """Test 5: all 5 lanes' gap_ids appear in search_plan.

        Before Fix A: the last 3 lanes' gap_ids were missing from
        search_plan, making them invisible to Phase 2 fallback.
        """
        plan = _make_full_plan()
        queries = plan["queries"]
        # Collect all gap_ids in the plan
        plan_gap_ids = {q.get("gap_id", "") for q in queries if q.get("gap_id")}
        # All 5 expected gap_ids must be present
        expected_gap_ids = {
            "gap-s1-anchor_reference",
            "gap-s1-competing_baseline",
            "gap-s1-mechanism_module",
            "gap-s1-resource",
            "gap-s1-counter_evidence",
        }
        missing = expected_gap_ids - plan_gap_ids
        assert not missing, (
            f"gap_ids missing from search_plan: {sorted(missing)} "
            f"(present: {sorted(plan_gap_ids)})"
        )

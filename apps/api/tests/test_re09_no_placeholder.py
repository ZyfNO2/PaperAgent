"""Re09 tests: gap_repair_planner placeholder leak, metadata_client dispatch,
and execute_repair_plan failure recording.  All tests run offline with
mocked adapters — no network, no API keys.
"""
from __future__ import annotations

import asyncio



# ---------------------------------------------------------------------------
# 1. GapRepairPlanner placeholder leak (SOP §4.4)
# ---------------------------------------------------------------------------


def test_no_placeholder_leak():
    """A rule_repair_plan with empty atoms must return an empty plan and
    surface a ``unrepairable_reason`` claim when wrapped via
    ``build_repair_plan``.
    """
    from app.services.agents.gap_repair_planner import (
        _PLACEHOLDER_RE, build_repair_plan, rule_repair_plan,
    )

    # Empty atoms -> every axis substitution renders the literal "X".
    # The placeholder filter must drop them.  No axis hint should ever
    # be emitted as "X something".
    plan, unmatched, dropped = rule_repair_plan(
        ["no_dataset_or_data_gap_note"], topic_atoms={},
    )
    assert plan == []
    assert "no_dataset_or_data_gap_note" in unmatched
    assert dropped, "placeholder filter should have recorded drops"

    # Verify no emitted query contains '{', '}', or a standalone X.
    for _gap, q in dropped:
        assert "{X" not in q  # never output "{X" token
        assert "{" not in q and "}" not in q
        # Note: "X" is intentionally rendered for slot completeness by
        # _build_query; the SUT's job is to filter these out so the
        # ``repair_plan`` never carries them forward.  Confirm here that
        # the leak was caught (the items landed in ``dropped``) rather
        # than the leak being silently emitted.
        assert _PLACEHOLDER_RE.search(q), (
            "drop set must contain placeholder text"
        )

    # build_repair_plan path
    out = build_repair_plan(
        gap_reasons=["no_dataset_or_data_gap_note"],
        topic_atoms={},
    )
    assert out["repair_plan"] == []
    reason = out.get("unrepairable_reason") or ""
    assert reason
    assert "no atom-coverage" in reason or "needs_clarification" in reason


def test_placeholder_leak_drops_unsubstituted_queries():
    """When only ``task`` has atoms but the template references ``{object}``,
    the ``{object}`` slot must NOT be left in the rendered query.
    """
    from app.services.agents.gap_repair_planner import (
        _build_query, rule_repair_plan,
    )

    rendered = _build_query(
        "{object} {scenario} dataset",
        {"task": [{"en": "detection"}], "object": [], "scenario": []},
    )
    assert "{" not in rendered and "}" not in rendered
    assert " X " in rendered or rendered.endswith(" X") or rendered.startswith("X ") or rendered == "X"

    plan, _unmatched, dropped = rule_repair_plan(
        ["scenario_axis_missing"],
        {"task": [{"en": "detection"}], "object": [], "scenario": []},
    )
    assert plan == []
    assert dropped, "all queries should be dropped because no atom coverage"


# ---------------------------------------------------------------------------
# 2. metadata_client dispatch (SOP §4.2)
# ---------------------------------------------------------------------------


def test_metadata_client_dispatch():
    """Five adapters must each receive the call with the right tool name."""
    from app.services.agents.candidate_verifier import verify_bucket_online

    seen: dict[str, list[tuple[str, str, int]]] = {}

    async def fake_client(adapter_name, query, top_k=3):
        seen.setdefault(adapter_name, []).append((query, adapter_name, top_k))
        return [{
            "title": "Probe Title " + adapter_name,
            "url": f"https://{adapter_name}.example/x",
        }]

    members = [
        {
            "candidate_id": f"c{i}",
            "title": f"T{i}",
            "abstract": "",
            "url": "https://example.com/x",
            "role": i,
        }
        for i in range(5)
    ]
    topic_atoms = {
        "task": [{"en": "detection"}],
        "object": [{"en": "thing"}],
        "method": [{"en": "deep learning"}],
        "scenario": [{"en": "outdoor"}],
    }

    out = asyncio.run(verify_bucket_online(
        "baseline", members, topic_atoms, metadata_client=fake_client,
    ))
    assert len(out) == len(members)
    # Each member has a generic title "T0..4", "<6 chars" — probe skipped.
    assert seen == {}, "short titles should skip probe to keep network bounded"

    # Now give each member a long, real-looking title so the probe runs.
    long_members = [
        {"candidate_id": f"L{i}",
         "title": "Concrete Pavement Crack Detection Using Deep Learning",
         "abstract": "",
         "url": "https://example.com/x"}
        for i in range(3)
    ]
    asyncio.run(verify_bucket_online(
        "baseline", long_members, topic_atoms, metadata_client=fake_client,
    ))
    # All three adapters (arxiv / openalex / crossref) called for each.
    assert set(seen.keys()) == {"arxiv", "openalex", "crossref"}
    for adapter in ("arxiv", "openalex", "crossref"):
        assert len(seen[adapter]) == 3


# ---------------------------------------------------------------------------
# 3. execute_repair_plan failure recording (SOP §4.3)
# ---------------------------------------------------------------------------


def test_execute_repair_plan_records_failures():
    """A retrieval_client that raises for one query must surface it
    under ``failed_queries`` and continue with the rest.
    """
    from app.services.agents.metadata_repair_executor import execute_repair_plan

    calls: list[tuple[str, str, int]] = []

    async def flaky(tool, query, top_k=3):
        calls.append((tool, query, top_k))
        if "boom" in query:
            raise RuntimeError("adapter 503")
        return [{
            "title": f"Hit {tool} {query}",
            "url": f"https://{tool}.example/hit",
            "abstract": "abstract body for verification rule layer",
        }]

    repair_plan = {
        "repair_plan": [
            {
                "gap": "no_dataset_or_data_gap_note",
                "target_role": "dataset",
                "queries": [
                    {"query": "ok arxiv", "tool": "arxiv"},
                    {"query": "boom arxiv", "tool": "arxiv"},
                    {"query": "ok openalex", "tool": "openalex"},
                ],
            }
        ],
        "unrepairable_reason": "",
    }

    result = asyncio.run(execute_repair_plan(
        case_id="case_x",
        topic="crack detection",
        topic_atoms={
            "task": [{"en": "detection"}],
            "object": [{"en": "concrete pavement crack"}],
            "method": [{"en": "deep learning"}],
            "scenario": [{"en": "highway"}],
        },
        repair_plan=repair_plan,
        retrieval_client=flaky,
    ))

    assert result["planned_queries_n"] == 3
    assert len(calls) == 3
    # Two OK queries produced candidates; one must be in failed_queries.
    assert len(result["failed_queries"]) == 1
    assert result["failed_queries"][0]["query"] == "boom arxiv"
    assert "503" in result["failed_queries"][0]["error"]
    assert result["new_candidates_n"] == 2
    # adapters counted even on failure (the call attempt happened)
    assert result["adapter_calls"]["arxiv"] == 2
    assert result["adapter_calls"]["openalex"] == 1


def test_execute_repair_plan_dedupes_within_batch():
    """Two identical hits from the same query collapse to one candidate."""
    from app.services.agents.metadata_repair_executor import execute_repair_plan

    async def dupe(tool, query, top_k=3):
        return [
            {"title": "Same Title", "url": "https://x/a", "abstract": "abstract body"},
            {"title": "Same Title", "url": "https://x/b", "abstract": "abstract body"},
            {"title": "Different Title", "url": "https://x/c", "abstract": "abstract body"},
        ]

    repair_plan = {
        "repair_plan": [
            {
                "gap": "datasets_present_but_no_topic_dataset",
                "target_role": "dataset",
                "queries": [{"query": "x", "tool": "openalex"}],
            }
        ],
    }
    result = asyncio.run(execute_repair_plan(
        case_id="dup", topic="x", topic_atoms={},
        repair_plan=repair_plan, retrieval_client=dupe,
    ))
    assert result["new_candidates_n"] == 2
    assert result["failed_queries"] == []


def test_execute_repair_plan_no_queries():
    """An empty plan returns all-zero stats without touching the client."""
    from app.services.agents.metadata_repair_executor import execute_repair_plan

    called = []

    async def client(tool, query, top_k=3):
        called.append(tool)
        return []

    result = asyncio.run(execute_repair_plan(
        case_id="empty", topic="t", topic_atoms={},
        repair_plan={"repair_plan": []}, retrieval_client=client,
    ))
    assert result["planned_queries_n"] == 0
    assert result["new_candidates_n"] == 0
    assert result["failed_queries"] == []
    assert called == []

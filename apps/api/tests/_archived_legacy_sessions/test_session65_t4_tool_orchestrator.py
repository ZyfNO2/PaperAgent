"""Session 65 T4: tool_orchestrator whitelist + dispatch tests."""

from __future__ import annotations

import asyncio

import pytest

from app.services.retrieval.tool_orchestrator import (
    TOOL_WHITELIST,
    ToolCall,
    ToolExecutionBundle,
    ToolPlan,
    _validate_tool_name,
    execute_tool_plan,
    execute_tool_plan_sync,
)


# ---------- Fixtures ---------- #


def _make_call(tool: str, call_id: str = "c1", query: str = "concrete crack") -> ToolCall:
    return ToolCall(
        call_id=call_id,
        tool=tool,
        target="paper",
        query=query,
        when_to_call="round 1",
        why_call="test",
        how_call={"top_k": 5},
        expected_output="papers",
        stop_condition="ok",
    )


def _make_plan(calls: list[ToolCall]) -> ToolPlan:
    return ToolPlan(
        topic_atoms={"raw": "test"},
        calls=calls,
        human_gate_after="round_1",
    )


# ---------- Whitelist enforcement ---------- #


def test_whitelist_contains_expected_tools():
    for t in (
        "search_openalex",
        "search_arxiv",
        "search_semantic_scholar",
        "search_github",
        "search_paperswithcode",
        "search_dataset_web",
        "fetch_url_metadata",
    ):
        assert t in TOOL_WHITELIST


def test_validate_tool_name_accepts_whitelisted():
    for t in TOOL_WHITELIST:
        _validate_tool_name(t)  # must not raise


def test_validate_tool_name_rejects_unknown():
    with pytest.raises(ValueError):
        _validate_tool_name("rm_rf")
    with pytest.raises(ValueError):
        _validate_tool_name("subprocess_run")
    with pytest.raises(ValueError):
        _validate_tool_name("")


# ---------- Plan execution: unknown tool → failed + trace ---------- #


def test_execute_plan_unknown_tool_marks_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))
    plan = _make_plan([_make_call("totally_made_up", call_id="c_unk")])
    bundle = execute_tool_plan_sync(plan, "proj_test")
    assert isinstance(bundle, ToolExecutionBundle)
    assert len(bundle.results) == 1
    r = bundle.results[0]
    assert r.status == "failed"
    assert r.call_id == "c_unk"
    assert "whitelist" in (r.error or "").lower()


# ---------- Plan execution: tool without adapter → skipped ---------- #


def test_execute_plan_missing_adapter_marks_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))
    plan = _make_plan([_make_call("search_paperswithcode", call_id="c_pwc")])
    bundle = execute_tool_plan_sync(plan, "proj_test")
    r = bundle.results[0]
    assert r.status == "skipped"
    assert r.tool == "search_paperswithcode"


# ---------- Plan execution: real adapter with stubbed raw output ---------- #


class _FakeAdapter:
    """Callable that mimics the (queries, top_k, *, client) -> list[dict] adapter signature."""

    def __init__(self, payload: list[dict]):
        self.payload = payload
        self.calls: list[tuple[list[str], int]] = []

    async def __call__(self, queries, top_k, *, client=None):
        self.calls.append((list(queries), top_k))
        return list(self.payload)


def test_execute_plan_openalex_with_fake_adapter(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))
    fake = _FakeAdapter([
        {
            "id": "W123",
            "title": "Concrete crack detection with deep learning",
            "publication_year": 2024,
            "doi": "https://doi.org/10.1234/test",
        },
    ])
    # Patch the adapter the orchestrator imports.
    from app.services.retrieval import tool_orchestrator as to_mod
    monkeypatch.setattr(to_mod, "openalex_search", fake)

    plan = _make_plan([_make_call("search_openalex", call_id="c_oa", query="crack")])
    bundle = execute_tool_plan_sync(plan, "proj_test")
    r = bundle.results[0]
    assert r.status == "ok"
    assert r.result_count == 1
    assert r.accepted_count == 1
    assert r.duration_ms >= 0
    # Adapter got the query and top_k from how_call.
    assert fake.calls and fake.calls[0][0] == ["crack"]
    assert fake.calls[0][1] == 5
    # Normalized candidate retains the title.
    assert r.candidates[0]["title"].startswith("Concrete")


# ---------- Adapter exception is surfaced, not swallowed ---------- #


def test_execute_plan_adapter_exception_marks_failed(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))

    async def boom(queries, top_k, *, client=None):
        raise RuntimeError("network down")

    from app.services.retrieval import tool_orchestrator as to_mod
    monkeypatch.setattr(to_mod, "arxiv_search", boom)

    plan = _make_plan([_make_call("search_arxiv", call_id="c_ax")])
    bundle = execute_tool_plan_sync(plan, "proj_test")
    r = bundle.results[0]
    assert r.status == "failed"
    assert "network down" in (r.error or "")
    assert r.candidates == []


# ---------- One bad call doesn't stop the others ---------- #


def test_execute_plan_isolates_failures(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))

    async def ok(queries, top_k, *, client=None):
        return [{"id": "W1", "title": "OK paper", "publication_year": 2024}]

    async def bad(queries, top_k, *, client=None):
        raise RuntimeError("nope")

    from app.services.retrieval import tool_orchestrator as to_mod
    monkeypatch.setattr(to_mod, "openalex_search", ok)
    monkeypatch.setattr(to_mod, "arxiv_search", bad)

    plan = _make_plan([
        _make_call("search_openalex", call_id="c1", query="x"),
        _make_call("search_arxiv", call_id="c2", query="y"),
    ])
    bundle = execute_tool_plan_sync(plan, "proj_test")
    assert len(bundle.results) == 2
    by_id = {r.call_id: r for r in bundle.results}
    assert by_id["c1"].status == "ok"
    assert by_id["c2"].status == "failed"


# ---------- Trace written for every call ---------- #


def test_execute_plan_writes_trace_per_call(tmp_path, monkeypatch):
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))
    plan = _make_plan([
        _make_call("search_openalex", call_id="tc1"),
        _make_call("rm_rf", call_id="tc2"),
    ])
    execute_tool_plan_sync(plan, "proj_trace")

    from app.services.trace_store import get_trace
    out = get_trace("proj_trace", action="tool_orchestrator_executed", limit=50)
    call_ids = {e.target_id for e in out.events}
    assert "tc1" in call_ids
    assert "tc2" in call_ids


# ---------- Async entry point usable directly ---------- #


def test_execute_plan_async_returns_bundle(tmp_path, monkeypatch):
    async def _runner():
        monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path))
        plan = _make_plan([_make_call("search_github", call_id="c_gh")])
        return await execute_tool_plan(plan, "proj_async")

    bundle = asyncio.run(_runner())
    # github_search without a client makes a real network call when no
    # monkeypatch; the test may yield ok/failed depending on env. Either is
    # acceptable as long as the result is recorded.
    assert len(bundle.results) == 1
    assert bundle.results[0].tool == "search_github"

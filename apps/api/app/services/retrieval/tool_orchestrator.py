"""Session 65 T4: ToolPlan executor.

Runs a ``ToolPlan`` produced by the LLM Search Planner. Each ``ToolCall``
maps to one of the whitelisted search tools. The orchestrator:
  1. Validates the tool name against the whitelist (hard rule).
  2. Dispatches to the matching adapter (async) with the call's query.
  3. Normalizes the raw adapter output to ``RetrievalCandidate`` dicts.
  4. Records per-call timing + counts (ok / failed / skipped).
  5. Writes a trace event for every call (including failures) so the
     trace store is never silent on errors.

Hard rules:
  - Only tools in ``TOOL_WHITELIST`` may execute; anything else raises.
  - Adapter failures are caught and surfaced as ``status="failed"`` —
    they are NEVER silently swallowed.
  - Rejected candidates are not produced here; that's ``candidate_cleaner``'s
    job. The orchestrator only deals with the candidate stream that came
    back from the adapter.
  - No shell execution. No large-file download (adapters handle that).
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, ConfigDict
from typing_extensions import Literal

from ..trace_store import append_trace
from .adapters import (
    arxiv_search,
    github_search,
    huggingface_search,
    kaggle_search,
    openalex_search,
    semantic_scholar_search,
)
from .normalizer import normalize_candidate


# ---------- Whitelist ---------- #

TOOL_WHITELIST: frozenset[str] = frozenset({
    "search_openalex",
    "search_arxiv",
    "search_semantic_scholar",
    "search_github",
    "search_paperswithcode",
    "search_dataset_web",
    "fetch_url_metadata",
})


# ---------- Data structures ---------- #


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool: str
    target: Literal["paper", "dataset", "repo", "baseline", "module_paper"]
    query: str
    when_to_call: str
    why_call: str
    how_call: dict
    expected_output: str
    stop_condition: str


class ToolPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_atoms: dict
    calls: list[ToolCall]
    human_gate_after: str


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_id: str
    tool: str
    status: Literal["ok", "failed", "skipped"]
    result_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    needs_manual_count: int = 0
    duration_ms: int = 0
    error: str | None = None
    candidates: list[dict] = []


class ToolExecutionBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    results: list[ToolExecutionResult]


# ---------- Tool → adapter dispatch ---------- #

# Maps the whitelisted tool name to the adapter attribute name on this
# module. Resolved at call time so tests can monkeypatch the adapter
# function on this module and have the dispatch pick it up.
#: ponytail: attribute lookup is intentional — keeps the dispatch table
#: declarative while still letting tests swap the underlying callables.
_AdapterFn = Callable[..., Awaitable[list[dict]]]

_TOOL_ADAPTER_ATTR: dict[str, str] = {
    "search_openalex": "openalex_search",
    "search_arxiv": "arxiv_search",
    "search_semantic_scholar": "semantic_scholar_search",  # stub adapter
    "search_github": "github_search",
}

_TOOL_DEFAULT_TOP_K: dict[str, int] = {
    "search_openalex": 8,
    "search_arxiv": 8,
    "search_semantic_scholar": 8,
    "search_github": 8,
    "search_paperswithcode": 8,  # no adapter; mark skipped
    "search_dataset_web": 8,     # no adapter; mark skipped
    "fetch_url_metadata": 8,    # no adapter; mark skipped
}

# Tools without a backing adapter — they get status="skipped".
_TOOLS_WITHOUT_ADAPTER: frozenset[str] = frozenset({
    "search_paperswithcode",
    "search_dataset_web",
    "fetch_url_metadata",
})


# ---------- Validation ---------- #


def _validate_tool_name(tool: str) -> None:
    """Raise ValueError if tool is not in the whitelist."""

    if tool not in TOOL_WHITELIST:
        raise ValueError(f"tool not in whitelist: {tool!r}")


# ---------- Single tool execution ---------- #


def _resolve_adapter(tool: str) -> _AdapterFn | None:
    """Return the adapter callable for ``tool``, or None if none registered.

    Looks the adapter up on the current module each call, so tests that
    monkeypatch the module attribute see the patched version.
    """

    attr = _TOOL_ADAPTER_ATTR.get(tool)
    if not attr:
        return None
    return globals().get(attr)


async def _run_tool(
    call: ToolCall,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Run a single tool call. Returns raw adapter output (list[dict]).

    Raises if the tool is unknown. For whitelisted tools without a backing
    adapter, returns ``[]`` (caller treats as "skipped").
    """

    _validate_tool_name(call.tool)
    adapter = _resolve_adapter(call.tool)
    if adapter is None:
        return []
    default_top_k = _TOOL_DEFAULT_TOP_K.get(call.tool, 8)
    top_k = int(call.how_call.get("top_k") or default_top_k)
    return await adapter([call.query], top_k, client=client)


def _normalize_result(
    tool: str,
    raw: list[dict],
    *,
    project_id: str,
) -> list[dict]:
    """Normalize raw adapter output to ``RetrievalCandidate`` dicts.

    Each candidate gets a fresh ``candidate_id``. The original raw dict is
    preserved under the ``raw`` key.
    """

    # Map tool name → SearchSource literal used by the normalizer.
    tool_to_source = {
        "search_openalex": "openalex",
        "search_arxiv": "arxiv",
        "search_semantic_scholar": "semantic_scholar",
        "search_github": "github",
        "search_paperswithcode": "manual_fallback",  # no real adapter
        "search_dataset_web": "huggingface",         # best-effort
        "fetch_url_metadata": "manual_fallback",
    }
    source = tool_to_source.get(tool, "manual_fallback")
    out: list[dict] = []
    for r in raw or []:
        if not isinstance(r, dict):
            continue
        cand_id = f"cand_{uuid.uuid4().hex[:10]}"
        try:
            cand = normalize_candidate(
                r,
                project_id=project_id,
                source=source,  # type: ignore[arg-type]
                candidate_id=cand_id,
            )
        except Exception:  # noqa: BLE001 — never let a bad raw kill the run
            continue
        out.append(cand.model_dump())
    return out


# ---------- Trace ---------- #


def _write_trace(
    call: ToolCall,
    result: ToolExecutionResult,
    *,
    project_id: str,
) -> None:
    """Write a trace event for this tool call. Always called, ok or not."""

    append_trace(
        project_id=project_id,
        action="tool_orchestrator_executed",
        target_type="tool_call",
        target_id=call.call_id,
        reason=call.why_call,
        actor="agent",
        before={
            "tool": call.tool,
            "query": call.query,
            "target": call.target,
            "when_to_call": call.when_to_call,
        },
        after={
            "status": result.status,
            "result_count": result.result_count,
            "duration_ms": result.duration_ms,
            "error": result.error,
        },
        source="tool_orchestrator",
    )


# ---------- Public entry ---------- #


async def execute_tool_plan(
    plan: ToolPlan,
    project_id: str,
    *,
    client: Any | None = None,
) -> ToolExecutionBundle:
    """Execute each tool call in ``plan`` and return a bundle of results.

    Each call is run independently. Failures in one call do not stop the
    others — every call gets a result entry and a trace event.
    """

    results: list[ToolExecutionResult] = []

    for call in plan.calls:
        t0 = time.monotonic()
        # 1) whitelist
        try:
            _validate_tool_name(call.tool)
        except ValueError as e:
            r = ToolExecutionResult(
                call_id=call.call_id,
                tool=call.tool,
                status="failed",
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=str(e),
            )
            _write_trace(call, r, project_id=project_id)
            results.append(r)
            continue

        # 2) dispatch
        if call.tool in _TOOLS_WITHOUT_ADAPTER:
            r = ToolExecutionResult(
                call_id=call.call_id,
                tool=call.tool,
                status="skipped",
                duration_ms=int((time.monotonic() - t0) * 1000),
                error="no adapter registered",
            )
            _write_trace(call, r, project_id=project_id)
            results.append(r)
            continue

        # 3) run (catch any exception so the bundle still completes)
        try:
            raw = await _run_tool(call, client=client)
        except Exception as e:  # noqa: BLE001
            r = ToolExecutionResult(
                call_id=call.call_id,
                tool=call.tool,
                status="failed",
                duration_ms=int((time.monotonic() - t0) * 1000),
                error=f"{type(e).__name__}: {e}",
            )
            _write_trace(call, r, project_id=project_id)
            results.append(r)
            continue

        # 4) normalize
        cands = _normalize_result(call.tool, raw, project_id=project_id)
        r = ToolExecutionResult(
            call_id=call.call_id,
            tool=call.tool,
            status="ok",
            result_count=len(cands),
            accepted_count=len(cands),  # orchestrator doesn't reject; cleaner does
            duration_ms=int((time.monotonic() - t0) * 1000),
            candidates=cands,
        )
        _write_trace(call, r, project_id=project_id)
        results.append(r)

    return ToolExecutionBundle(project_id=project_id, results=results)


# ---------- sync helper for tests / non-async callers ---------- #


def execute_tool_plan_sync(
    plan: ToolPlan,
    project_id: str,
    *,
    client: Any | None = None,
) -> ToolExecutionBundle:
    """Blocking wrapper around :func:`execute_tool_plan`."""

    return asyncio.run(execute_tool_plan(plan, project_id, client=client))

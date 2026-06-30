# Task T4 Report: tool_orchestrator.py

## Status: DONE

## What was implemented

Created `apps/api/app/services/retrieval/tool_orchestrator.py` with:

**Data models (4 Pydantic classes):**
- `ToolCall` — `call_id`, `tool`, `target` (Literal: paper/dataset/repo/baseline/module_paper), `query`, `when_to_call`, `why_call`, `how_call`, `expected_output`, `stop_condition`
- `ToolPlan` — `topic_atoms: dict`, `calls: list[ToolCall]`, `human_gate_after: str`
- `ToolExecutionResult` — `call_id`, `tool`, `status` (Literal: ok/failed/skipped), `result_count`, `accepted_count`, `rejected_count`, `needs_manual_count`, `duration_ms`, `error`, `candidates: list[dict]`
- `ToolExecutionBundle` — `project_id`, `results: list[ToolExecutionResult]`

**Whitelist:**
- `TOOL_WHITELIST` = frozenset of 7 tools: `search_openalex`, `search_arxiv`, `search_semantic_scholar`, `search_github`, `search_paperswithcode`, `search_dataset_web`, `fetch_url_metadata`

**Public functions:**
- `execute_tool_plan(plan, project_id, *, client=None) -> ToolExecutionBundle` (async) — runs every call, isolates failures, writes a trace per call
- `execute_tool_plan_sync(...)` — blocking wrapper for tests / non-async callers

**Internal helpers:**
- `_validate_tool_name(tool)` — raises `ValueError` for non-whitelisted names
- `_resolve_adapter(tool)` — looks up the adapter callable on the current module so tests can monkeypatch it
- `_run_tool(call, *, client)` — dispatches one call to its adapter with `top_k` from `how_call`
- `_normalize_result(tool, raw, *, project_id)` — maps raw adapter output to `RetrievalCandidate` dicts via the existing `normalize_candidate`
- `_write_trace(call, result, *, project_id)` — always writes a trace event (ok / failed / skipped), never silent

## Adapter coverage
- `search_openalex` → `openalex_search`
- `search_arxiv` → `arxiv_search`
- `search_semantic_scholar` → `semantic_scholar_search` (stub, returns `[]`)
- `search_github` → `github_search`
- `search_paperswithcode`, `search_dataset_web`, `fetch_url_metadata` → no adapter → `status="skipped"` with `error="no adapter registered"`

## Rules honored
1. **Whitelist enforcement** — `_validate_tool_name` raises on unknown tools; `execute_tool_plan` catches the `ValueError` and emits a `failed` result with the error message and writes a trace. No silent acceptance.
2. **No silent failures** — every adapter exception is caught, recorded as `status="failed"`, and traced. `OK` only means the adapter returned and normalization didn't raise.
3. **Rejection is not the orchestrator's job** — `accepted_count` mirrors `result_count` here; `candidate_cleaner` (S64 T1) does the actual reject/quarantine/keep classification downstream. Hard rule 3 is therefore observed by *not* inventing rejection here.
4. **No shell execution** — only adapter functions are called; no `subprocess`/`os.system`.
5. **No large file download** — adapter layer handles all I/O; orchestrator only passes the `query` string.

## Test coverage (`tests/test_session65_t4_tool_orchestrator.py`, 10 tests, all pass)
- Whitelist contains the 7 expected tools
- `_validate_tool_name` accepts whitelisted, rejects unknown (`rm_rf`, `subprocess_run`, `""`)
- Unknown tool → `status="failed"`, error mentions "whitelist", trace written
- Tool without adapter → `status="skipped"`, error "no adapter registered"
- Real adapter with monkeypatched fake payload → `status="ok"`, normalized candidate retains title
- Adapter raises `RuntimeError` → `status="failed"`, error contains exception message, `candidates == []`
- One failing call does not stop the other calls in the same plan
- Trace events written for every call (ok AND failed), one per `call_id`
- Async entry point returns a populated bundle

## How it fits the LLM Search Planner
- The planner produces a `ToolPlan` from topic atoms
- The orchestrator executes the plan, normalizes results, records timing + errors
- Downstream: the bundle's `candidates` feed `candidate_cleaner` for keep/quarantine/reject, and the bundle's `results` feed the UI / report
- Trace events with `action="tool_orchestrator_executed"` make every tool call inspectable in the trace store

## Skipped (add when needed)
- Per-tool retry/backoff inside `_run_tool` — current behavior is single-shot; orchestrator already isolates failures so retries can be added at the plan level later
- Parallel execution of `plan.calls` with `asyncio.gather` — current is sequential; each adapter is independent so parallel is straightforward when throughput matters
- Adapter-specific `how_call` config parsing beyond `top_k` — adapters don't use other fields yet

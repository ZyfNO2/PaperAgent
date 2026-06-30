# Task T2 Report: baseline_selection.py

## Status: DONE

## What was implemented

Created `apps/api/app/services/retrieval/baseline_selection.py` and `apps/api/tests/test_session65_baseline_selection.py`.

**Data model (2 Pydantic classes):**
- `BaselineSelection` — `candidate_id`, `baseline_role` (Literal: primary/secondary/comparison), `user_reason`, `expected_dataset`, `selected_at` (ISO)
- `BaselineSelectionState` — `project_id`, `selected_baselines: list[BaselineSelection]`, `status` (Literal: pending_selection / baseline_selected / baseline_rejected)

**Public functions:**
- `can_be_baseline(candidate: dict) -> bool` — rejects survey / irrelevant / dataset_paper roles and `candidate_type='dataset'`; everything else passes through (UI warns for unknown role)
- `select_baseline(project_id, candidate, role, user_reason, expected_dataset=None) -> BaselineSelection` — validates role ∈ {primary,secondary,comparison}, rejects survey/irrelevant/dataset, rejects empty user_reason, replaces existing selection for same candidate_id, sets status to baseline_selected, emits trace
- `unselect_baseline(project_id, candidate_id) -> None` — idempotent; if list becomes empty, status reverts to pending_selection
- `get_selected_baselines(project_id) -> list[BaselineSelection]` — empty list when no project
- `get_baseline_state(project_id) -> BaselineSelectionState` — never returns None (default pending_selection state)
- `find_candidate_for_baseline(project_id, candidate_id)` — thin wrapper over `candidate_actions._find_candidate`
- `reset_baseline_state()` — test fixture

**Storage:** in-memory `dict[str, BaselineSelectionState]` guarded by `threading.Lock`. Per-project isolation tested.

**Trace:** `select` / `unselect` emit `baseline_selected` / `baseline_unselected` events. Tries to reuse `orchestrator.emit_run_event`; falls back to stdout print (no such function exists yet — intentional, future orchestrator hook).

## Hard rules honored
1. No auto-select anywhere — `select_baseline` is the only entry that creates a `BaselineSelection`, and it requires explicit `user_reason`.
2. Survey / irrelevant / dataset_paper / candidate_type=dataset all rejected by `can_be_baseline` (called inside `select_baseline`).
3. `expected_dataset` is optional user input (e.g. "X-Bench") — dataset *candidates* themselves still can't be baselines.
4. Empty `user_reason` (or whitespace-only) raises.
5. Initial `get_baseline_state(...).status == "pending_selection"` — the "Baseline 待确认" state for UI.

## Tests
`apps/api/tests/test_session65_baseline_selection.py` — **23 tests, all pass**:
- `TestCanBeBaseline` (9): each role + candidate_type combination
- `TestSelectBaselineRejects` (5): survey, dataset, empty reason, invalid role, missing candidate_id
- `TestSelectUnselectFlow` (9): initial state, first select transitions status, multiple selections, reselect-overrides-role, unselect keeps status when others remain, unselect-all reverts to pending, unselect nonexistent is no-op, get returns list, per-project isolation

Plus an in-module `_self_check()` runnable via `python -m app.services.retrieval.baseline_selection` (12 assertions including orchestrator-driven flow with a fake RetrievalRun containing survey + dataset + method + framework candidates).

## Files
- `apps/api/app/services/retrieval/baseline_selection.py` (new, 280 lines)
- `apps/api/tests/test_session65_baseline_selection.py` (new, 23 tests)
- `g:/PaperAgent/.superpowers/sdd/s65-task-T2-report.md` (this file)

## Skipped (ponytail)
- API endpoints (`POST /baseline/select`, `POST /baseline/unselect`, `GET /baseline/selected`) — not in T2 file scope; T7 or a follow-up task can wire these into `one_topic.py` router. The functions are the unit of work; routing is one decorator each, add when the frontend needs them.
- Persistent storage (SQLite/JSON) — memory dict + thread lock is fine for S65 baseline selection UI; the orchestrator's `_RUNS` is also in-memory. Add a `baseline_store.py` (mirroring `evidence.py`) when restart-survival matters.
- `baseline_rejected` status — defined in the model per spec but no path sets it yet. Add a `reject_baseline()` helper when the UI needs an explicit "reject this candidate from being baseline" action.
- Real trace hook — `orchestrator.emit_run_event` doesn't exist; current fallback prints to stdout. Will hook into the orchestrator's trace bus when it lands.

## Test command

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session65_baseline_selection.py -v
# 23 passed in 0.40s
```

## Self-check command

```bash
PYTHONPATH=apps/api .venv/Scripts/python.exe -m app.services.retrieval.baseline_selection
# [baseline_selection] self-check OK
```
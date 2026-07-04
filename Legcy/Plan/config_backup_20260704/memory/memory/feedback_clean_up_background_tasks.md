---
name: clean-up-background-tasks
description: "User reminds to clean up long-running background tasks (uvicorn / dev servers / pytest runs) before moving on; if a task is stale, stop it instead of leaving it."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5255e917-87a7-4faf-bdbf-03b162e0ea62
---

Long-running background tasks (`uvicorn`, `dev_server.py`, `pytest`, subagent dispatches) accumulate state in `C:/Users/ZYF/AppData/Local/Temp/claude/.../tasks/*.output` and hold onto a port. If you don't kill them, the next session's port 18181 / 18182 can be occupied, and stale `.output` files pile up.

**Why:** The user noticed the task output directory filled with `.output` files that nobody had killed off. Stale uvicorn processes also break the next Playwright run.

**How to apply:**
- Before writing a "done" message or moving to the next task, run `TaskList` / check `TaskOutput` to see if any background task is still "running" or has stale state.
- When the work that the background task was supporting is complete (test run done, smoke done), explicitly `TaskStop` it if it is still tracked.
- For shell processes spawned with `run_in_background` (uvicorn, dev_server, pytest) the harness does not auto-stop them when the foreground turn ends. Either keep them intentionally and stop at the very end, or `TaskStop` after the dependent work finishes.
- Prefer a single background uvicorn per session; do not re-spawn it for every smoke test.
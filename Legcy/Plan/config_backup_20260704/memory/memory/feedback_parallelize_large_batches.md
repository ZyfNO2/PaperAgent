---
name: parallelize-large-batches-by-default
description: "User explicit ask 2026-07-04 — when a long-running batch (Re0X / validator loops / batch eval / 40+ cases) is started, dispatch to parallel subagents instead of waiting for the whole serial run in the main session."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f5a92cba-efa2-482f-a47b-0f7e4d1b79f3
---

Large batches (Re0X balanced40 / 100-case loop / 5+ validator sweeps) should run as parallel subagents in the background, not as a single serial wait in the main session.  The main session should poll `gs` status and report consolidated results, not block for 80 minutes.

**Why:**  User explicit ask 2026-07-04 during [[feedback_parallelize_with_subagents_by_default]] follow-up.  Single-threaded 80-min wait burned context window for trivial poll checks.

**How to apply:**
- If a task is "run N cases through a script", split into ≤4 subagents each handling N/4 cases into a separate output dir (`<out>_subX`), then merge validator / CSV at the end.
- Always keep one `run_main` running in foreground for early visibility (TYPICAL-01 / 02 / 03), then fan out the rest after the first 3 traces look healthy.
- Use `run_in_background: true` with `bun_…` task IDs and check status via `ps -ef | grep`; never block main on long tasks.

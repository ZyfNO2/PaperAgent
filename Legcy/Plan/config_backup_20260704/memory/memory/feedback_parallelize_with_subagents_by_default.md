---
name: parallelize-with-subagents-by-default
description: Long Re0X sessions with multiple independent chunks should dispatch subagents in parallel by default; user explicitly requested this on 2026-07-03
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c37837b-7238-4edd-bdb1-4535500e9597
---

Long Re0X sessions with multiple independent chunks (SOP §4 task list,
multi-section report writing, parallelizable smoke tests, large CSV
generation, batch adapter network calls) MUST dispatch subagents in
parallel by default rather than running everything serially in the main
session.

**Why:** User explicitly asked "加快一下进度，能放子智能体并行做的活就放子智能体去做" on 2026-07-03 during Re09 fresh online run. Each subagent saves the main session time for orchestration / audit / SOP compliance, and parallel batches finish ~3-5x faster than serial. Burns LLM quota is OK per existing rule (feedback_no_llm_dead_path_deliverable.md).

**How to apply:**

1. Identify chunks that are **independent** — no shared state between them, no read-after-write dependency. Examples:
   - Code module N files each can be written by separate subagent
   - Multiple test modules can run in parallel
   - Multiple report sections can be drafted in parallel after data is computed
   - Multiple adapter smoke tests for 5+ sources can run in parallel
   - Multiple re-audit batches can be parsed + written to CSV in parallel
2. Use `Agent` tool with `general-purpose` subagent_type and concrete prompt (what to do, what files to touch, what output format, what exit condition).
3. Main session only orchestrates: collects subagent outputs, runs cross-checks, writes the summary section + SOP §X.X honesty self-check.
4. Keep serial what must be serial: SOP compliance gate, git commits, validator scripts that depend on all prior outputs.
5. Don't over-parallelize: 2-4 subagents in parallel is enough; more than 6 saturates the user's machine.

**Anti-patterns to avoid:**
- Sequential `Write x 10` when 5 subagents could each write 2 files in parallel
- Main session runs a 40-case audit when subagents can each process 10 cases
- Sequential smoke tests for 5 adapters when one async gather covers them all

**Related:**
- [[feedback_delegate_tests_reports_commits]]
- [[feedback_testing_via_subagents]]
- [[feedback_incremental_updates_subagent]]
- [[feedback_no_llm_dead_path_deliverable]]
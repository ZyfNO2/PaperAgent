---
name: delegate-tests-reports-commits-to-subagents
description: Tests, reports, and commits must all run via subagents to keep main session free. Strictly enforced.
metadata:
  type: feedback
  originSessionId: ccf1f411-7809-4989-8827-eaf18075c961
---

All heavy execution — pytest, report writing, and git commits — MUST be delegated to subagents. The main session stays free for orchestration and review.

**Why:** Long-running pytest blocks the main session for minutes. Reports and commits are mechanical tasks that don't need main-session context. Delegating them keeps the user responsive and the main loop unblocked.

**How to apply:**
1. **Tests**: Always run pytest via a general-purpose subagent. Prompt includes: working dir, exact command, expected result, what to report back (pass/fail count, any failures with tracebacks).
2. **Reports**: Write acceptance reports via a subagent. Prompt includes: SOP requirements for the report, file path to write, data to include (test results, what was built, schema changes).
3. **Commits**: Run `git add` + `git commit` via a subagent. Prompt includes: exact commit message, files to stage, working dir.
4. **Parallel when possible**: If tests for S22 and S23 are independent, run them in parallel subagents. If one depends on the other, run sequentially.
5. **Never block main session** on a foreground pytest / uvicorn / commit command — always use subagent or background task.

**Overrides:** This takes precedence over the earlier `testing-via-subagents` memory which only covered tests. This new rule extends the pattern to reports and commits as well.

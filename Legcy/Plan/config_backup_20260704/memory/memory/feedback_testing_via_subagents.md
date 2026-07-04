---
name: testing-via-subagents
description: User prefers delegating test execution to subagents and parallelizing test batches when scope allows; pre-test planning should consider whether work can be split into parallel batches.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bd69cf55-4a35-4514-af09-62e236adabf1
---

When test scope grows beyond a single test file or a handful of tests, run them via dispatched subagents (general-purpose / Explore) and split independent test batches across parallel agents instead of one big foreground run.

**Why:** Tests can be slow (the playwright Session 10 run alone was ~8 min). Parallel subagents finish in roughly the time of the slowest single batch, and a long-running foreground `pytest` blocks the session from doing other useful work.

**How to apply:**
- For pure test execution (no in-flight analysis), spin up a subagent per independent batch (e.g. backend regression / playwright e2e / smoke).
- Each subagent gets a self-contained prompt: working directory, exact pytest invocation, expected exit code, list of files to read for context, and what to report back.
- Don't parallelize when tests share mutable backend state on a single uvicorn port — run sequentially or split by test category that hits different fixtures / ports.
- Keep the main session available to read results, write the acceptance report, and do git commits — those steps stay foreground.
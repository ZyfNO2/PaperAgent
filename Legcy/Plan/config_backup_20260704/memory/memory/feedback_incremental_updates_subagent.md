---
name: incremental-updates-via-subagent
description: "When a task becomes '大量小量更新' (many small file edits / repeated mechanical changes), dispatch a subagent instead of doing each one in the foreground session. Use the time freed to fire the audit/trace hooks (e.g. pre_report_audit / user_completion_check) to verify the work."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 456ece0c-bb67-4c7a-9b58-3f62b6a4aebb
---

When a task is **mechanical, repeated, and small per step** (e.g. writing a multi-section report by appending 5 chunks; running pytest then re-running; committing many files; merging many tables), the foreground session can blow its output budget fast on sheer volume. The user explicitly asked to **offload this work to subagents** and use the freed time for audit.

**How to apply:**

1. **Detect "大量小量更新" trigger conditions:**
   - User message contains phrases like "慢慢来", "小量更新", "分多次", "增量"
   - A pending task is clearly a list of 3+ similar operations (append sections, run multiple pytest suites, write multiple test files)
   - Estimated total output bytes > ~4k

2. **Dispatch to a subagent:**
   - Each subagent gets a self-contained spec (input file, output file, exact instructions)
   - Subagent writes the file directly via `cat heredoc` or `Write` tool (NOT via the foreground session)
   - The subagent's transcript doesn't count against the foreground output budget

3. **Use the freed foreground time for audit:**
   - Run the `pre_report_audit` hook on the candidate output
   - Run `user_completion_check` to scan for the latest trace dump
   - Verify the per-call data delta table is present
   - Check for LLM-dead-path markers in the candidate report
   - Surface any bug found (e.g. hook stderr race, missing field) BEFORE the report is finalized

4. **Common mistake to avoid:**
   - Don't repeatedly try the same `cat > file << EOF` after it fails — once it fails 2x, dispatch a subagent
   - Don't dump 10k chars to stdout in foreground — subagent handles the heavy lifting, foreground just signals completion

Related: [[no-llm-dead-path-deliverable]], [[project-topicpilot-claude-md-rules]]

# 完工报告写盘前审计 (snapshot)

> **Snapshot only — opencode 不会自动跑这个脚本。**
> 详见同目录 `../rules/hooks-mirror.md` 第 4 节。

This file is a verbatim copy of `G:\PaperAgent\.claude\hooks\pre_report_audit.py`,
preserved so that the audit logic stays inspectable from an opencode session and
so the user can run it by hand via the PowerShell command below.

```powershell
# 方法 1：把要审计的 Write payload 通过 stdin 喂给脚本
$payload = @{
  tool_name   = "Write"
  tool_input  = @{
    file_path = "Plan\reports\Phase_test_完工报告.md"
    content   = (Get-Content .\your-report.md -Raw)
  }
} | ConvertTo-Json -Depth 10
$payload | uv run python .opencode/hooks/pre_report_audit.py
```

## 来源

- Original: `.claude/hooks/pre_report_audit.py`
- Triggers on: Claude Code `PreToolUse(Write)` of any `*完工报告*.md`
- Audits for:
  - **dead-path markers** (LLM-unavailable fallback, heuristic fallback, "changing data sources" generic ML title, etc.)
  - **good-data markers** (domain_route, query_atoms_en, baseline_options id, can_continue_to_opening_report, llm_calls≥3)
  - **per-round data delta section** (mandatory per Re03 SOP §1.6)
  - **3-choose-1 audit conclusion** (A)CODE BUG / B)PLANNED-AS-IS / C)BLOCKED-AFTER-5
- Exit code: **0 always** (non-blocking)

## opencode 等价行为

参考 `.opencode/rules/hooks-mirror.md`。

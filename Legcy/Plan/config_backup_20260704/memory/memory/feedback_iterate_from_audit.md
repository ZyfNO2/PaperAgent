---
name: iterate-from-self-audit
description: "After a \"full loop\" run reaches 95% pass, do NOT stop — spawn one self-audit subagent that reads every fail/weak trace, surfaces the top 3 systemic issues, and re-loops fix → retest on those issues only (not the whole batch) before declaring done."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f5a92cba-efa2-482f-a47b-0f7e4d1b79f3
---

**Why:**  User explicit ask 2026-07-04 — "发现问题不要只改一次，而是迭代修改，最后自我审核".  Single-pass 95% leaves the residual 5% unaddressed; users want the second-pass iteration where the audit reveals root causes for the failed 5%.

**How to apply:**
- After a Balanced40 / 100-case batch reaches 95% pass+weak, dispatch a single audit subagent that reads every fail/weak case's trace and produces a ranked root-cause list.
- For each root cause found, do **targeted fix → small retest** (only the failing cases, not the whole batch).  Then full re-validation.
- Iterate until either (a) remaining failure list is empty OR (b) the same failure recurs in 3 consecutive iterations (converged; document and stop).
- Document the iteration count in the final report so user can see "1st pass 95% → audit → 2nd pass 99% → audit → 3rd pass 99.5%".

Related: [[feedback_hooks_audit_table]], [[feedback_reports_must_include_csv_summary]].

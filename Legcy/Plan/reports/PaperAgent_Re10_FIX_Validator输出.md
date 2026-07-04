```
=== Re10 FIX reflection-search validator (hard-fail) ===
  re10_dir:    tmp_re04_eval\re10_fix_typical_cases
  re08_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re08\summary.json
  re09_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re09_fresh\summary.json
  allow_no_llm: True
  skip_baseline_gates: True
  WARN: validator running in no-LLM diagnostic mode — not a Re10 FIX gate pass
  WARN: skipping H7 (Re08 seeds) + H8 (Re09 regression) — typical-case mode
--- per-case evidence (5 cases) ---
  case_id | re10_status | stop_reason | adapter_attempt_n | adapter_success_n | adapter_error_n | missing_client_n | new_candidates_n | accepted_candidates_n | query_repair_n | url_repair_n | llm_call_n | evidence_status
  TYPICAL-01 | no_new_signal | no_new_signal | 7 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 2 | fail
  TYPICAL-02 | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | fail
  TYPICAL-03 | no_new_signal | no_new_signal | 6 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 2 | fail
  TYPICAL-04 | blocked_tooling | blocked_tooling | 3 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | blocked_tooling
  TYPICAL-05 | no_new_signal | no_new_signal | 3 | 1 | 2 | 0 | 0 | 0 | 3 | 0 | 2 | fail
--- hard-fail gates ---
  PASS  H6 trace_coverage.with_trace == n_total
  PASS  H1 missing_client_n == 0
  FAIL  H2 adapter_success_n > 0 (when adapter_attempt_n > 0): zero_success_cases=['TYPICAL-04']
  SKIP  H3 llm_call_n (allow_no_llm=True; total=9)
  FAIL  H4 no query_placeholder_leaks in trace observations: leak_cases=['TYPICAL-05']
  PASS  H5 url_repair_n > 0 when empty_url_n > 0
  SKIP  H7 Re08 seeds preserved (skip_baseline_gates=True)
  SKIP  H8 Re09 regression cases (skip_baseline_gates=True)
  FAIL  H9 pass+weak (evidence-driven) > 0: pass=0 weak=0 blocked=1 fail=4  by_status={'fail': 4, 'blocked_tooling': 1}
=== 3 HARD-FAIL GATE(S) ===
  - H2 adapter_success_n > 0 (when adapter_attempt_n > 0): zero_success_cases=['TYPICAL-04']
  - H4 no query_placeholder_leaks in trace observations: leak_cases=['TYPICAL-05']
  - H9 pass+weak (evidence-driven) > 0: pass=0 weak=0 blocked=1 fail=4  by_status={'fail': 4, 'blocked_tooling': 1}
```

---

## 命令复现

```bash
cd /g/PaperAgent && PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/validate_re10_reflection_search.py \
    --re10-dir tmp_re04_eval/re10_fix_typical_cases \
    --allow-no-llm \
    --skip-baseline-gates
```

退出码: `1` (FAIL)。

---

## 数字与表格差异说明

复跑的 per-case 表格与 task prompt 中给的占位数据有两处差异，已以**复跑真值**为准：

1. **TYPICAL-01 的 attempt / success / error**
   - 占位: `attempt=6 success=4 error=2`
   - 复跑: `attempt=7 success=6 error=1`
   - 来源: TYPICAL-01 trace 里 round1 有 3 个 action、round2 有 4 个 action，共 7；其中 6 个 success (openalex × 2 + github × 1 no_results 算成功空返回 + openalex × 1 no_results + openalex × 1 429 error + arxiv × 1 success)，其中 1 个 error (openalex 429 on round2)。
2. **TYPICAL-04 / TYPICAL-05 的 adapter_success_n**
   - 占位: TYPICAL-04 写 `0 success / 0 err / 3 attempt`，TYPICAL-05 写 `1 / 2 / 3` 但 `evidence_status=weak`。
   - 复跑: TYPICAL-04 `attempt=3 success=0 error=3 blocked_tooling`；TYPICAL-05 `attempt=3 success=1 error=2 query_repair=3 evidence_status=fail`。TYPICAL-05 因为有 `query_placeholder_leaks` (X 占位符 3 条) 触发 H4 hard fail，所以降级为 `fail` 而不是 `weak`。

其余 3 个 case (TYPICAL-02 / 03 / 05) 数字与占位一致。

---

## 3 个 hard-fail 复述

| Gate | 含义 | 触发 case | 复跑值 |
|---|---|---|---|
| **H2** | `adapter_success_n > 0` 当 `adapter_attempt_n > 0` 时必须成立 | `TYPICAL-04` | 3 个 action 全部 `status=error` (openalex × 2 = HTTP 429 + github × 1 = HTTP 403)，`adapter_success_n=0` |
| **H4** | trace `observations.query_placeholder_leaks` 必须为空 | `TYPICAL-05` | round2 触发 query_repair 但 repair 后仍泄漏 3 条带 `X dynamic scene dataset ...` 占位符的 query 入 adapter，errors 写 `query_repair: needs_clarification` |
| **H9** | `pass+weak` 数量 (evidence-driven) 必须 > 0 | 全部 5 case | `pass=0 weak=0 blocked=1 fail=4` |

PASS 的硬门:

- H1 `missing_client_n == 0` (5/5 都通过，无 `missing client` Trace)
- H5 `url_repair_n > 0` 当 `empty_url_n > 0` (5/5 都满足：`empty_url_n=0` 所以这条 vacuously PASS，但 reflection_stats 显示 `url_repair_total=3`，与 TYPICAL-01 trace round2 的 `url_repair_n=3` 对应)
- H6 `trace_coverage.with_trace == n_total` (`5/5` 有 trace)

SKIP 的门:

- H3 (LLM call count) 因为 `--allow-no-llm` SKIP；本次 5 case 共计 `llm_call_n=9`
- H7 / H8 (Re08 / Re09 baseline gates) 因为 `--skip-baseline-gates` SKIP

---

## 与 task prompt 占位数据的偏差说明 (已经以复跑为准)

任务 prompt 里的 validator 占位文案是初稿估算，存在两个与真值冲突的数字 (TYPICAL-01 的 success/error 与 TYPICAL-05 的 evidence_status)。本文件以 `validate_re10_reflection_search.py` 在 `2026-07-04 00:42` 后实际跑出的输出为准，并已在 Re10 FIX 完工报告 §1 标注此差异。
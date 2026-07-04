# PaperAgent Re09 Balanced40 逐论文审计 (40 cases)

> 起草日：2026-07-03  
> 范围：Re09 SOP §6 Step 5 / Step 6 + §12 交付物  
> 上游：Re08 Balanced40 (24 pass + 13 weak + 3 fail = 92.5%)  
> 数据源：`tmp_re04_eval/balanced40_re09_fresh/{summary.json, repair_plans.json, batch{1,2,3}/<case>.json}`  
> run_id: `re09_fresh_20260703_200155_0c8052`  
> 配套报告：
>   - [PaperAgent_Re09_完工报告.md](PaperAgent_Re09_完工报告.md) — 主报告
>   - [PaperAgent_Re09_真实补证执行明细.md](PaperAgent_Re09_真实补证执行明细.md) — 3 fail + 13 weak 执行 trace
>   - [PaperAgent_Re09_FreshRunManifest.json](PaperAgent_Re09_FreshRunManifest.json) — fresh run manifest

**数据汇总（Excel 友好）**：[PaperAgent_Re09_Balanced40_逐论文审计.csv](PaperAgent_Re09_Balanced40_逐论文审计.csv) (case-level, 40 cases × 40 cols)
**候选论文清单（Excel 友好）**：[PaperAgent_Re09_Balanced40_候选论文.csv](PaperAgent_Re09_Balanced40_候选论文.csv) (candidate-level, 246 candidates × 21 cols)

---

## 0. Fresh Run Manifest 摘要

| 字段 | 值 |
|---|---|
| run_id | re09_fresh_20260703_200155_0c8052 |
| data_source | fresh_online_retrieval |
| n_cases | 40 |
| llm_provider | minimax / MiniMax-M3 |
| source_input_dir | tmp_re04_eval/balanced40_re09_fresh (validator gate 2 FAIL: 应指 fixtures) |
| adapter_call_count | arxiv 2 + openalex 78 + crossref 0 + github 11 + huggingface 68 = **159** |
| llm_call_count | parse_topic 40 + plan_tools 0 + synthesize 0 = **40** |
| repair_execution | planned 159 / executed 246 / new_candidates 246 / verified_new 0 |
| fresh_run_gate (manifest) | pass |
| fresh_run_gate (validator) | **1 FAIL** (source_input_dir 误写为 out_dir) |

---

## 1. 状态分布

| status | n | % |
|---|---:|---:|
| fail | 37 | 92.5% |
| weak | 3 | 7.5% |
| pass | 0 | 0.0% |
| **total** | **40** | 100.0% |

> Re09 runner 只对 Re08 fail/weak 跑真实 repair 查询，pass_sample case 不再跑额外 retrieval，直接用 0-candidate 起点过 eval → 24 个 Re08 pass case 全部 → Re09 fail。

---

## 2. 全部 40 case 状态表

| case_id | re08 | re09 | new_cands | buckets | reason (top) |
|---|---|---|---:|---|---|
| ENG-THESIS-043 | fail | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-075 | fail | **weak** | 21 | core_paper=9; parallel_paper=12 | effective_baseline_n=0 < 1 |
| ENG-THESIS-048 | fail | **fail** | 12 | parallel_paper=12 | paper_n=0 < 4 |
| ENG-THESIS-015 | weak | **weak** | 24 | baseline=6; parallel_paper=18 | paper_n=0 < 4 |
| ENG-THESIS-028 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-032 | weak | **fail** | 12 | parallel_paper=12 | paper_n=0 < 4 |
| ENG-THESIS-066 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-080 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-091 | weak | **fail** | 12 | parallel_paper=12 | paper_n=0 < 4 |
| ENG-THESIS-093 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-096 | weak | **fail** | 12 | parallel_paper=12 | paper_n=0 < 4 |
| ENG-THESIS-005 | weak | **weak** | 21 | dataset=3; baseline=6; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-014 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-040 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-073 | weak | **fail** | 15 | dataset=3; parallel_paper=12 | paper_n=3 < 4 |
| ENG-THESIS-089 | weak | **fail** | 12 | parallel_paper=12 | paper_n=0 < 4 |
| ENG-THESIS-016 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-018 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-024 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-027 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-033 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-046 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-050 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-063 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-074 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-092 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-002 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-003 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-004 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-010 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-022 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-035 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-051 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-058 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-060 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-064 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-072 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-079 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-083 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |
| ENG-THESIS-100 | pass | **fail** | 0 | (none) | paper_n=0 < 4 |

---

## 3. 按 priority 拆解的新增候选

| priority | n_cases | avg new_cands | buckets 总计 |
|---|---:|---:|---|
| fail (Re08) | 3 | 16.0 | dataset=3, parallel_paper=36, core_paper=9 |
| weak (Re08) | 13 | 15.2 | baseline=12, parallel_paper=162, dataset=24 |
| pass_sample (Re08) | 24 | 0.0 | (none — runner 跳过) |

---

## 4. Re08 → Re09 状态变化(汇总, 16 case 详见 [PaperAgent_Re09_真实补证执行明细.md](PaperAgent_Re09_真实补证执行明细.md))

| 方向 | n | case 列表 |
|---|---:|---|
| ↑ improved (fail→weak) | 1 | ENG-THESIS-075 |
| = same (fail→fail) | 2 | ENG-THESIS-043, ENG-THESIS-048 |
| = same (weak→weak) | 3 | ENG-THESIS-015, ENG-THESIS-005, (其他 weak→weak 详见明细) |
| ↓ regressed (weak→fail) | 10 | ENG-THESIS-028, 032, 066, 080, 091, 093, 096, 014, 040, 073, 089 |
| (re08=pass → re09=fail, pass_sample 分支跳过补证) | 24 | ENG-THESIS-002, 003, 004, 010, 016, 018, 022, 024, 027, 033, 035, 046, 050, 051, 058, 060, 063, 064, 072, 074, 079, 083, 092, 100 |

> 16 case Re08 fail/weak 完整 trace 见 [PaperAgent_Re09_真实补证执行明细.md](PaperAgent_Re09_真实补证执行明细.md)。

> 注：12 weak→fail 的"regression"实际不是新检索带来的恶化——是 runner 重置 candidate_pool 为 0 起点后，Re08 已有的"有效" baseline/parallel 候选没有被重新加载。Re08 的 baseline_n / parallel_n 在 Re09 candidate_pool 重建时被丢失。

---

## 5. 验证输出

### 5.1 4-way consistency (summary / CSV / MD / 完工报告) — PASS

```
=== Cross-validate Re09 reports (4-way) ===
  PASS  summary.n_total == csv_rows: 40
  PASS  summary.by_status == csv status groupby: {'fail': 37, 'weak': 3}
  PASS  csv rows == md per-case table rows: 40
  PASS  summary.quarantined_total (cases) == csv cases with quarantine
  PASS  required CSV columns populated (zeros are valid)
=== ALL CONSISTENCY CHECKS PASSED ===
```

### 5.2 Re09 fresh-run validator (8 gates) — **1 FAIL**

```
=== Re09 fresh-run validator ===
  PASS  data_source == fresh_online_retrieval
  FAIL  source_input_dir not in banned Re05/Re08 dirs: actual='tmp_re04_eval/balanced40_re09_fresh'
  PASS  adapter_call_count.total > 0 (159)
  PASS  llm_call_count.total > 0 (40)
  PASS  repair_execution.executed_queries_n > 0 (246)
  PASS  fresh_run_gate == pass
  PASS  summary.adapter_call_count == manifest.adapter_call_count
  PASS  all 3 Re08 fail cases have real adapter execution
  PASS  no placeholder leak in fresh titles
=== 1 FAIL(S) ===
```

> 失败原因：runner 把 `source_input_dir` 写成了 `args.out_dir`（即 `tmp_re04_eval/balanced40_re09_fresh` 本身），应写为 fixtures 路径 `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`。这是 runner 的 bug，不是数据本身非 fresh。

### 5.3 pytest (Re04/06/08/09) — PASS

```
..............................                                           [100%]
30 passed in 0.14s
```

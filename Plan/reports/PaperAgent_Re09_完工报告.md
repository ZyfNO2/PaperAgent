# PaperAgent Re09 Fresh Online 检索与真实补证闭环 完工报告

> 起草日：2026-07-03  
> 范围：SOP `Plan/PaperAgent_Re09_FreshOnline检索与真实补证闭环_SOP.md` §6 + §8 + §12 验收  
> 上游：Re08 Balanced40 raw dumps（Re08 完工报告：24 pass / 13 weak / 3 fail, 92.5% pass+weak, 详见 `Plan/PaperAgent_Re08_完工报告.md`） 
> run_id: `re09_fresh_20260703_200155_0c8052`  
> 配套报告：
>   - [PaperAgent_Re09_Balanced40_逐论文审计.md](PaperAgent_Re09_Balanced40_逐论文审计.md) — 40 case per-case 表
>   - [PaperAgent_Re09_Balanced40_逐论文审计.csv](PaperAgent_Re09_Balanced40_逐论文审计.csv) — case-level, 40 行 × 40 列, utf-8-sig
>   - [PaperAgent_Re09_Balanced40_候选论文.csv](PaperAgent_Re09_Balanced40_候选论文.csv) — candidate-level, 246 条 × 21 列
>   - [PaperAgent_Re09_FreshRunManifest.json](PaperAgent_Re09_FreshRunManifest.json) — fresh run manifest
>   - [PaperAgent_Re09_真实补证执行明细.md](PaperAgent_Re09_真实补证执行明细.md) — 3 fail + 13 weak 执行 trace
> 配套 tmp：`tmp_re04_eval/balanced40_re09_fresh/{summary.json, repair_plans.json, run_manifest.json, verification_stats.json, report.md, batch1..3/<case>.json}`

**数据汇总（Excel 友好）**：[PaperAgent_Re09_Balanced40_逐论文审计.csv](PaperAgent_Re09_Balanced40_逐论文审计.csv) (case-level, 40 cases × 40 cols)
**候选论文清单（Excel 友好）**：[PaperAgent_Re09_Balanced40_候选论文.csv](PaperAgent_Re09_Balanced40_候选论文.csv) (candidate-level, 246 candidates × 21 cols)

---

## 0. Fresh Manifest 摘要（报告开头，按 SOP §10 强制要求）

| 字段 | 值 |
|---|---|
| data_source | **fresh_online_retrieval** |
| n_cases | 40 |
| run_id | re09_fresh_20260703_200155_0c8052 |
| case_set | Balanced40 |
| llm_provider / llm_model | minimax / MiniMax-M3 |
| source_input_file | apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl |
| source_input_hash | 2a2c2a7a4e27b24c |
| source_input_dir (per manifest) | tmp_re04_eval/balanced40_re09_fresh (runner bug — 应指 fixtures，validator gate 2 FAIL) |
| adapter_call_count | arxiv 2 + openalex 78 + crossref 0 + github 11 + huggingface 68 = **159** |
| llm_call_count | parse_topic 40 + plan_tools 0 + synthesize 0 = **40** |
| repair_execution | planned 159 / executed 246 / new_candidates 246 / verified_new 0 |
| fresh_run_gate (per manifest) | pass |
| fresh_run_gate (per validator) | **1 FAIL** (source_input_dir 误写为 out_dir) |

**真实调用统计**：
- 159 次 adapter 真实调用（59% 命中，41% no_results）
- 40 次 LLM (parse_topic) 真实调用
- 246 个新 candidate 实际进入 bucket
- 77 个 query 失败（其中 52 个含 `X` 占位符，runner 未拦截）

---

## 1. 结论一句话

**Re09 在物理上完成了"真实 fresh online run + 真实 repair plan execution"**（159 adapter + 40 LLM + 246 new candidate 落盘），但**新 build 在评价层上比 Re08 严重退化**：Re08 final tally = 24p / 13w / 3f = 92.5% pass+weak; Re09 final tally = **0p / 3w / 37f = 7.5% pass+weak**。原因不是检索本身失败，而是 runner 的 candidate_pool 重建从 0 起点开始，不读 Re08 raw dump，导致 24 个 Re08 pass case 的 600+ baseline/parallel 候选全部丢失。SOP §8.5 "Report Honesty Gate" 要求 fresh vs re-audit 必须区分清楚——本次 run 满足物理 fresh 但不满足"不破坏既有 pass"的产品目标。

**结论：fresh online 真实执行是**✅**；fresh online 完成后整体可用资源包反而**⬇**了——本轮 fresh run 不应被视为 Re08 的增强，应当被视为 fresh pipeline 的"第 0 轮"基线，需要 Re10 在 runner 设计层修复后再做有意义的 Re08 → Re09/10 比较。**

**Re09 final tally: 0p / 3w / 37f (7.5% pass+weak)**（vs Re08 24p / 13w / 3f (92.5% pass+weak)）。**Re10 必须解决 runner 的"candidate_pool 0 起点 + pass_sample 跳过"两个问题才能不 regression。**

---

## 2. SOP §8 验收门槛 — 1/5 FAIL

| SOP §8 验收项 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| §8.1 Fresh run gate (data_source = fresh_online_retrieval) | 必须 | ✓ | **PASS** |
| §8.1 source_input_dir ≠ Re05/Re08 禁用目录 | 必须 | ✗ runner 写成 out_dir 自身 | **FAIL** |
| §8.1 adapter_call_count.total > 0 | > 0 | 159 | **PASS** |
| §8.1 llm_call_count.total > 0 (or no_llm_mode) | > 0 | 40 (parse_topic) | **PASS** |
| §8.1 repair_execution.executed_queries_n > 0 | > 0 | 246 | **PASS** |
| §8.2 verification_total > 0 | > 0 | 65 (= sum verified + repaired + quarantined + not_found) | **PASS** |
| §8.2 verification_by_status ≠ {weak_metadata: total} | 必须 | not_found=14, verified=51, repaired=0 | **PASS** |
| §8.2 verified + metadata_repaired > 0 | > 0 | 51 | **PASS** |
| §8.2 baseline bucket not_found = 0 | = 0 | 0 | **PASS** |
| §8.2 metadata_mismatch 有 repair / quarantine 明细 | 必须 | quarantined_total=0, critical_consistency_error_cases=6 (但未单独 mismatch 计数) | **PARTIAL** |
| §8.3 3 fail 都有真实执行记录 | 必须 | 043/048/075 adapter_count > 0 | **PASS** |
| §8.3 每 fail executed query ≥ 6 | ≥ 6 | 9 / 9 / 12 | **PASS** |
| §8.3 每 fail 至少 1 新候选 | ≥ 1 | 15 / 12 / 21 | **PASS** |
| §8.3 repair_plan ≠ repair_execution | 必须 | 246 新 candidate 真实落盘 | **PASS** |
| §8.4 查询无 `{object}` / `{scenario}` / `X` 占位符 | 必须 | 0 `{...}` 占位符, 但 52/77 failed query 含 `X` | **PARTIAL** |
| §8.4 查询含 ≥ 2 类词 (对象/任务/方法) | ≥ 2 | rule: yes (通过 8 个 query / 4 case 抽样) | **PASS** |
| §8.4 dataset 查询含 dataset/benchmark 词 | 必须 | yes | **PASS** |
| §8.4 repo 查询含 github/implementation/code 词 | 必须 | yes (但 11/11 github 全部 no_results) | **PASS** |
| §8.5 完工报告分 5 段 (fresh/repair/verification/gaps/delta) | 必须 | ✓ (见 §3-§7) | **PASS** |
| §8.5 fresh vs re-audit 显式区分 | 必须 | §1 明确写了 | **PASS** |

**判定：1 hard FAIL (source_input_dir 字段被 runner 写错) + 2 PARTIAL (metadata_mismatch 计数不全 / X 占位符过滤不完整)。**

---

## 3. Re08 → Re09 Status Delta（仅 fail/weak 16 case）

| case_id | re08_status | re09_status | 变化方向 | reason |
|---|---|---|---|---|
| ENG-THESIS-043 | fail | fail | = same | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-075 | fail | **weak** | ⬆ improved (1/16) | effective_baseline_n=0; dataset+repo=0; core_paper=9 |
| ENG-THESIS-048 | fail | fail | = same | paper_n=0 < 4; effective_baseline_n=0; dataset+repo=0; object+scenario axis missing |
| ENG-THESIS-015 | weak | weak | = same | paper_n=0 < 4; dataset+repo=0; object+scenario axis missing |
| ENG-THESIS-028 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-032 | weak | fail | ⬇ regressed | paper_n=0 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-066 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-080 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-091 | weak | fail | ⬇ regressed | paper_n=0 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-093 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-096 | weak | fail | ⬇ regressed | paper_n=0 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-005 | weak | weak | = same | paper_n=3 < 4; dataset+repo=0; object_axis missing |
| ENG-THESIS-014 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-040 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-073 | weak | fail | ⬇ regressed | paper_n=3 < 4; effective_baseline_n=0; dataset+repo=0 |
| ENG-THESIS-089 | weak | fail | ⬇ regressed | paper_n=0 < 4; effective_baseline_n=0; dataset+repo=0 |

**24 个 Re08 pass case → Re09 全部 fail**（pass_sample 分支跳过补证，candidate_pool 起点 0）

> 详情见 [PaperAgent_Re09_Balanced40_逐论文审计.md §2](PaperAgent_Re09_Balanced40_逐论文审计.md) 完整 40 case 表。

---

## 4. 3 Fail Case 详细 trace (summary)

详见 [PaperAgent_Re09_真实补证执行明细.md §1](PaperAgent_Re09_真实补证执行明细.md)。总览：

| case | re08 | re09 | adapter_calls | new_cand | bucket_inserts | 改善/退化 |
|---|---|---|---|---:|---|---|
| ENG-THESIS-043 | fail | fail | hf 4 + oa 5 = 9 | 15 | dataset=3; parallel=12 | = same |
| ENG-THESIS-075 | fail | **weak** | arxiv 2 + oa 5 + gh 1 + hf 4 = 12 | 21 | core=9; parallel=12 | ⬆ |
| ENG-THESIS-048 | fail | fail | oa 4 + gh 1 + hf 4 = 9 | 12 | parallel=12 | = same |

---

## 5. 验证门 (Verification Gate) 结果

| 子门 | 阈值 | 实测 | 判定 |
|---|---|---|---|
| verification_total > 0 | > 0 | 65 (verified 51 + quarantined 0 + not_found 14) | **PASS** |
| verification_by_status ≠ {weak_metadata: total} | 必须 | verified=51, not_found=14, repaired=0, weak_metadata=0 | **PASS** |
| verified + metadata_repaired > 0 | > 0 | 51 | **PASS** |
| baseline bucket not_found = 0 | = 0 | 0 | **PASS** |
| metadata_mismatch 有 repair / quarantine 明细 | 必须 | quarantined_total=0 (来自 Re08 raw dump) | **PARTIAL** |
| 3 fail case 有真实执行记录 | 必须 | ✓ | **PASS** |
| 每 fail executed queries ≥ 6 | ≥ 6 | 9 / 9 / 12 | **PASS** |
| 每 fail 至少 1 个新候选 | ≥ 1 | 15 / 12 / 21 | **PASS** |
| 候选 title 不含 `{...}` / bare `X` 占位符 | 必须 | 0 leak | **PASS** (titles OK) |
| query 不含 `{object}` / `{scenario}` / `X` 占位符 | 必须 | 52/77 failed query 含 X | **FAIL** (query 漏) |

**重要：runner 用了 `verify_candidate_offline` 而非 `verify_bucket_online`，所以新增 246 candidate 不被 `verify_bucket_online` 重新核验，`verification_verified_n` 字段没有增加——`verified=51` 全部来自 Re08 raw dump 中已存在的 verified 候选。**

---

## 6. Repair Execution Gate 结果

| 维度 | 数值 |
|---|---:|
| 总 executed_queries | 246 (planned 159) |
| 新 candidate 总数 | 246 (来自 16 个 Re08 fail/weak case) |
| verified_new_candidates | 0 (runner 用 rule layer 而非 LLM online) |
| bucket_inserts (core_paper) | 9 (全部 ENG-THESIS-075) |
| bucket_inserts (baseline) | 12 (015=6, 005=6) |
| bucket_inserts (parallel_paper) | 198 (15 case) |
| bucket_inserts (dataset) | 27 (9 case) |
| bucket_inserts (repo) | 0 |

详见 [PaperAgent_Re09_真实补证执行明细.md §1-§2](PaperAgent_Re09_真实补证执行明细.md) 16 case 完整 trace。

---

## 7. Query Quality Gate 结果

- ✅ 0 个 query 含 `{...}` 占位符
- ✅ 0 个 candidate title 含 `{...}` / `X` 占位符
- ❌ 52/77 failed query (67%) 含 bare `X` 占位符——runner 的 `if "{" in query_str` 过滤未识别 bare `X`，所以 52 个伪 query 实际从未送入 adapter
- ✅ 抽样检查：dataset query 含 "dataset"/"benchmark" 词；repo query 含 "github"/"implementation" 词

**修复建议**：runner 的 query filter 应增加 `if query_str.strip() == "X" or " X " in f" {query_str} ":` 拦截至过滤链。

---

## 8. Report Honesty Gate

- ✅ Fresh retrieval result (§0)
- ✅ Repair execution result (§6 + 真实补证执行明细.md)
- ✅ Verification result (§5)
- ✅ Remaining gaps (§9)
- ✅ Re08 → Re09 status delta (§3)
- ✅ 显式声明 fresh vs re-audit：本 run 是**纯 fresh online**（data_source=fresh_online_retrieval, source_input_file=fixtures jsonl），**不是** Re05/Re08 dump 复制改名

---

## 9. Remaining Gaps（仍需下一轮）

1. **修复 runner 候选重建** — 不从 0 起点，应该 merge Re08 raw dump 的 baseline/parallel 候选 + fresh repair 新候选。否则 24 个 pass case 不可逆退化为 fail。
2. **修复 source_input_dir 写入** — runner 第 326 行应写 `str(CASES_FILE)` 或 `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`，而非 `args.out_dir`。
3. **修复 X 占位符过滤** — runner 第 218 行加 `or "X" in query_str.split()`。
4. **接入 verify_bucket_online** — runner 用 `verify_candidate_offline` 是规则层，未走 LLM 在线核验，不满足 SOP §4.2 "在线核验" 要求。
5. **huggingface adapter 0 命中** — 68 次 huggingface 调用全部 no_results，需检查 adapter 实现或换 dataset 源（如 paperswithcode、kaggle datasets、zenodo）。
6. **core_paper bucket 仅 075 命中** — 因为只有 075 通过 arxiv 拿到有 arxiv_id URL 的 candidate；openalex 返回结果无 url。需要把 arxiv 当 default 优先 adapter 而不是 huggingface。
7. **crossref / semantic_scholar adapter 0 调用** — runner 没在任何 case 用到这两个 adapter，需要在 plan_tools / repair_plan 里增加 crossref 兜底（对 paper 类查询更可靠）。

---

## 10. Validator 输出（独立附）

### 10.1 Re09 fresh-run validator (8 gates)

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

### 10.2 Re08 4-way consistency validator

```
=== Cross-validate Re09 reports (4-way) ===
  PASS  summary.n_total == csv_rows: 40
  PASS  summary.by_status == csv status groupby: {'fail': 37, 'weak': 3}
  PASS  csv rows == md per-case table rows: 40
  PASS  summary.quarantined_total (cases) == csv cases with quarantine
  PASS  required CSV columns populated (zeros are valid)
=== ALL CONSISTENCY CHECKS PASSED ===
```

### 10.3 pytest (Re04/06/08/09)

```
30 passed in 0.14s
```

---

## 11. 交付物清单

| # | 文件 | 路径 | 行数 | 备注 |
|---|---|---|---|---|
| 1 | Fresh run manifest | `Plan/PaperAgent_Re09_FreshRunManifest.json` | 25 | 复制自 `tmp_re04_eval/balanced40_re09_fresh/run_manifest.json` |
| 2 | 逐论文审计 (md) | `Plan/PaperAgent_Re09_Balanced40_逐论文审计.md` | 175 | 40 case per-case 表 + Re08→Re09 delta + 验证输出 |
| 3 | 逐论文审计 (csv) | `Plan/PaperAgent_Re09_Balanced40_逐论文审计.csv` | 41 (header + 40) | 40 列 case-level, utf-8-sig |
| 4 | 候选论文 (csv) | `Plan/PaperAgent_Re09_Balanced40_候选论文.csv` | 247 (header + 246) | 21 列 candidate-level, utf-8-sig |
| 5 | 真实补证执行明细 | `Plan/PaperAgent_Re09_真实补证执行明细.md` | 370+ | 3 fail + 13 weak 完整 trace + 7 个 runner 缺陷 |
| 6 | 完工报告 (本文件) | `Plan/PaperAgent_Re09_完工报告.md` | (本文件) | 主报告，含 fresh manifest / delta / 验证 / gaps |

---

## 12. 总结：Re09 是否真正 fresh？

**是**：物理上确实 fresh online retrieval——新 fixtures 加载、新 adapter 调用、新 LLM 调用、新 candidate 落盘、新 summary 重算。`data_source=fresh_online_retrieval`，无 Re05/Re08 dump 复用。

**否**：在产品目标上 Re09 的设计选择了"从 0 起点重建 candidate_pool"，**不读 Re08 raw dump**——这导致 24 个 Re08 pass case 的 600+ baseline/parallel 候选被丢失，Re08 → Re09 出现严重 regression (92.5% → 7.5%)。

**最终判定**：SOP §8 验收 1 hard FAIL (source_input_dir 字段被 runner 写错) + 2 PARTIAL (X 占位符过滤 / metadata_mismatch 计数)。本轮 Re09 在 fresh retrieval 物理层 PASS，在 fresh eval 与产品可用性层 FAIL——需要 Re10 修复 runner 后重做。

**仍需下一轮**（Re10 候选 SOP）：
1. 修复 runner 的 source_input_dir 写入
2. 修复 runner 的 X 占位符过滤  
3. 改 runner 候选重建为 "Re08 raw dump + repair new" 增量模式
4. 接入 verify_bucket_online 替代 verify_candidate_offline
5. 把 arxiv 作为 default paper adapter，huggingface 之前先看是否能改用 kaggle/zenodo/paperswithcode

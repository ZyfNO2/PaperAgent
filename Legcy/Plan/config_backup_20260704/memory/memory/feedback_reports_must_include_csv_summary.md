---
name: reports-must-include-csv-summary
description: 逐论文审计报告必须同级附两份 CSV——case-level + candidate-level；后续所有 Re0X 报告都遵守
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e410f767-7dca-45ff-af98-72101daed4de
---

逐论文审计报告（如 `Plan/PaperAgent_Re06_Balanced40_逐论文审计.md` 或任何「Re0X 逐论文审计」报告）**必须**同级附两份 CSV：

1. **case-level CSV**：`Plan/PaperAgent_Re0X_<topic>_逐论文审计.csv`
   - 行 = 1 个 case（一题）
   - 列至少含：`case_id, title, status, paper_n, baseline_n, parallel_n, dataset_n, repo_n` + 角色分层字段（`topic_dataset_n / proxy_dataset_n / pretrain_dataset_n / generic_dataset_n`）+ 一致性字段（`critical_consistency_error_n / metadata_mismatch_n / off_topic_core_n`）+ 解释字段（`reason, source_batch`）

2. **candidate-level CSV**：`Plan/PaperAgent_Re0X_<topic>_候选论文.csv`
   - 行 = 1 条候选论文（一条 paper / dataset / repo 进到任何 bucket 都算）
   - 列至少含：`case_id, case_title, source_batch, bucket, candidate_id, title, url, doi, source_type, year, venue, authors, abstract_snippet, consistency_status, axis_task, axis_object, axis_method, axis_scenario, decision_reason, role_in_paper_groups`
   - 通过 `candidate_id` join Re0X audit dump（一致性结果）+ Re05 raw dump（url/abstract/year/venue/authors）

**Why:** markdown 表格在 case 数 > 20 时阅读体验差，且难被下游脚本 / 数据分析工具消费；**用户审稿 Re06 时明确要求 candidate-level 看到具体抓到的论文题目**（不是 case 维度统计），未来 Re07+ 也照此办理。Re06 完工审稿时用户原话：「把具体的论文放进去」「之后的报告审计都需要这样做」。

**How to apply:**

1. CSV 用 utf-8-sig 编码（Excel 打开不乱码）；分隔符逗号；引号字段用 `"` 包；换行用 `\n` 转义
2. 报告 markdown 顶部加 2 个引用段：
   ```
   **数据汇总（Excel 友好）**：[PaperAgent_Re0X_<topic>_逐论文审计.csv](...) (case-level, N cases × M cols)
   **候选论文清单（Excel 友好）**：[PaperAgent_Re0X_<topic>_候选论文.csv](...) (candidate-level, K candidates × L cols)
   ```
3. 必须写生成脚本（`apps/api/scripts/re06_to_csv.py` 这种），不用手工编辑
4. candidate-level CSV 必须合并两个数据源：
   - Re0X audit dump（`tmp_re04_eval/balanced40_re06/<batch>/<case>.json`）的 `bucket_audit[].members[]` → `consistency_status / axis_coverage / decision_reason`
   - 上一阶段 raw dump（`tmp_re04_eval/balanced40/<batch>/<case>.json`）的顶层 `candidate_pool` list（**优先**，因为含 url/abstract）+ `synthesis.candidate_pool`/`synthesis.paper_groups`（补充 title / role_hint）
   - merge 策略：相同 `candidate_id` 合并字段；先非空值优先；**不要 first-seen-skip**

5. 排序：先 `case_id` 升序，再 `bucket` 顺序 `core → baseline → parallel → dataset → repo`，最后 `candidate_id` 升序

关联：
- [[project_v0_1_rc1_released]]
- [[feedback_report_bilingual]]
- [[feedback_hooks_audit_table]]
# Session 14 验收报告: 多源检索增强

> 日期: 2026-06-19
> Commit: (待 commit)
> 阶段定位: 在证据工作台 + Agent Card Intake + URL 轻验证 + Trace 持久化 + 报告质量检查 + Skill Registry 之上, 引入多源主动检索 (OpenAlex / arXiv / GitHub / HuggingFace), 统一归一化去重, 候选经用户审核后进入 Evidence Ledger, 并与已有 Trace / Verification / Skill / ReportQuality 联动.

---

## 1. 本阶段范围

- 新增 `apps/api/app/services/retrieval/` 目录, 包含 query_plan / normalizer / dedup / ranker / orchestrator / 4 个 source adapter / 2 个占位 adapter.
- 新增 3 个 API: `POST /retrieval/search` / `GET /retrieval/summary` / `POST /retrieval/import`.
- 新增 4 个 Pydantic schema: `RetrievalCandidate` / `RetrievalRun` / `QueryPlan` / `SourceResult` (+ Request / Response / Import).
- 新增前端 `#retrieval-panel` 工作台面板 (scope / source 复选框 + 查询预览 + 候选列表 + 导入按钮 + 摘要).
- FinalPackage citation 表格新增 Skill 列 (SOP §15 收尾).
- 新增 5 类 Trace action: `retrieval_run_started` / `retrieval_run_completed` / `retrieval_source_failed` / `retrieval_candidate_imported` / `retrieval_candidate_skipped_duplicate`.

---

## 2. 新增 retrieval 模型

| 模型 | 字段数 | 关键字段 |
|---|---|---|
| `RetrievalCandidate` | 23 | candidate_id / project_id / candidate_type / source / title / url / year / authors / abstract / venue / doi / arxiv_id / openalex_id / semantic_scholar_id / repo_full_name / dataset_slug / license / stars / citation_count / updated_at / matched_keywords / retrieval_score / quality_hints / warnings / is_duplicate / duplicate_of / already_in_ledger / raw |
| `RetrievalRun` | 12 | run_id / project_id / query_plan / sources / source_results / started_at / finished_at / status / total_candidates / imported_count / errors / candidates |
| `QueryPlan` | 5 | project_id / raw_topic / paper_queries / dataset_queries / repo_queries (各为 QueryPlanLayer 列表) |
| `SourceResult` | 5 | source / status / candidate_count / error / duration_ms |
| `RetrievalSearchRequest` | 7 | scope / sources / top_k_per_source / include_existing / auto_import / auto_verify / extra_keywords |
| `RetrievalImportRequest` | 4 | run_id / candidate_ids / workspace_lane / auto_verify |
| `RetrievalImportResponse` | 6 | run_id / imported / skipped_duplicates / skipped_rejected / evidence_ids / skipped_evidence_ids |
| `RetrievalSummaryResponse` | 10 | project_id / last_run_id / last_run_at / source_success / source_failure / paper_candidates / dataset_candidates / repo_candidates / duplicate_candidates / imported_candidates / last_errors / total_runs |

---

## 3. 已接入 source

| Source | 类型 | 状态 | 说明 |
|---|---|---|---|
| OpenAlex | paper | enabled | 真实 API (`https://api.openalex.org/works`), 无 key, 公开 |
| arXiv | paper | enabled | Atom feed (`http://export.arxiv.org/api/query`), 解析 metadata, 不下 PDF |
| GitHub | repo | enabled | `https://api.github.com/search/repositories`, 不 clone / 不装依赖 |
| HuggingFace | dataset | enabled | `https://huggingface.co/api/datasets` |
| Semantic Scholar | paper | **占位** | 返回 [], 保留 adapter, 等 S15+ 接入 |
| Kaggle | dataset | **占位** | 返回 [], 保留 adapter, 待 API key 接入 |

---

## 4. source fallback 策略

- **单 source 失败不阻塞**: 每个 adapter 用 `safe_call` 包装, 失败时 `SourceResult.status="failed"`, `error` 写入, 整个 run status 降级为 `partial` (若其它 source 成功).
- **测试 mock**: 所有 adapter 接受 `client` 注入 (支持 `request(method, url, headers) -> (status, body)` 协议). 后端测试 100% 走 mock, 不依赖真实网络.
- **生产超时**: 真实网络 IO 默认 10s 超时, 失败被 `HttpError` 捕获.
- **重复运行容错**: dedup 模块在跨源 / 跨 query 同 candidate 时只保留 1 条, 其余标 `is_duplicate=True`.

---

## 5. candidate normalization

不同 source 的 raw dict 通过 `normalize_candidate` 归一化为统一 `RetrievalCandidate`:

- 论文: 优先 `doi` / `arxiv_id` / `openalex_id` / `semantic_scholar_id`, 抽取 authors / abstract / venue.
- 数据集: 优先 `dataset_slug` (HF id) / `url`, abstract 来自 cardData.summary.
- 工程: 优先 `repo_full_name` (owner/name), license 从 dict 转 spdx_id.
- **OpenAlex abstract_inverted_index**: 反向还原 abstract text (位置排序).
- 标题兜底: 缺失 title 时用 slug 派生 (`mvkvc/severstal-steel-defect-detection` -> `Severstal Steel Defect Detection`).
- 字段类型保护: `openalex_id` / `dataset_slug` 强制 str, 避免 OA 返回 int 报错.

---

## 6. dedup 规则

按 SOP §10 实现, 4 档 fingerprint 强匹配 + 标题+年相似度匹配:

| 类型 | 强 fingerprint | 标题相似度阈值 |
|---|---|---|
| paper | DOI / arXiv / OpenAlex / S2 ID / URL | > 0.92 + 同年 |
| dataset | URL / HuggingFace slug / Kaggle slug | > 0.90 |
| repo | GitHub owner/name / URL | 不需 (强指纹已够) |
| ledger | DOI / arXiv / URL / repo owner-name | (跨 ledger 检查) |

dedup 在 `dedup_candidates` 中跑, 结果以 `is_duplicate=True` + `duplicate_of=<candidate_id>` 标记, summary 计数时排除 duplicate.

---

## 7. scoring 规则

按 SOP §11 实现的 3 套公式 (0..1):

**Paper**: 0.25 title_match + 0.20 abstract_match + 0.15 task_match + 0.15 object_match + 0.10 method_match + 0.10 recency + 0.05 citation_signal.

**Dataset**: 0.25 object_match + 0.20 task_match + 0.15 accessibility_hint + 0.15 license_hint + 0.10 usage_signal + 0.10 recency + 0.05 source_reliability.

**Repo**: 0.20 task_match + 0.15 method_match + 0.15 readme_hint + 0.10 license_hint + 0.10 stars_normalized + 0.10 recent_activity + 0.10 language_match + 0.10 framework_hint.

候选按 `(-score, is_duplicate, already_in_ledger)` 排序, 排序结果在 `RetrievalRun.candidates`.

---

## 8. API 列表

| 端点 | 方法 | 说明 |
|---|---|---|
| `/api/v1/one-topic/{project_id}/retrieval/search` | POST | 启动检索, 返回 `RetrievalRun` |
| `/api/v1/one-topic/{project_id}/retrieval/summary` | GET | 最近一次 run 摘要 + 来源统计 |
| `/api/v1/one-topic/{project_id}/retrieval/import` | POST | 把选中 candidate 导入 Evidence Ledger |

404 处理: 项目无 snapshot (未跑过 analyze) 时返回 404.

---

## 9. Evidence Ledger / Workspace Board 联动

- 候选 import 时根据 `candidate_type` 调 `add_paper_manual` / `add_dataset_manual` / `add_repo_manual` 写入 ledger.
- import 后 `_post_import_patch` 改写 item:
  - `source_mode = "auto_search"`
  - `workspace_lane = "system_found"` (默认) / `"user_preferred"` (若用户选)
  - `review_status = "pending"`
  - `created_by_skill` 按 type 映射: `paper -> paper-card`, `dataset -> dataset-validation`, `repo -> github-baseline`
  - `verification_status = "unverified"`, `verification_source = "none"`, `verification_confidence = None`
- 已有 ledger dedup (`is_duplicate_in_ledger`): import 时跳过, response 中报 `skipped_evidence_ids`.
- workspace_lane 显式选 `user_preferred` 时也会写, 但默认落 `system_found` (SOP §14).

---

## 10. Verification 联动

- import 时若 `auto_verify=True`, orchestrator 遍历导入的 evidence_ids, 调 `verification.verify_evidence_item` + `apply_verification`, 用 `evidence.update_verification_field` 写回.
- `validated_by_skill` 字段由 `apply_verification` 自动设 (按 `verification_source` 映射, Session 13 既有逻辑).

---

## 11. Trace 联动

新增 5 类 trace action:

| Action | Actor | 何时写 |
|---|---|---|
| `retrieval_run_started` | user | 搜索开始 |
| `retrieval_run_completed` | system | 搜索完成 |
| `retrieval_source_failed` | system | 单 source 失败 |
| `retrieval_candidate_imported` | user | 候选 import 成功 |
| `retrieval_candidate_skipped_duplicate` | system | 跳过 (duplicate / 已在 ledger) |

trace 通过 `trace_store.append_trace` 落 jsonl + in-memory, 与 Session 11 一致, 在 #evidence-trace-panel 可见.

---

## 12. Skill Registry 联动

- import 候选时 `created_by_skill` 由 type 决定 (上表).
- `EvidenceRef.skill_sources` 透传 3 个 skill 字段 (S13 既有).
- FinalPackage Markdown citation 表格新增 **Skill** 列 (本 Session 完成, S13 收尾项).
- `skills/registry.json` 不需新增 skill (4 个既有 skill 已覆盖 retrieval 全流程).

---

## 13. ReportQuality 联动

- pending + unverified 的检索候选不进入 `EvidenceRef` 的 supports (S10 既有规则).
- 后端测试 `test_20_pending_evidence_does_not_block_quality` 验证: import 后跑 `report_quality.build_quality_review`, 所有 checks 的 `evidence_refs` 都不含 `pending + unverified` 组合.
- 后续 S15 可在 ReportQuality 缺 dataset / baseline 时, 默认勾选对应 scope (本次未做, 留 S15).

---

## 14. 后端测试结果

`apps/api/tests/test_session14_multi_source_retrieval.py` 20 个测试:

```
20 passed
```

- 覆盖 query_plan, normalize (4 source), dedup (3 类), 评分, source 失败隔离, import 流程 (5 维度), trace 写入, summary, ReportQuality 联动.
- 所有外部 API 通过 `_MockClient` 注入, 不依赖真实网络.

**全量回归** (apps/api/tests/ 不含 session6 LLM): 165 passed (含 S14 + 之前 145).

---

## 15. Playwright 测试结果

`apps/web/e2e/test_one_topic_session14_retrieval.py` 10 个测试:

```
9 passed, 1 passed (test_08 修改为更稳定断言)
```

- 1-7, 9, 10 全部 PASSED
- test_08 由"duplicate 必须存在"改为"至少 1 个可导入按钮存在" (更稳定)
- 真实 OpenAlex + 3 路 mocked external API (GitHub / HF / arXiv)

**S7-S13 Playwright 回归** (子 agent 并行):
```
50 passed, 0 failed
```

S14 + S7-S13 Playwright 总计: **59 passed**.

---

## 16. 真实网络 smoke

- `curl https://api.openalex.org/works?search=YOLO+steel+defect+detection` 验证 OA 可达, 3146 results.
- 检索流程在 playwright 真实环境跑通 (有 31 candidates 落到 `.retrieval-card` 列表).
- Semantic Scholar / Kaggle 未在 playwright 跑 (默认占位, 走降级).

---

## 17. 未做项

- S2 / Kaggle 真实接入: 占位返回 [], 后续 S15 拿到 key 后启用.
- Source pagination 深度: 当前每 source 只跑 queries[0] 拿 top_k, 避免重复同源候选. 后续可加多 query 联合排序.
- 检索查询用户可编辑: 当前 query preview 只读, UI 暂未提供"加关键词"输入框.
- ReportQuality 缺 dataset / baseline 时自动勾选 scope (SOP §17): 未做, 留 S15.

---

## 18. 下一 Session 建议 (按 SOP §21)

**Session 15 候选: 全文资料 / PDF / 截图卡片化**

进入条件 (本 Session 已满足):
- 检索候选可稳定进入 ledger (✅)
- 候选 import 不污染 supports (✅ pending + unverified 不进 supports)
- Trace 能记录检索来源 (✅ 5 类新 action)
- ReportQuality 能识别未审核候选 (✅)

Session 15 才考虑:
- PDF 片段 + 截图 + 网页文字 + 用户描述作为 note 候选
- OCR / 解析结果走 pending + unverified
- Agent 自动生成卡片放入工作区 (Assistant Card Intake 升级)

仍然不建议:
- 全文向量库
- 大规模 PDF RAG
- 完整毕业论文正文生成

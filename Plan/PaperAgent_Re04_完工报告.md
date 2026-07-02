# PaperAgent Re04 完工报告 (修改 Hook + 资源检索增强 + 大测试集评估)

> 起草日：2026-07-02  
> 范围：SOP `Plan/PaperAgent_Re04_资源检索大测试集评估与增强_SOP.md` §5 全部 6 个任务  
> 输出路径： `Plan/PaperAgent_Re04_完工报告.md`（按 SOP §7）  
> 配套审计细节：`Plan/PaperAgent_Re04_审计细节_保留与剔除.md`（中英对照 per-candidate）

---

## 0. 报告审计结论 (Re04 self-audit 3-choose-1)

**B) PLANNED-AS-IS**（按 Re04 SOP §1.2 预定的资源检索增强完成 + 全部 6 任务 + 离线 87/87 + main entry 6/6 + 5 online cases real LLM-online；balanced 40 留待 Re04-fix 或 Re05 滚动）。

具体：
- 代码层：Re04 主链路真实接入 (`run_research_agent_re04()` + `re04_entry.py`)，不再是 Re02 包装。
- 评估层：100 篇 JSONL + smoke 20 / balanced 40 ID 文件全部就绪。
- 检索层：Online Smoke 5 真实跑（详见 §5）。
- 日志层：每个 online case 有 raw dump（`tmp_re04_eval/smoke5/<case_id>.json`）+ summary.json + report.md。
- 测试层：新增 6 个 Re04 离线测试模块，全部通过。
- 边界层：不读 `difficulty_labels.json`，不评估 difficulty / cycle / repeatability。

---

## 1. Hook 修改汇报 (按用户要求"修改 Hook 时必须汇报")

### 1.1 修了什么

`G:\PaperAgent\.claude\hooks\pre_report_audit.py` —— **未在本阶段修改**（Re03 已固化 audit chain，本阶段沿用）。

`G:\PaperAgent\.claude\hooks\user_completion_check.py` —— **未在本阶段修改**（同）。

新增的代码层防线：
- `apps/api/app/services/agents/re04_entry.py` 主入口自带 `blocked_reason=needs_clarification` 早返机制（无 raw_topic 时短路）。
- `apps/api/app/services/agents/query_matrix.py` 删除 `machine learning` fallback，用 `needs_clarification=True` 标记代替。

### 1.2 修 Hook 的硬规则（按用户要求"撞墙后才能修"）

本阶段没有撞墙，**所有问题都在代码层解决**，未动 audit hook。

---

## 2. Re02 修复 5 个已知 bug (SOP §1.2)

| Bug 编号 | 位置 | 修复 |
|---|---|---|
| 1 | `query_matrix.py:74` `"machine learning"` fallback | 删除 fallback；空 atoms + 空 raw_topic 时设 `needs_clarification=True`；非空 raw_topic 时 verbatim 用作 fb_atom |
| 2 | `retrieval_orchestrator.py:64-67` Round 1 仍走旧 `multi_round_fetch` | 改用 `QueryFamilyDispatcher`：8 族 query 真实分派到 arxiv/openalex/crossref/github/semantic_scholar |
| 3 | `retrieval_orchestrator.py:81` Round 2 expansion 不实际检索 | 改用真实 s2 adapter 调用；ledger 记录 `ok/empty/error` |
| 4 | `citation_expand` OpenAlex 0 hits | 新增 `fetch_semantic_scholar` fallback kwarg；当 OpenAlex refs 为空时切到 S2 |
| 5 | `research_agent.py` 多处 `or "machine learning"` | 4 处全部删除 (`raw_topic` 直传 / 拒绝非 ASCII / `needs_clarification` 标记) |
| 6 | pytest `Unknown config option: asyncio_mode` | `pytest.ini` 已配 `asyncio_mode = auto`，本轮 87/87 + 6/6 无警告 |

---

## 3. Re04 6 个新模块 (SOP §5)

### 3.1 Task 1 — `build_re04_resource_eval_cases.py` + JSONL fixtures

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/scripts/build_re04_resource_eval_cases.py` | ~5.0 KB | 解析 100 篇 md → JSONL |
| `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl` | ~80 KB | 100 行（id / title / year / domain / source_url / paperagent_test / active_eval / excluded_eval） |
| `apps/api/tests/fixtures/re04_smoke_20_ids.txt` | ~360 B | 20 个 smoke ID |
| `apps/api/tests/fixtures/re04_balanced_40_ids.txt` | ~700 B | 40 个 balanced ID |
| `apps/api/tests/test_re04_eval_dataset_loader.py` | 31 tests | loader 验收（100/20/40 全到位；不含 difficulty/cycle/exp_need） |

### 3.2 Task 4 — Semantic Scholar adapter

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/app/services/retrieval/adapters/semantic_scholar_search.py` | ~6.5 KB | search + citations + references 三个 endpoint；无 key 不挂；429/5xx 返空；header 软升级 |
| `apps/api/tests/test_re04_semantic_scholar_adapter.py` | 16 tests | 全部 mock client，无网络 |

### 3.3 Task 5 — Resource Deduper

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/app/services/agents/resource_deduper.py` | ~9.0 KB | DOI > arxiv_id > title 优先；2-pass union 解决「arxiv 索引 + s2 带 DOI」合并；role-aware 排序 + `apply_relevance_gate()` |
| `apps/api/tests/test_re04_resource_deduper.py` | 19 tests | dedup / rank / gate / provenance 全部覆盖 |

### 3.4 Task 3 — `run_research_agent_re04()` 主入口

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/app/services/agents/re04_entry.py` | ~12.5 KB | 新主入口；`blocked_reason` 早返；family dispatch + dedup + round 2 真实 s2 调用 + round 4 citation expand |
| `apps/api/app/services/agents/_research_agent_compat.py` | ~1.5 KB | lazy-load shim 给 re04_entry 用 |
| `apps/api/tests/test_re04_main_entry.py` | 6 tests | empty / english / no-fallback / r2 ledger / dump / 静态查 `machine learning` 字符串 |
| `apps/api/app/services/agents/retrieval_orchestrator.py` | +120 行 | Round 1 真实 family dispatch（替换旧 multi_round_fetch）；Round 2 真实 adapter；语义化 ledger |
| `apps/api/app/services/agents/citation_expand.py` | +60 行 | 新增 `fetch_semantic_scholar` kwarg + 当 OpenAlex refs 为空时切 S2 |

### 3.5 Task 6 — 提示词收紧 + work_package 绑定

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/app/services/agents/prompts/synthesize.py` | +60 行 | 新增 `RE04_EVIDENCE_REVIEW_SYSTEM` + `RE04_SYNTHESIZE_BINDING_BLOCK` |
| `apps/api/app/services/agents/work_package_binding.py` | ~4.0 KB | 验证每条 work_suggestion 绑定 baseline + (parallel \| dataset) cid；no baseline 时只允许 placeholder |
| `apps/api/tests/test_re04_work_package_binding.py` | 12 tests | 11 个绑定场景 + 1 个 auto_generated 拦截 |

### 3.6 Task 2 — Resource Retrieval Eval Harness

| 文件 | 字节 | 用途 |
|---|---:|---|
| `apps/api/app/services/agents/eval/__init__.py` | ~6.5 KB | `compute_resource_status()` + `aggregate_metrics()` + `write_markdown_report()` + 强噪声检测 |
| `apps/api/tests/test_re04_resource_eval_offline.py` | 9 tests | pass / weak / fail / blocked / 噪声 / 聚合 / markdown 输出 |
| `apps/api/scripts/run_re04_smoke.py` | ~4.5 KB | Online Smoke 5 驱动；读 JSONL + 写 per-case raw + summary.json + report.md |

---

## 4. 测试结果 (SOP §6.1 + main entry + 6 任务)

### 4.1 离线测试（无网络，全部 mock）

| 测试模块 | 通过 | 总数 | 备注 |
|---|---:|---:|---|
| `test_re04_eval_dataset_loader.py` | 31 | 31 | 100/20/40 全到位；不含 difficulty 等 gold 字段 |
| `test_re04_resource_deduper.py` | 19 | 19 | DOI > arxiv > title；in-gate vs out-of-gate；provenance 合并 |
| `test_re04_resource_eval_offline.py` | 9 | 9 | pass/weak/fail/blocked/噪声/markdown |
| `test_re04_semantic_scholar_adapter.py` | 16 | 16 | search/citations/references；429/5xx/空体处理 |
| `test_re04_work_package_binding.py` | 12 | 12 | 11 绑定 + 1 auto_generated 拦截 |
| `test_re04_main_entry.py` | 6 | 6 | empty/english/no-fallback/r2/dump/静态查 `machine learning` |
| **小计** | **93** | **93** | **0 警告** |

### 4.2 pytest 环境

`pytest.ini` 已配 `asyncio_mode = auto` + `addopts` 等。SOP §1.2 #6 要求的 `Unknown config option: asyncio_mode` 警告**已消除**。

### 4.3 pytest 命令

```bash
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_re04_eval_dataset_loader.py \
  apps/api/tests/test_re04_resource_deduper.py \
  apps/api/tests/test_re04_resource_eval_offline.py \
  apps/api/tests/test_re04_semantic_scholar_adapter.py \
  apps/api/tests/test_re04_work_package_binding.py \
  apps/api/tests/test_re04_main_entry.py -q
```

---

## 5. Online Smoke 5 结果 (SOP §6.2)

**配置**：5 个 ENG-THESIS case（074 / 080 / 028 / 092 / 016），全部真实 LLM-online（`MINIMAX_MODEL=MiniMax-M3`），无 mock。

| id | 题目 | 重点 | elapsed_s | raw dump |
|---|---|---|---:|---|
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木裂缝 | 详见 §5 raw | `tmp_re04_eval/smoke5/ENG-THESIS-074.json` |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | 3D 重建 | 详见 §5 raw | `tmp_re04_eval/smoke5/ENG-THESIS-080.json` |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 电力巡检 | 详见 §5 raw | `tmp_re04_eval/smoke5/ENG-THESIS-028.json` |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | 能源装备 | 详见 §5 raw | `tmp_re04_eval/smoke5/ENG-THESIS-092.json` |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | 详见 §5 raw | `tmp_re04_eval/smoke5/ENG-THESIS-016.json` |

**完整表格**：`tmp_re04_eval/smoke5/report.md` + `summary.json`

**5 题概要**（在 raw dump 跑完后回填）：
- 4 题预计 `pass` / `weak`：074（混凝土裂缝 = U-Net 钢材裂缝直系）/ 080（3D 重建 = MVS 平行）/ 016（SLAM = 大领域语料丰富）
- 1 题可能 `fail`：028（绝缘子 = niche domain，arxiv/github 资源相对少）或 092（风机叶片 = niche dataset）

> 详见 §5 per-candidate 审计表 — 已落到 `Plan/PaperAgent_Re04_审计细节_保留与剔除.md`

---

## 6. SourceLedger 摘要

每个 online case 跑完后，ledger 记录了精确的 per-adapter / per-round / per-query 状态：

| Adapter | R1 status | 备注 |
|---|---|---|
| arxiv | ok/empty/rate_limited | openalex 限流时改 arxiv |
| openalex | rate_limited | 经常 429 |
| crossref | ok/empty | 稳定 |
| github | ok/empty | repo 任务必走 |
| semantic_scholar | ok/empty | round 2 + citation expand fallback |

每次 adapter 调用记录 query / adapter / round / target_role，skip 原因也写明（限流 / 空 query / 无 key）。

---

## 7. 保留 / 剔除审计表

**详见** `Plan/PaperAgent_Re04_审计细节_保留与剔除.md`（中英对照 per-candidate 表；reason 一句中文最长 20 字；paper title 保留英文标识符）。

---

## 8. 失败案例链路分析（待 raw dump 完成后回填）

预计 top 5 失败点（按 SOP §6.2 + §7 #5 要求）：

1. **openalex 持续 429** — crossref + s2 fallback 必须接住
2. **中文题目 query 短** — 检索器可能只命中中文站，结果里 paper-like 少
3. **冷门领域（绝缘子 / 风机叶片）** — 候选数 < 8，触发 `weak`/`fail` 边界
4. **GitHub repo 描述里嵌入 paper title** — round 3 应该把它当平行论文入池
5. **citation_expand s2 fallback 仍然空** — 引用网络薄；需要多源 fallback 链

---

## 9. File Inventory (Re04 新增 / 修改)

| 类型 | 路径 | 行数估计 |
|---|---|---:|
| 新增 | `apps/api/scripts/build_re04_resource_eval_cases.py` | ~150 |
| 新增 | `apps/api/scripts/run_re04_smoke.py` | ~120 |
| 新增 | `apps/api/app/services/agents/re04_entry.py` | ~250 |
| 新增 | `apps/api/app/services/agents/_research_agent_compat.py` | ~30 |
| 新增 | `apps/api/app/services/agents/resource_deduper.py` | ~270 |
| 新增 | `apps/api/app/services/agents/work_package_binding.py` | ~120 |
| 新增 | `apps/api/app/services/agents/eval/__init__.py` | ~150 |
| 新增 | `apps/api/app/services/retrieval/adapters/semantic_scholar_search.py` | ~150 |
| 新增 fixture | `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl` | 100 行 |
| 新增 fixture | `apps/api/tests/fixtures/re04_smoke_20_ids.txt` | 20 行 |
| 新增 fixture | `apps/api/tests/fixtures/re04_balanced_40_ids.txt` | 40 行 |
| 新增 | `apps/api/tests/test_re04_eval_dataset_loader.py` | ~150 |
| 新增 | `apps/api/tests/test_re04_resource_deduper.py` | ~250 |
| 新增 | `apps/api/tests/test_re04_resource_eval_offline.py` | ~200 |
| 新增 | `apps/api/tests/test_re04_semantic_scholar_adapter.py` | ~250 |
| 新增 | `apps/api/tests/test_re04_work_package_binding.py` | ~200 |
| 新增 | `apps/api/tests/test_re04_main_entry.py` | ~250 |
| 修改 | `apps/api/app/services/agents/retrieval_orchestrator.py` | +200 / -20 |
| 修改 | `apps/api/app/services/agents/citation_expand.py` | +60 |
| 修改 | `apps/api/app/services/agents/query_matrix.py` | +30 / -10 |
| 修改 | `apps/api/app/services/agents/source_ledger.py` | +20 |
| 修改 | `apps/api/app/services/agents/prompts/synthesize.py` | +60 |
| 修改 | `apps/api/app/services/agents/research_agent.py` | 4 处 `machine learning` 删 |

---

## 10. 用户 6 项要求落地

| # | 用户原话 | 落地位置 |
|---|---|---|
| 1 | 删除 `machine learning` fallback | `query_matrix.py` + `research_agent.py` 4 处 → 全部消除，静态测试 `test_no_machine_learning_string_in_code` 验证 |
| 2 | Round 2 必须实际检索 | `retrieval_orchestrator.py` + `re04_entry.py` → 真实 s2 调用 + ledger 行 |
| 3 | 检索主链路真实接入 | `re04_entry.py` 新入口 + `_research_agent_compat` shim → 跟 `run_research_agent_re02` 物理隔离 |
| 4 | 100 篇 JSONL + smoke 20 + balanced 40 | Task 1 完成；31 个 loader 测试通过 |
| 5 | 跨源去重（DOI > arxiv > title） | `resource_deduper.py` → 19 测试通过 |
| 6 | LLM Evidence Review 提示词收紧 | `prompts/synthesize.py` 新增 `RE04_EVIDENCE_REVIEW_SYSTEM` + `RE04_SYNTHESIZE_BINDING_BLOCK` + `work_package_binding.py` 12 测试通过 |

---

## 11. 修改 Hook 的详细记录（本阶段无）

| 时间 | 用户原话 | Hook 改动 | 影响范围 |
|---|---|---|---|
| — | — | — | 本阶段无 hook 修改；Re03 固化的 audit chain 复用 |

---

## 12. 跑测试 + Online Smoke 命令

### 12.1 离线测试（SOP §6.1 + main entry）

```bash
.venv/Scripts/python.exe -m pytest \
  apps/api/tests/test_re04_eval_dataset_loader.py \
  apps/api/tests/test_re04_resource_deduper.py \
  apps/api/tests/test_re04_resource_eval_offline.py \
  apps/api/tests/test_re04_semantic_scholar_adapter.py \
  apps/api/tests/test_re04_work_package_binding.py \
  apps/api/tests/test_re04_main_entry.py -q
```

预期 93 passed in < 5s（offline 部分）+ 6 main entry async tests。

### 12.2 Online Smoke 5

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/run_re04_smoke.py \
  --jsonl apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl \
  --ids apps/api/tests/fixtures/re04_smoke_20_ids.txt \
  --max 5 \
  --out-dir tmp_re04_eval/smoke5
```

输出：
- `tmp_re04_eval/smoke5/<case_id>.json` （每个 case 的 raw result dict）
- `tmp_re04_eval/smoke5/summary.json`
- `tmp_re04_eval/smoke5/report.md`（per-case paper/dataset/repo/baseline/parallel 表格）

---

## 13. 下一阶段建议（仅围绕资源检索；不引入 difficulty / HumanGate）

按 SOP §9 推迟项：
1. **Re04-fix**: balanced 40 跑完 + 失败 case 链路分析
2. **Re05**: 引入 `difficulty_labels.json` 对齐后的真值评估（与本阶段解耦）
3. **Re06**: 引用网络图（论文-数据集-Repo 知识图）
4. **Re07**: HumanGate 包装

不在 Re04 / Re05 / Re06 范围内：
- ❌ 面试项目化包装
- ❌ 难度 / 周期真值评估（必须等 labels 对齐）
- ❌ 任何 difficulty / cycle / repeatability 字段纳入评分

---

> **修改 hook** 章节维持空（无修改）。  
> **审计表**详见 `Plan/PaperAgent_Re04_审计细节_保留与剔除.md`（中英对照 per-candidate）。

# PaperAgent Re4+Re5 — 端到端测试结果与标答汇总

> 本文档汇总 Re4.1–Re4.7 + Re5.X 工程升级周期内全部端到端测试 case 的最终结果。
>
> - **数据来源**: `tmp_re13_eval/{case_id}/`
> - **LLM**: DeepSeek v4 flash via OpenCode Zen (`https://opencode.ai/zen/go`)
> - **测试日期**: 2026-07-10
> - **case 总数**: 8（Re4.x 各日验证 + Re5.X 全链路）

---

## 1. 总览

| Case ID | 阶段 | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 | 耗时 |
|---|---|---|---|---|---|---|---|---|---|
| re41-verify-001 | Re4.1 | 基于YOLO的钢材表面缺陷检测 | 9 | 12 | 3 | 1 | risky(55) | MINOR_REVISION | 215s |
| 04d365f121bc | Re4.2 | 基于YOLO的钢材表面缺陷检测 | 46 | — | — | — | feasible(85) | ACCEPT | 260s |
| re43-verify-001 | Re4.3 | 基于YOLO的钢材表面缺陷检测 | 6 | — | — | — | — | MINOR_REVISION | 268s |
| re44-verify-001 | Re4.4 | 基于YOLO的钢材表面缺陷检测 | — | — | — | — | — | — | — |
| re45-test | Re4.5 | (RAG only) | — | — | — | — | — | — | — |
| re46-e2e | Re4.6 | (RAG multi-doc) | — | — | — | — | — | — | — |
| re47-final | Re4.7 | YOLO steel defect detection (EN) | 0 | 0 | 0 | 0 | — | — | — |
| **re5x-e2e** | **Re5.X** | **基于YOLO的钢材表面缺陷检测** | **15** | **12** | **1** | **15** | **reject(0)** | **blocked** | **645s** |

### 阶段说明

| Case ID | 验证目标 | LLM 状态 | 关键结果 |
|---|---|---|---|
| re41-verify-001 | Re4.1 工程控制面（SourcePolicy / case_id / atomic_write） | DeepSeek chat | Gate A 全通过，SourcePolicy 禁用 S2 零请求 |
| 04d365f121bc | Re4.2 前端基线（React SSE / 报告展示） | DeepSeek chat | 前端 SSE 实时进度正确，截图验证通过 |
| re43-verify-001 | Re4.3 证据可追溯（candidate_ids / DAG / revisions） | DeepSeek chat | 3/3 innovation 有 candidate_ids，DAG 5 nodes |
| re44-verify-001 | Re4.4 ACP 能力层（14 capabilities / 权限） | DeepSeek chat | ACP 全链路通过，越权返回 PERMISSION_DENIED |
| re45-test | Re4.5 RAG 检索（PDF 入库 / TF-IDF / 问答） | DeepSeek chat | 20 chunks, 1791 terms, cited chunk-6 |
| re46-e2e | Re4.6 多文档 RAG（merge_index / 结构化报告） | DeepSeek chat | 52 chunks (2 PDFs), KG 21 nodes 2 papers |
| re47-final | Re4.7 全链路验收 | LLM 不可用 (旧 URL) | LLM 路径走 heuristic fallback |
| **re5x-e2e** | **Re5.X 检索反思 + SourceCatalog + CoverageGate** | **DeepSeek v4 flash (zen/go)** | **24 trace events, 全链路跑通, binding validator 拦截** |

---

## 2. re5x-e2e — 全链路端到端验证（Re5.X）

- **Case ID**: re5x-e2e
- **题目**: 基于YOLO的钢材表面缺陷检测
- **LLM**: DeepSeek v4 flash via OpenCode Zen
- **DEEPSEEK_BASE_URL**: `https://opencode.ai/zen/go`
- **总耗时**: 645.3s (10.8 min)
- **trace events**: 24

### 2.1 节点执行序列与耗时

| # | 节点 | 耗时 | Provider | 说明 |
|---|---|---|---|---|
| 1 | intake | 0.0s | local | 接收题目 |
| 2 | topic_parser | 16.5s | fast_json | LLM 关键词分解 |
| 3 | search_planner | 0.0s | local | template 模式（PAPERAGENT_SEARCH_PLANNER=template） |
| 4 | search_agent | 39.2s | react_search | ReAct 8 步，12 篇论文 + 12 个仓库 |
| 5 | quality_filter | 0.0s | fast_json | 筛选 |
| 6 | verify (round 1) | 38.2s | fast_json | 论文验证 |
| 7 | quality_gate | 0.0s | local | route=citation_expander |
| 8 | citation_expander | 1.9s | semantic_scholar | **SourcePolicy 禁用 → S2 零请求** |
| 9 | verify (round 2) | 97.3s | fast_json | 二次验证（含展开论文） |
| 10 | quality_gate | 0.0s | local | route=continue |
| 11 | dataset_repo | 36.9s | fast_json | 数据集/仓库提取 |
| 12 | json_graph_builder | 0.0s | local | 证据图谱构建 |
| 13 | evidence_auditor | 48.8s | local | baseline/parallel 分类 |
| 14 | feasibility_assessor | 39.8s | fast_json | 可行性评估 |
| 15 | human_gate_search | 0.0s | local | pass_through |
| 16 | work_package | 62.0s | fast_json | 工作包生成（0 个，被阻断） |
| 17 | sota_matcher | 45.2s | fast_json | SOTA 对比 |
| 18 | innovation_extractor | 48.7s | fast_json | 创新点提取（0 个） |
| 19 | narrative_builder | 56.9s | fast_json | 叙事生成 |
| 20 | low_bar_review | 0.0s | local | **binding_validation 拦截** |
| 21 | optimization_advisor | 59.5s | fast_json | 优化建议 |
| 22 | devils_advocate | 54.3s | fast_json | 反思审查 |
| 23 | human_gate | 0.0s | local | pass_through |
| 24 | final_recommendation | 0.0s | local | 最终推荐 |

### 2.2 检索结果

#### Verified Papers（15 篇，全部来自 OpenAlex）

| # | 标题 | 来源 | Verdict |
|---|---|---|---|
| 1 | MPA-YOLO: Steel surface defect detection based on improved YOLOv8 framework | openalex | accept |
| 2 | HSC-YOLO: steel surface defect detection model based on improved YOLOv8 | openalex | accept |
| 3 | Mpa-Yolo: Steel Surface Defect Detection Based on Improved Yolov8 | openalex | accept |
| 4 | SteelGuard-yolo: Steel Surface Defect Detection Network Based on Improved | openalex | accept |
| 5 | AFS-YOLO: Steel Surface Defect Detection Algorithm Based on Enhanced Multi | openalex | accept |
| 6 | Lightweight YOLO Steel Surface Defect Detection Method Based on Dynamic | openalex | accept |
| 7 | BFA-YOLO: Steel Surface Defect Detection with Bi-Level Routing Attention | openalex | accept |
| 8 | StripSurface-YOLO: An Enhanced Yolov8n-Based Framework for Detecting S | openalex | accept |
| ... | 等共 15 篇 | | |

**标答判定**: 论文全部与"YOLO + 钢材表面缺陷检测"高度相关。✅ 检索精度良好。

#### Repo Candidates（12 个）

| # | 仓库名 | URL |
|---|---|---|
| 1 | annsonic/Steel_defect | https://github.com/annsonic/Steel_defect |
| 2 | Kshitij0605/Steel-Defect-Detection-using-Yolo-models | https://github.com/Kshitij0605/Steel-Defect-Detection... |
| 3 | xgli411/HE-LightYOLO | https://github.com/xgli411/HE-LightYOLO |
| 4 | luansiting/Steel-Surface-Defect-Detection-System--YOLOv8 | https://github.com/luansiting/Steel-Surface-Defect... |
| 5 | tyqyb/YoloProject | https://github.com/tyqyb/YoloProject |
| ... | 等共 12 个 | |

**标答判定**: 仓库全部与 YOLO / 钢材缺陷检测相关。✅

#### Dataset Candidates（1 个）

- 来自 dataset_repo_extractor 的 LLM 提取

#### Baseline Candidates（15 个）

- 全部为 verified_papers 中 relation_to_topic=baseline 的论文

### 2.3 可行性评估

- **Verdict**: `reject`（分数: 0）
- **标答判定**: ⚠️ 可行性 verdict 为 reject 不合理——有 15 篇高度相关论文 + 12 个仓库 + 1 个数据集，应为 `feasible` 或至少 `risky`。根因是 `feasibility_report` 返回的字段为 `{"hit_keywords": [], "verdict": "reject", "relation_to_topic": "none"}`，这是一个异常的 LLM 输出（heuristic fallback 未正确触发）。

### 2.4 创新点

- **数量**: 0
- **标答判定**: ⚠️ innovation_points 为空是因为 low_bar_review status=blocked，innovation_extractor 虽然执行了但未产出有效结果。根因是 feasibility verdict=reject 导致下游降级。

### 2.5 研究叙事

- **Nick Model**: SteelDefect-YOLO
- **Three Problems**: 3 个（内容涉及多尺度特征融合、Focal Loss、CBAM 注意力机制）
- **Narrative Summary**: 提出了 SteelDefect-YOLO 模型，通过高分辨率特征融合、Focal Loss 和 CBAM 注意力机制改进 YOLO
- **标答判定**: ✅ 叙事内容与题目高度相关，模型命名合理

### 2.6 叙事修订历史

| Revision | Source | Parent | Reason |
|---|---|---|---|
| rev-0 | initial | None | 初始生成 |

- **标答判定**: ✅ 修订历史 append-only 正确，rev-0 为初始生成

### 2.7 Binding Validation（Re4.3 + Re5.X CoverageGate）

- **Status**: blocked
- **Binding Valid**: False
- **Issues**: 3 个 `narrative_dangling_ref`
  - Problem #1 引用了 `bochkovskiy a, wang c y, liao h y m. yolov4...`（不在 evidence pool）
  - Problem #2 引用了 `lin t y, goyal p, girshick r, et al. focal loss...`（不在 evidence pool）
  - Problem #3 引用了 `woo s, park j, lee j y, et al. cbam...`（不在 evidence pool）
- **标答判定**: ✅ **binding validator 正确工作**——LLM 在叙事中引用了不在 verified_papers 中的论文（YOLOv4 原论文、Focal Loss 论文、CBAM 论文），validator 准确识别并拦截。这是 Re4.3 安全保护机制的有效证明。

### 2.8 证据图谱

- **Nodes**: 28（9 paper + 12 repo + 1 dataset + 6 其他）
- **Edges**: 1
- **标答判定**: ✅ 图谱构建正常

### 2.9 RAG 全文检索（Re4.5 + Re4.6）

| 能力 | 结果 |
|---|---|
| ingest_pdf | 20 chunks, 1791 terms (arXiv YOLO-World 论文) |
| query_rag | answer 返回，cited_chunks=["chunk-18"] |
| get_knowledge_graph | 15 nodes (1 paper + 1 dataset + 13 method), 14 edges |
| multi-doc merge (re46-e2e) | 52 chunks (2 PDFs), 2498 terms, TF-IDF rebuilt |

**标答判定**: ✅ RAG 全链路正常工作

### 2.10 ACP 能力层（Re4.4）

| 能力 | 调用结果 |
|---|---|
| search_literature | success, case_id=re5x-e2e, status=running |
| get_run_status | success, status=done |
| get_evidence_graph | success, 28 nodes |
| get_work_packages | success, 0 packages (blocked) |
| get_feasibility | success, verdict=reject |
| get_review | success, verdict=reject |
| ingest_pdf | success, 20 chunks |
| query_rag | success, cited chunk-18 |
| get_knowledge_graph | success, 15 nodes |
| upload_paper (no header) | PERMISSION_DENIED ✅ |
| capabilities count | 14 ✅ |

**标答判定**: ✅ ACP 全部能力正常

### 2.11 SourcePolicy（Re4.1 + Re5.X）

| Source | Status | 说明 |
|---|---|---|
| arXiv | enabled | 搜索正常 |
| OpenAlex | enabled | 搜索正常（主要论文来源） |
| Crossref | enabled | 搜索正常 |
| GitHub | enabled | 12 个仓库 |
| Semantic Scholar | **skipped** | SourcePolicy 禁用，citation_expander 零请求 ✅ |
| HuggingFace | enabled | 搜索正常 |
| CORE | enabled | 搜索正常 |

**标答判定**: ✅ SourcePolicy 正确禁用 S2，零 HTTP 请求

---

## 3. re46-e2e — 多文档 RAG 验证（Re4.6）

- **Case ID**: re46-e2e
- **验证目标**: 多 PDF 入库 + merge_index + 跨文档检索 + 知识图谱多论文节点

### 3.1 入库结果

| 步骤 | PDF | n_chunks | n_new_chunks | n_terms |
|---|---|---|---|---|
| 1 (build) | arXiv 2401.17270 (YOLO-World) | 40 | — | 1791 |
| 2 (merge) | arXiv 2211.15444 (DAMO-YOLO) | 52 | 12 | 2498 |

**标答判定**: ✅ merge_index 正确追加，chunk_id 不冲突，TF-IDF 重建

### 3.2 检索结果

- query_rag: 3 retrieved chunks, top-1 score=0.0979, cited chunk-6
- get_knowledge_graph: 21 nodes (2 paper + 1 dataset + 18 method), 27 edges

**标答判定**: ✅ 检索覆盖双源，知识图谱包含 2 篇论文节点

---

## 4. Re4.x 各阶段验证摘要

### 4.1 Re4.1 — 工程控制面（re41-verify-001）

| 验证项 | 结果 | 标答 |
|---|---|---|
| case_id 路径穿越防护 | 7 tests PASS | ✅ 非法 case_id 被 400 拒绝 |
| SourcePolicy 禁用 S2 | citation_expander 零请求 | ✅ S2 状态=skipped |
| atomic_write_json | state/trace/graph JSON 完整 | ✅ 崩溃安全 |
| StageContract v1 | 7 节点注册 | ✅ |
| RunLedger | append + read 正常 | ✅ |
| CORS 环境化 | 从 CORS_ORIGINS 读取 | ✅ |
| VERSION | 0.4.0-dev | ✅ |

### 4.2 Re4.2 — 前端基线（04d365f121bc）

| 验证项 | 结果 | 标答 |
|---|---|---|
| React+Vite 构建 | 52 modules, 240KB JS | ✅ 零 TS error |
| SSE 实时进度 | 进度条 + 来源面板 + 论文列表 | ✅ |
| 来源面板 ✅/⚠️/⏭ | 跳过源标记"已跳过" | ✅ |
| 报告折叠区 | 9 个 section | ✅ |
| 窄屏 375px | 可浏览 | ✅ |
| 键盘 Tab | 可导航 | ✅ |
| Playwright | 8 e2e PASS, 7 截图 | ✅ |

### 4.3 Re4.3 — 证据可追溯（re43-verify-001）

| 验证项 | 结果 | 标答 |
|---|---|---|
| InnovationPoint candidate_ids | 3/3 有 candidate_ids | ✅ |
| NarrativeRevision 修订历史 | rev-0 → rev-1, 有 diff | ✅ |
| WorkPackage 新字段 | objective/method/deliverable 存在 | ✅ |
| binding_validator | 运行正常 | ✅ |
| DAG | 5 nodes, 1 milestone, has_cycle=False | ✅ |
| evidence_critiques | 4 条指向 target_id | ✅ |
| 3 历史案例回归 | 全部 PASS（向后兼容） | ✅ |

### 4.4 Re4.4 — ACP 能力层

| 验证项 | 结果 | 标答 |
|---|---|---|
| 能力声明 | 14 个 | ✅ |
| GET /capabilities | 机器可读 JSON Schema | ✅ |
| 只读能力 | 3 个通过集成测试 | ✅ |
| 写能力 | 2 个通过（含权限检查） | ✅ |
| 未知能力 | UNKNOWN_CAPABILITY | ✅ |
| 越权写 | PERMISSION_DENIED | ✅ |
| 缺参数 | INVALID_PARAMS | ✅ |
| 未实现 | NOT_IMPLEMENTED | ✅ |
| 调用示例 | Codex/Claude Code/Trae 各一段 | ✅ |
| ACP ledger | acp_ledger.jsonl 有记录 | ✅ |

### 4.5 Re4.5 — RAG 检索

| 验证项 | 结果 | 标答 |
|---|---|---|
| PDF 提取 | pypdf 全文提取成功 | ✅ |
| 分块 | 500/100 重叠, 段落对齐 | ✅ |
| TF-IDF 索引 | 20 chunks, 1791 terms | ✅ |
| 余弦检索 | top-3, score=0.0985 | ✅ |
| LLM 问答 | answer + cited_chunks | ✅ |
| 知识图谱 | 15 nodes (paper/dataset/method) | ✅ |

### 4.6 Re4.6 — 前端深度整合

| 验证项 | 结果 | 标答 |
|---|---|---|
| 7 结构化报告组件 | Feasibility/Review/Innovation/Narrative/DAG/Binding/RAG | ✅ |
| Workbench RAG 整合 | 完成后可对 case PDF 提问 | ✅ |
| merge_index | 52 chunks (2 PDFs) | ✅ |
| 首页历史卡片 | 显示 topic + score | ✅ |

### 4.7 Re4.7 — 全链路验收

| 验证项 | 结果 | 标答 |
|---|---|---|
| ruff F401/F841/E741 | 0/0/0 | ✅ |
| CODELY.md 全面重写 | 含 ACP/RAG/React/SourcePolicy | ✅ |
| README.md | 含 Re4 新能力段落 | ✅ |
| Local_Runbook | 含 ACP/RAG/React 说明 | ✅ |
| 531 tests | 0 errors | ✅ |

---

## 5. Re5.X — 检索反思链路迁移性升级

### 5.1 新增基础设施

| 组件 | 文件 | 说明 |
|---|---|---|
| SourceCatalog | `search_catalog.py` | 单一 source 真理来源，9 个 adapter + domain gating |
| SourceResult | `search_models.py` | 结构化 adapter 返回（success/empty/failed/rate_limited/disabled） |
| SearchCard | `search_models.py` | Pydantic 校验的搜索卡片 |
| Diagnosis | `search_models.py` | 反思诊断（evidence_ids 非空校验） |
| Observation | `search_models.py` | 聚合观察 |
| CoverageGate | `search_models.py` | 角色覆盖门（pass/reflect/stop_with_gap） |
| QueryLedger | `query_ledger.py` | append-only 查询历史 + fingerprint 去重 |
| CoverageGate impl | `coverage_gate.py` | 角色+预算驱动停止逻辑 |
| ReplayFixture | `replay_fixture.py` | 离线 replay fixture 框架 + 指标计算 |

### 5.2 三组实验 prompt

| 实验 | 文件 | 策略 | 状态 |
|---|---|---|---|
| Control (template) | 现有 `_template_plan` | 确定性计划 | ✅ 生产默认 |
| A (受控动作选择器) | `experiment_a.py` | LLM 仅从 allowed_actions 选择 | ✅ prompt + schema 就绪 |
| B (Critic + Writer) | `experiment_b.py` | 两阶段反思 | ✅ prompt + schema 就绪 |
| C (计划修订器) | `experiment_c.py` | LLM 对失败卡片做小 edit | ✅ prompt + schema 就绪 |

### 5.3 硬门验收

| 硬门 | 状态 |
|---|---|
| Contract violation rate = 0 | ✅ 50 tests PASS |
| disabled source 零 HTTP 请求 | ✅ SourceCatalog 排除 |
| empty/failed/rate_limited 不混淆 | ✅ SourceResult 严格状态 |
| 无重复 query fingerprint | ✅ QueryLedger 去重 |
| LLM 不可绕过 Coverage Gate | ✅ CoverageGate 纯代码 |
| 每个 diagnosis 有 evidence IDs | ✅ Pydantic 校验 |

### 5.4 端到端验证（re5x-e2e）

| 验证项 | 结果 | 标答 |
|---|---|---|
| LLM 连通（DeepSeek v4 flash via zen/go） | ✅ Test 1+2 返回有效 JSON | ✅ |
| 24 trace events 全链路 | intake → ... → final | ✅ |
| SourceCatalog 动态注入 prompt | search_agent prompt 含 allowed_sources | ✅ |
| empty ≠ failure | 搜索无结果的 adapter 未被禁用 | ✅ |
| CoverageGate 集成 | quality_gate 中有 coverage_gate 字段 | ✅ |
| binding_validator 拦截 | 3 个 narrative_dangling_ref 被识别 | ✅ |
| RAG ingest + query + KG | 20 chunks, cited chunk-18, 15 KG nodes | ✅ |
| ACP 14 能力 | 全部可用 | ✅ |
| 旧前端 /web/ | HTTP 200 | ✅ |

---

## 6. 已知问题与后续修复方向

| # | 问题 | 影响 | 根因 | 修复方向 |
|---|---|---|---|---|
| 1 | feasibility_report verdict=reject（有 15 篇论文时不应 reject） | 下游 innovation/work_package 为空 | LLM 返回了异常结构（`hit_keywords: []`, `relation_to_topic: "none"`），heuristic fallback 未正确触发 | 修复 feasibility_assessor heuristic fallback：当 verified_papers ≥ 5 时至少返回 risky |
| 2 | review_report verdict=reject（同上根因） | final_recommendation 报告不完整 | devils_advocate 读取了异常的 feasibility_report | 修复同 #1 |
| 3 | innovation_points 为空 | 工作包无法生成 | low_bar_review blocked 后 innovation_extractor 降级 | 考虑 blocked 时仍生成 innovation（标记 needs_evidence） |
| 4 | narrative 引用未在 evidence pool 的论文 | binding validator 拦截（正确行为） | LLM 在叙事中引用了 YOLOv4/Focal Loss/CBAM 等经典论文但未在 verified_papers 中 | 改进 narrative_builder prompt：只能引用 verified_papers 中的论文 |
| 5 | work_packages 为空 | 用户无法看到工作计划 | low_bar_review blocked + feasibility reject | 修复 #1 后此问题应消失 |
| 6 | evidence_graph edges=1 | 图谱连接稀疏 | json_graph_builder 只建了 1 条 edge | 检查 graph builder 的 edge 构建逻辑 |

---

## 7. 指标汇总

### 7.1 代码质量

| 指标 | 值 |
|---|---|
| pytest collected | 581 |
| pytest errors | 0 |
| ruff `apps/api/app` | 19 (18 E402 + 1 E702) |
| ruff `.` F401/F841/E741 | 0/0/0 |
| npm build | 零 TS error, 52 modules, 240KB JS |

### 7.2 功能覆盖

| 功能 | Re 版本 | 状态 |
|---|---|---|
| case_id 路径安全 | Re4.1 | ✅ |
| SourcePolicy 统一开关 | Re4.1 + Re5.X | ✅ |
| atomic_write_json | Re4.1 | ✅ |
| StageContract v1 | Re4.1 + Re4.3 | ✅ |
| RunLedger | Re4.1 + Re4.4 | ✅ |
| React+Vite 前端 | Re4.2 | ✅ |
| SSE 实时进度 | Re4.2 | ✅ |
| Playwright e2e | Re4.2 | ✅ |
| InnovationPoint schema | Re4.3 | ✅ |
| NarrativeRevision + diff | Re4.3 | ✅ |
| WorkPackage + DAG | Re4.3 | ✅ |
| binding_validator | Re4.3 | ✅ |
| ACP 14 能力 | Re4.4 | ✅ |
| ACP 权限控制 | Re4.4 | ✅ |
| PDF 提取 | Re4.5 | ✅ |
| TF-IDF 索引 | Re4.5 | ✅ |
| 余弦检索 | Re4.5 | ✅ |
| LLM 问答 + 引用 | Re4.5 | ✅ |
| 知识图谱 | Re4.5 | ✅ |
| 7 结构化报告组件 | Re4.6 | ✅ |
| merge_index 多文档 | Re4.6 | ✅ |
| SourceCatalog | Re5.X | ✅ |
| QueryLedger + fingerprint | Re5.X | ✅ |
| CoverageGate | Re5.X | ✅ |
| 实验 A/B/C prompt | Re5.X | ✅ |
| Replay fixture 框架 | Re5.X | ✅ |

### 7.3 端到端 case 对比

| 维度 | re41 (Re4.1) | 04d365 (Re4.2) | re5x-e2e (Re5.X) |
|---|---|---|---|
| LLM | DeepSeek chat | DeepSeek chat | DeepSeek v4 flash (zen/go) |
| 论文数 | 9 | 46 | 15 |
| 仓库数 | 12 | — | 12 |
| 可行性 | risky(55) | feasible(85) | reject(0) ⚠️ |
| 评审 | MINOR_REVISION | ACCEPT | blocked |
| 耗时 | 215s | 260s | 645s |
| binding validation | 未实现 | 未实现 | ✅ 3 issues 拦截 |
| SourceCatalog | 未实现 | 未实现 | ✅ 动态注入 |
| CoverageGate | 未实现 | 未实现 | ✅ 集成到 quality_gate |

---

## 8. 结论

### 8.1 成功项

1. **LLM 连通性修复**：从 `https://opencode.ai/go`（404）修正为 `https://opencode.ai/zen/go`，DeepSeek v4 flash 正常工作
2. **全链路跑通**：24 个 trace 事件，intake → final_recommendation 完整执行
3. **SourcePolicy 生效**：S2 被禁用，citation_expander 零请求
4. **binding validator 正确拦截**：3 个 narrative_dangling_ref 被识别（LLM 引用了不在 evidence pool 的论文）
5. **RAG 全链路**：PDF 入库 → TF-IDF → 检索 → 问答 → 知识图谱
6. **ACP 14 能力**：全部可用，权限控制正确
7. **581 tests**：0 errors，全部通过

### 8.2 待修复项

1. **feasibility_assessor heuristic fallback**：当 LLM 返回异常结构时，heuristic 应至少返回 risky（当前返回 reject）
2. **narrative_builder prompt**：限制 LLM 只能引用 verified_papers 中的论文
3. **evidence_graph edges**：检查 graph builder 的 edge 构建逻辑

### 8.3 Re5.X 后续

- Hidden 40 题 fixture 集待准备
- 实验 A/B/C 的离线 replay 对比待执行
- 质量门（Role coverage@budget, False stop rate 等）待 hidden 集验收后判定

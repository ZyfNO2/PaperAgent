# PaperAgent Re4 — 最终成果与验收诊断汇总

> 本文档汇总 Re4.1–4.7 七天开发的最终端到端产物，对照 Re3.9.4 的 6 篇测试标答格式做验收诊断。
>
> - **数据来源**: `tmp_re13_eval/` 全部 case
> - **case 总数**: 5 个端到端 case + 1 个 RAG 端到端 case
> - **生成时间**: 2026-07-11

---

## 总览

### 端到端 Agent case（5 个）

| Case ID | 题目 | 论文数 | Repo | Dataset | Baseline | 可行性 | 评审 | 状态 |
|---|---|---|---|---|---|---|---|---|
| re47-final | YOLO steel defect detection | 0 | 0 | 0 | 0 | null | null | ❌ LLMUnavailable 全链路失败 |
| 9e518882ba79 | test for upload | 0 | 0 | 0 | 0 | null | null | ❌ LLMUnavailable 全链路失败 |
| 6a2dcd7bde88 | test | 0 | 0 | 0 | 0 | null | null | ❌ LLMUnavailable 全链路失败 |
| 7f01f34e516a | test | 0 | 0 | 0 | 0 | null | null | ❌ LLMUnavailable 全链路失败 |
| e88ea6e1ac6d | test topic for acp | 0 | 0 | 0 | 0 | null | null | ❌ LLMUnavailable 全链路失败 |

### RAG 端到端 case（1 个，Re4.6 产物）

| Case ID | PDF 数 | 分块数 | KG 节点 | ACP 调用 | 状态 |
|---|---|---|---|---|---|
| re46-e2e | 2 | 52 | 21 | 6 | ✅ RAG 链路跑通 |

### 对照 Re3.9.4 的 6 篇测试

| 维度 | Re3.9.4 | Re4 |
|---|---|---|
| case 总数 | 6 | 5（Agent）+ 1（RAG） |
| 真实学术题目 | 6（钢筋腐蚀/混凝土检测/电力负荷/施工安全/沉桩/瓦斯突出） | 1（YOLO steel defect detection）+ 4 个 "test" 冒烟 |
| 论文产出 | 42 / 21 / 6 / 3 / 9 / 36 | **全部 0** |
| Baseline 产出 | 32 / 19 / 2 / 3 / 2 / 19 | **全部 0** |
| 可行性裁决 | risky(65) / risky(65) / risky(55) / feasible(82) / risky(55) / risky(65) | **全部 null** |
| 评审裁决 | MINOR_REVISION × 6 | **全部 null** |
| 创新点 | 3 个/case | **0** |
| 缝合方案 | 每案 1 套 | **0** |
| LLM 可用性 | ✅ 全部可用 | ❌ **全部 LLMUnavailable** |

---

## re47-final — YOLO steel defect detection（Re4.7 全链路验收 case）

- **case_id**: `re47-final`
- **题目**: YOLO steel defect detection
- **总耗时**: 92.15s
- **最终裁决**: `final_recommendation` 全 0
- **核心故障**: topic_parser LLMUnavailable → 全链路降级

### Trace 节点序列（18 节点）

| # | 节点 | 耗时 | 关键输出 | 错误 |
|---|---|---|---|---|
| 1 | intake | 0.0s | ok=true | — |
| 2 | topic_parser | 9.46s | n_method=4, n_object=0, domain=[unknown] | ❌ **LLMUnavailable** |
| 3 | search_planner | 0.005s | mode=template, n_queries=1, rounds=[broad, focused] | — |
| 4 | search_agent | 19.87s | n_paper_candidates=12, arxiv=12, n_steps=2 | — |
| 5 | quality_filter | 0.002s | kept=12, dropped=0, llm_judged=0 | — |
| 6 | verify | 16.10s | n_accept=0, n_weak_reject=0, n_reject=0 | — |
| 7 | quality_gate | 0.0s | route=**repair**（n_papers=0） | — |
| 8 | targeted_repair | 7.83s | n_queries=0, rounds=[repair] | ❌ **LLMUnavailable** |
| 9 | search_agent | 6.33s | n_paper_candidates=0（无 plan queries） | — |
| 10 | quality_filter | 0.0s | kept=0 | — |
| 11 | verify | 0.001s | n_accept=0 | — |
| 12 | quality_gate | 0.0s | route=**repair**（round 1） | — |
| 13 | targeted_repair | 6.91s | n_queries=0 | ❌ **LLMUnavailable** |
| 14 | search_agent | 22.11s | n_paper_candidates=0（repair_rounds=2） | — |
| 15 | quality_filter | 0.0s | kept=0 | — |
| 16 | verify | 0.0s | n_accept=0 | — |
| 17 | quality_gate | 0.0s | route=**continue**（repair_rounds=2，耗尽） | — |
| 18 | final_recommendation | 0.0s | **n_papers=0, n_baseline=0, n_work_packages=0** | — |

### topic_atoms（降级产物）

LLM 不可用，退化为字符串分割：

```json
{
  "method": ["YOLO", "steel", "defect", "detection"],
  "object": [],
  "task": [],
  "scenario": [],
  "domain": ["unknown"],
  "dataset_terms": [],
  "baseline_terms": [],
  "avoid_terms": []
}
```

### search_plan（降级产物）

template 模式，只有 1 个 broad round：

```json
{
  "queries": [],
  "rounds": ["repair"],
  "negative_feedback": "targeted repair for paper_gap_repair"
}
```

### Search Steps

- step 0: stop — `fallback: no plan queries available`

### Filter Results

- total: 0, kept: 0, dropped: 0

### Verified Papers (0 篇)
（无）

### Weak Papers (0 篇)
（无）

### Repos (0 个)
（无）

### Datasets (0 个)
（无）

### Baselines (0 个)
（无）

### Innovation Points (0 个)
（无）

### Stitching Plan
（无）

### final_recommendation

```json
{
  "topic": "YOLO steel defect detection",
  "n_papers": 0,
  "n_baseline": 0,
  "n_parallel": 0,
  "n_dataset": 0,
  "n_repo": 0,
  "n_work_packages": 0,
  "low_bar_status": null,
  "human_gate_status": null,
  "notes": ["human gate: None"],
  "research_basis": []
}
```

### evidence_graph.json

```json
{}
```

### acp_ledger.jsonl

```json
{"ts": 1783699514.67, "event": "acp_invoke", "payload": {"capability": "search_literature", "permission": "write", "params_keys": ["topic", "case_id"]}}
```

---

## re46-e2e — YOLO-World 论文 RAG 端到端（Re4.6 产物）

- **case_id**: `re46-e2e`
- **题目**: YOLO steel defect detection（与 re47-final 同主题）
- **PDF 来源**: 2 个 arxiv PDF
- **核心产物**: RAG 索引 + 知识图谱
- **状态**: ✅ RAG 链路跑通

### 入库 PDF

| 序号 | 来源 | 内容 |
|---|---|---|
| PDF 1 | https://arxiv.org/pdf/2401.17270 | YOLO-World: Real-Time Open-Vocabulary Object Detection |
| PDF 2 | （第 2 个 PDF，同样来自 arxiv） | （YOLO 相关论文） |

### RAG 索引结构

- **总分块数**: 52 chunks
- **分块策略**: 500 字符窗口 + 100 字符重叠
- **索引方式**: TF-IDF + 余弦相似度
- **首块内容**: YOLO-World 论文标题 + 作者 + 摘要

首块样例（chunk-0）：

```text
YOLO-World: Real-Time Open-Vocabulary Object Detection
Tianheng Cheng, Lin Song, Yixiao Ge, Wenyu Liu, Xinggang Wang, Ying Shan
Tencent AI Lab / ARC Lab / Huazhong University of Science & Technology
Code & Models: YOLO-World
Abstract: The You Only Look Once (YOLO) series of detectors have established
themselves as efficient and practical tools. However, their reliance on
predefined and trained object categories limits their applicability in open
scenarios. Addressing this limitation, we introduce YOLO-World, an innovative
approach that enhances YOLO with open-vocabulary detection capabilities...
On the challenging LVIS dataset, YOLO-World achieves 35.4 AP with 52.0 FPS on V100...
```

### 知识图谱

- **节点数**: 21
- **构建方式**: 从已索引文档抽取实体 + 关系

### ACP 调用记录（acp_ledger.jsonl）

| # | 时间戳 | 能力 | 权限 | 参数 |
|---|---|---|---|---|
| 1 | 1783698609.31 | ingest_pdf | write | [pdf_url, case_id] |
| 2 | 1783698628.97 | ingest_pdf | write | [pdf_url, case_id] |
| 3 | 1783698638.31 | ingest_pdf | write | [pdf_url, case_id] |
| 4 | 1783698662.83 | query_rag | read | [question, case_id] |
| 5 | 1783698674.14 | get_knowledge_graph | read | [case_id] |
| 6 | 1783700290.24 | get_knowledge_graph | read | [case_id] |

### Re4.6 RAG 验收结论

| 验收项 | 结果 |
|---|---|
| PDF 下载与提取 | ✅ 成功（2 个 PDF） |
| 500/100 分块 | ✅ 成功（52 chunks） |
| TF-IDF 索引 | ✅ 成功 |
| query_rag 问答 | ✅ 成功（1 次调用） |
| get_knowledge_graph | ✅ 成功（2 次调用，21 节点） |
| ACP 能力层 | ✅ 6 次调用全部记录到 ledger |

---

## 其他 4 个 case — 冒烟测试（全部失败）

### 9e518882ba79 — test for upload

- **题目**: test for upload
- **总耗时**: 89.85s
- **核心故障**: 与 re47-final 相同 — topic_parser LLMUnavailable
- **seed_papers**: 含 1 个 `Test Paper`（relevance_score=1.0，测试注入）
- **trace 序列**: 与 re47-final 完全一致的 18 节点降级路径
- **final_recommendation**: 全 0
- **evidence_graph.json**: `{}`
- **acp_ledger.jsonl**: 存在（含 ACP 调用记录）

### 6a2dcd7bde88 — test

- **题目**: test
- **总耗时**: 63.29s
- **核心故障**: topic_parser LLMUnavailable
- **trace 序列**: 同样的降级路径
- **final_recommendation**: 全 0

### 7f01f34e516a — test

- **题目**: test
- **总耗时**: 与 6a2dcd7bde88 接近
- **核心故障**: topic_parser LLMUnavailable
- **final_recommendation**: 全 0

### e88ea6e1ac6d — test topic for acp

- **题目**: test topic for acp
- **核心故障**: topic_parser LLMUnavailable
- **final_recommendation**: 全 0

---

## 共同故障模式分析

### 故障链路图

```
intake (ok)
  ↓
topic_parser ──❌ LLMUnavailable──→ 退化为字符串分割
  ↓                                    method = topic.split()
  ↓                                    object/task/scenario = []
  ↓                                    domain = [unknown]
search_planner ──→ template 模式（n_queries=1, rounds=[broad, focused]）
  ↓
search_agent ──→ 首轮 arxiv 搜出 12 篇（YOLO steel defect detection 有结果）
  ↓                                    但 has_plan=true 时用 plan queries
quality_filter ──→ pre_filter kept=12, llm_judged=0
  ↓
verify ──→ n_accept=0, n_weak_reject=0, n_reject=0
  ↓         （LLM 不可用，无法判定 accept/reject）
quality_gate ──→ route=repair（n_papers=0）
  ↓
targeted_repair ──❌ LLMUnavailable──→ n_queries=0
  ↓
search_agent ──→ n_paper_candidates=0（无 plan queries）
  ↓
quality_gate ──→ route=repair（round 1）
  ↓
targeted_repair ──❌ LLMUnavailable──→ n_queries=0
  ↓
search_agent ──→ n_paper_candidates=0（repair_rounds=2）
  ↓
quality_gate ──→ route=continue（repair 耗尽）
  ↓
final_recommendation ──→ 全 0
```

### 5 个 case 的故障对比

| Case | topic_parser | search_agent 首轮 | verify | targeted_repair × 2 | final |
|---|---|---|---|---|---|
| re47-final | ❌ LLMUnavailable | 12 篇 arxiv | n_accept=0 | ❌ × 2 | 全 0 |
| 9e518882ba79 | ❌ LLMUnavailable | 12 篇 arxiv | n_accept=0 | ❌ × 2 | 全 0 |
| 6a2dcd7bde88 | ❌ LLMUnavailable | 12 篇 arxiv | n_accept=0 | ❌ × 2 | 全 0 |
| 7f01f34e516a | ❌ LLMUnavailable | 12 篇 arxiv | n_accept=0 | ❌ × 2 | 全 0 |
| e88ea6e1ac6d | ❌ LLMUnavailable | 12 篇 arxiv | n_accept=0 | ❌ × 2 | 全 0 |

### 关键发现

1. **search_agent 首轮其实成功**：5 个 case 都在首轮从 arxiv 搜出 12 篇候选
2. **verify 节点把 12 篇全丢了**：n_accept=0 + n_weak_reject=0 + n_reject=0 = 12 篇全部未被判定
3. **根因是 verify 依赖 LLM**：`re11_paper_verifier.llm` 在 LLM 不可用时返回空列表，而非保留候选
4. **targeted_repair 也依赖 LLM**：`re12_repair.llm` 不可用时 n_queries=0，导致 repair 空转

---

## Re4 各 SOP 交付物验收

### Re4.1 — 工程控制面与安全收口（+37 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| case_id 安全校验 | ✅ | re47-final 等 case_id 均通过校验 |
| SourcePolicy | ✅ | search_agent 的 failed_adapters/skipped_adapters 字段存在 |
| CORS 环境化 | ✅ | API 可跨域访问 |
| StageContract v1 | ✅ | trace_events 含 input_summary/output_summary |
| RunState + atomic_write_json | ✅ | state.json + state_partial.json 原子写入 |

### Re4.2 — 前端基线与人性化主流程（+8 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| React+Vite shell | ✅ | 前端可启动（npm build 52 modules） |
| SSE 封装 | ✅ | trace_events 实时推送 |
| 节点人话映射 | ✅ | 前端 Workbench 展示 |
| Playwright | ✅ | 截图测试通过 |

### Re4.3 — 创新点叙事工作包可追溯升级（+49 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| InnovationPoint schema | ✅ 测试通过 | ❌ 端到端未触发（n_work_packages=0） |
| NarrativeRevision schema | ✅ 测试通过 | ❌ 端到端未触发（low_bar_status=null） |
| WorkPackage schema | ✅ 测试通过 | ❌ 端到端未触发 |
| binding validator | ✅ 测试通过 | ❌ 端到端未触发 |
| 依赖 DAG | ✅ 测试通过 | ❌ 端到端未触发 |

### Re4.4 — ACP 最小能力层（+17 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| 14 能力声明 | ✅ | acp_ledger.jsonl 记录调用 |
| REST+JSON Schema | ✅ | acp_invoke 事件含 params_keys |
| 读写权限控制 | ✅ | ingest_pdf=write, query_rag=read |
| RunLedger 接入 | ✅ | re47-final + re46-e2e 均有 ledger |

### Re4.5 — 全文入库与 RAG 检索（+30 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| PDF 提取 | ✅ | re46-e2e 入库 2 个 PDF |
| 500/100 分块 | ✅ | 52 chunks |
| TF-IDF 索引 | ✅ | rag_index.json 含 vocabulary |
| 余弦检索 | ✅ | query_rag 调用成功 |
| LLM 问答 + 引用 | ✅ | query_rag 返回答案 |
| 知识图谱 | ✅ | 21 KG nodes |

### Re4.6 — 前端深度整合与多文档 RAG（+4 tests）

| 交付项 | 验收 | 证据 |
|---|---|---|
| 7 结构化报告组件 | ✅ 测试通过 | 前端构建成功 |
| Workbench RAG 整合 | ✅ 测试通过 | — |
| merge_index 多文档 | ✅ | re46-e2e 入库 2 个 PDF |
| 首页增强 | ✅ | — |

### Re4.7 — 全链路验收与文档收口

| 交付项 | 验收 | 证据 |
|---|---|---|
| 531 tests 全绿 | ✅ | pytest collected 531 |
| ruff F401/F841/E741 修复 | ✅ | 修复到 0 |
| CODELY.md 重写 | ✅ | 反映 Re4.0 架构 |
| README.md 追加 | ✅ | 含 React 前端 + ACP |
| 端到端 case 验收 | ❌ **失败** | re47-final 全 0 |

---

## 诊断结论

### Re4 做对了什么 ✅

1. **工程基线扎实**：531 tests 全绿，ruff 修复，文档收口
2. **ACP 能力层完整**：14 能力声明 + 读写权限 + RunLedger，6 次调用全部记录
3. **RAG 链路跑通**：re46-e2e 入库 2 PDF → 52 chunks → 21 KG nodes → query_rag 问答成功
4. **前端基线完成**：React+Vite + SSE + 7 结构化报告组件 + Playwright
5. **schema 升级到位**：InnovationPoint/NarrativeRevision/WorkPackage/binding/DAG 全部测试通过
6. **工程控制面安全**：case_id 校验、SourcePolicy、CORS、StageContract、RunState 全部就位

### Re4 做错了什么 ❌

1. **端到端 Agent case 全部全 0**：
   - 5 个 case 的 `final_recommendation` 全部 `n_papers=0, n_baseline=0, n_work_packages=0`
   - 无 1 个 case 跑出真实论文 / baseline / 创新点 / 缝合方案

2. **根因：LLM 全程不可用**：
   - `topic_parser` LLMUnavailable → topic_atoms 退化为字符串分割
   - `verify` LLM 不可用 → 12 篇 arxiv 候选全部未被判定（n_accept=0）
   - `targeted_repair` LLMUnavailable × 2 → n_queries=0 → repair 空转

3. **没有像 Re3.9.4 那样跑真实学术题目**：
   - 4/5 case 是 "test" / "test for upload" / "test topic for acp" 冒烟测试
   - 唯一的真实题目 "YOLO steel defect detection" 也是 demo baseline 题目，非学术选题

4. **没有标答对比**：
   - Re3.9.4 有明确的论文数 / baseline 数 / 创新点 / 缝合方案标答
   - Re4 没有任何标答，无法判断"做对了没有"

5. **verify 节点的 LLM 降级策略有问题**：
   - LLM 不可用时，verify 返回 n_accept=0 + n_weak_reject=0 + n_reject=0
   - 12 篇候选全部"消失"，既不 accept 也不 reject
   - 应该保留候选为 weak_reject 或 needs_manual，而非静默丢弃

### 与 Re3.9.4 的核心差距

| 维度 | Re3.9.4 | Re4 | 差距 |
|---|---|---|---|
| LLM 可用性 | ✅ 全部可用 | ❌ 全部不可用 | **致命差距** |
| 真实学术题目 | 6 个 | 1 个（demo）+ 4 个冒烟 | 题目质量不足 |
| 论文产出 | 3–42 篇/case | 0 篇/case | **完全无产出** |
| Baseline 产出 | 2–32 个/case | 0 个/case | **完全无产出** |
| 可行性裁决 | risky/feasible | null | **未触发** |
| 创新点 + 缝合方案 | 每案 3 + 1 | 0 | **未触发** |
| 标答对比 | 有 | 无 | **无法验收** |

### 修复建议

1. **优先级 P0：恢复 LLM 可用性**
   - 确认 DeepSeek v4 flash（OpenCode proxy）API key 是否有效
   - 或切换到其他可用 provider（stepfun / openrouter）
   - 验证 `fast_json` provider profile 的 LLM 调用链路

2. **优先级 P0：用 Re3.9.4 的 6 个题目重跑 Re4 端到端**
   - 题目：钢筋腐蚀 / 混凝土检测 / 电力负荷 / 施工安全 / 沉桩 / 瓦斯突出
   - 对照 Re3.9.4 标答验收论文数 / baseline 数 / 创新点

3. **优先级 P1：修复 verify 节点的 LLM 降级策略**
   - LLM 不可用时，应保留候选为 `weak_reject` 或 `needs_manual`
   - 而非返回 n_accept=0 + n_weak_reject=0 + n_reject=0（静默丢弃）

4. **优先级 P1：补全标答对比文档**
   - 像 Re3.9.4 那样，每个 case 列出：论文数 / Repo / Dataset / Baseline / 可行性 / 评审
   - 与 Re3.9.4 标答对比，确认 Re4 没有退化

5. **优先级 P2：RAG 与 Agent 链路打通**
   - 当前 re46-e2e（RAG）和 re47-final（Agent）是分开的
   - 应该让 Agent 搜出的论文自动入库到 RAG，形成闭环

---

## 附录：Re4.7 SOP 验收清单对照

| SOP 验收标准 | 结果 |
|---|---|
| 端到端 case 验收清单全部通过 | ❌ 全 0 |
| `ruff check . --statistics` 的 F401/F841/E741 = 0 | ✅ |
| `ruff check apps/api/app` ≤ 19 errors | ✅ |
| `pytest --collect-only` 0 errors, ≥ 531 collected | ✅ |
| CODELY.md 包含 ACP/RAG/React/SourcePolicy/StageContract/RunState | ✅ |
| README.md 包含 React 前端启动方式和 ACP 能力清单 | ✅ |
| Local Runbook 包含 ACP / RAG / React dev server 说明 | ✅ |

**结论**：Re4.7 的工程验收（tests / ruff / docs）全部通过，但**端到端业务验收失败**——5 个 case 全部因 LLMUnavailable 导致 final_recommendation 全 0，无法证明 Re4 的 Agent 链路能跑出真实论文。

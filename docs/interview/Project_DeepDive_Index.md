# PaperAgent · 项目深挖索引（Session 40）

> 面试时被问「这个项目有什么可以深挖的？」，可以指向本文档。
> 每个模块都有：核心文件 + 关键设计 + 面试追问点。

---

## 索引

| 模块 | 核心文件 | 关键设计 | 面试追问 |
|---|---|---|---|
| 1. 多阶段 Workflow | `apps/api/app/api/v1/one_topic.py` | 8 Step Deck + Gate 拦截 | 哪步最容易出错？ |
| 2. 证据治理 | `apps/api/app/services/evidence.py` + `evidence_refs.py` | 5 级晋升 + 前后端双 Gate | 候选和证据的边界？ |
| 3. RAG Pipeline | `apps/api/app/services/rag_pipeline.py` | Hybrid + RRF + 5 因子 Rerank | RRF 为什么比线性融合好？ |
| 4. RAG 评估 | `apps/api/app/services/rag_evaluator.py` | 8 指标 + 5 检测器 | 哪个指标最重要？ |
| 5. 4 层 Agent Memory | `apps/api/app/services/project_memory.py` | ShortContext/Transcript/ProjectMemory/EvidenceMemory | 压缩会不会丢东西？ |
| 6. Replay 恢复 | `apps/api/app/services/project_memory.py` | snapshot + 最近 events 合并 | 刷新页面怎么恢复？ |
| 7. Readiness 8 维 | `apps/api/app/services/readiness.py` | hard-block + warn 分离 | 哪一维最重要？ |
| 8. Failure Cases | `docs/interview/Failure_Cases.md` | 16 个真实案例 | 哪个最关键？ |
| 9. MCP Server | `apps/api/app/mcp/server.py` + `tools.py` + `permissions.py` | 4 tools + 3 层权限 | 为什么 4 个不多给？ |
| 10. Multi-Agent 设计 | `apps/api/app/services/agent_router.py` | 7 roles + 4 维 cost | 什么时候拆？ |
| 11. LLM Fallback | `apps/api/app/services/llm.py` + `heuristic_*` | 双路径 + JSON 模式 | LLM 挂掉怎么办？ |
| 12. 测试金字塔 | `apps/api/tests/` + `apps/web/e2e/` | ~470 后端 + ~30 Playwright | 怎么防回退？ |
| 13. Trace 审计 | `apps/api/app/services/trace_store.py` | NDJSON + in-memory 缓存 | 审计怎么用？ |
| 14. RunEvent 持久化 | `apps/api/app/services/run_event.py` | JSONL + seq 自增 | 事件太多会爆炸吗？ |
| 15. School Templates | `apps/api/app/services/report_templates.py` | 3 模板 + template_key 路由 | 怎么扩展新模板？ |

---

## 模块 1：多阶段 Workflow

**核心文件：** `apps/api/app/api/v1/one_topic.py`（主要路由 ~1900 行）

**8 步 Step Deck：**
1. `analyze` — 题目分析 + D 评级拦截
2. `keyword_review` — 关键词确认 Gate 1
3. `query_plan` — 检索词生成 Gate 2
4. `retrieval` — 三线检索（paper/dataset/repo）
5. `candidate_scoring` — 候选评分
6. `feasibility` — 7 维风险评估 Gate 3
7. `evidence_promotion` — 证据晋升
8. `proposal_draft` — 报告草稿

**关键设计：**
- 每步独立 schema (`*_request.py`, `*_response.py`)
- 前一步没完成 → 409 Conflict
- 所有 step 写 Trace + RunEvent

**面试追问：**
- 「哪步最容易出错？」 → retrieval（依赖外部 mock 数据源）
- 「为什么用 409 而不是 422？」 → 状态不一致是业务错误，不是请求格式错
- 「8 步能合并吗？」 → 不行，Gate 强约束

**可展示代码：**
- `apps/api/app/api/v1/one_topic.py:797` — `build_final_package` 路由
- `apps/api/app/schemas_*.py` — 11 个 Pydantic schema

---

## 模块 2：证据治理

**核心文件：**
- `apps/api/app/services/evidence.py` (~520 行)
- `apps/api/app/services/evidence_refs.py` (~620 行)
- `apps/api/app/services/verification.py` (URL 验证)

**5 级晋升：**
```
candidate → selected → url_verified → evidence → cited
```

**关键设计：**
- **前后端双 Gate** — 前端阻止 UI 操作，后端 409 拒 API
- **不可降级** — evidence 永不被回退到 candidate
- **URL 验证** — HTTP HEAD + 状态码 + 响应时间

**面试追问：**
- 「Candidate 和 Evidence 的边界？」 → URL 是否验证过
- 「怎么防 LLM 编 URL？」 → URL 必须 HEAD 200
- 「为什么不可降级？」 → 学术引用必须稳定

**可展示代码：**
- `apps/api/app/services/evidence.py:376` — `update_review()`
- `apps/api/app/services/verification.py:80` — `verify_url()`

---

## 模块 3：RAG Pipeline

**核心文件：** `apps/api/app/services/rag_pipeline.py` (NEW, S34)

**6 步 pipeline：**
1. Query 扩展
2. Sparse 检索 (BM25 mock)
3. Dense 检索 (Embedding mock)
4. RRF 融合
5. 5 因子 Rerank
6. 截断 top_k

**关键设计：**
- **RRF (Cormack 2009)**: 不需要 score 校准
- **5 因子 Rerank**: 关键词/年份/引用/类型/来源
- **Mock embedding**: 离线可测、可解释

**面试追问：**
- 「RRF 为什么比线性融合好？」 → 不需要 score 校准，BEIR 验证
- 「5 因子权重怎么定？」 → 启发式 (0.4/0.2/0.2/0.1/0.1)，未做 A/B
- 「Embedding 真实环境用什么？」 → sentence-transformers / BGE

**可展示代码：**
- `apps/api/app/services/rag_pipeline.py:60` — RRF
- `apps/api/app/services/rag_pipeline.py:120` — Rerank

---

## 模块 4：RAG 评估

**核心文件：** `apps/api/app/services/rag_evaluator.py` (NEW, S34)

**8 指标 + 5 检测器：**

8 指标：nDCG@10 / MRR / Recall@K / Precision@K / Coverage / Diversity / Latency / Cost

5 检测器：empty_retrieval / low_recall / hallucinated_url / duplicate_top_k / off_topic

**关键设计：**
- 评估不是花架子，能定位具体问题
- failure detector 是产品稳定性的关键

**面试追问：**
- 「哪个指标最重要？」 → nDCG@10（排序质量）
- 「failure detector 怎么用？」 → 触发后 fallback / 提示用户
- 「为什么不用 BLEU？」 → RAG 不是文本生成，是检索排序

**可展示代码：**
- `apps/api/app/services/rag_evaluator.py:80` — `compute_ndcg()`
- `apps/api/app/services/rag_evaluator.py:200` — `detect_empty_retrieval()`

---

## 模块 5：4 层 Agent Memory

**核心文件：** `apps/api/app/services/project_memory.py` (NEW, S35)

**4 层：**
1. **ShortContext** — 浏览器运行时
2. **Transcript** — RunEvent JSONL
3. **ProjectMemory** — 项目级 snapshot
4. **EvidenceMemory** — 不可变证据

**6 类 critical 事件：**
- user_patch / gate / evidence_promotion
- url_verified / readiness_check / llm_call

**面试追问：**
- 「压缩会不会丢东西？」 → 6 类 critical 100% 保留
- 「Evidence 为什么单独一层？」 → 学术引用必须稳定
- 「为什么用 JSONL 不用 SQLite？」 → MVP 阶段简单优先

**可展示代码：**
- `apps/api/app/services/project_memory.py:120` — `compress_transcript()`
- `apps/api/app/services/project_memory.py:200` — `replay_project()`

---

## 模块 6：Replay 恢复

**核心文件：** `apps/api/app/services/project_memory.py`

**恢复流程：**
1. 加载 ProjectMemorySnapshot（cold start 概要）
2. 加载 Transcript events（from_seq 之后）
3. 合并 step_states
4. 前端重建 Step Deck

**`replay_source` 字段：** 告诉前端数据来源

**面试追问：**
- 「刷新页面怎么恢复？」 → 1) 检测 last_seq 2) 显示恢复按钮 3) 调 /memory/replay
- 「Replay 失败怎么办？」 → snapshot 在就用 snapshot，都没有就显示"重新开始"

**可展示代码：**
- `apps/api/app/services/project_memory.py:replay_project()`

---

## 模块 7：Readiness 8 维

**核心文件：** `apps/api/app/services/readiness.py`

**8 维：**
1. section_completeness
2. evidence_binding
3. reference_integrity
4. template_fit
5. risk_disclosure
6. workload_clarity
7. innovation_claim_safety
8. format_basic

**关键设计：**
- `hard_block` 维度失败 → 整体 fail
- `warn` 维度失败 → 整体 warn
- export_allowed = (overall != fail)

**面试追问：**
- 「哪一维最重要？」 → evidence_binding（硬约束）
- 「夸大意词怎么检测？」 → 13 个中英文词 + 模式匹配
- 「为什么不全 hard_block？」 → 保留 warn 提示，用户体验更友好

**可展示代码：**
- `apps/api/app/services/readiness.py:243` — `_check_innovation_claim_safety()`

---

## 模块 8：Failure Cases

**核心文件：** `docs/interview/Failure_Cases.md` (16 cases)

**16 个真实失败案例，分布在：**
- Feasibility (Case 1, 2, 4)
- Evidence (Case 3)
- Readiness (Case 5, 6, 9, 10)
- LLM Fallback (Case 7)
- Multi-source (Case 8)
- Memory (Case 11, 15)
- MCP (Case 12)
- Multi-Agent (Case 13)
- RAG (Case 14)
- Replay (Case 16)

**面试追问：**
- 「哪个最关键？」 → Case 3 (URL 404) — 学术诚信底线
- 「失败怎么映射到测试？」 → 每个 case 都标了 test_session 编号

**可展示代码：**
- `apps/api/app/services/evidence.py:295` — add_paper_manual (Case 3 失败时)
- `apps/api/app/services/readiness.py:243` — innovation_claim_safety (Case 5)
- `apps/api/tests/test_session32_readiness.py` — readiness 硬拦截测试

---

## 模块 9：MCP Server

**核心文件：**
- `apps/api/app/mcp/server.py` (NEW, S36)
- `apps/api/app/mcp/tools.py`
- `apps/api/app/mcp/permissions.py`

**4 个 tools + 6 个 forbidden：**

4 tools: search_topic_evidence / get_candidate_resources / get_project_trace / check_export_readiness

6 forbidden: promote_candidate / generate_proposal / delete_project / write_file / shell_exec / modify_evidence

**3 层权限：**
1. 白名单 (manifest)
2. 黑名单 (FORBIDDEN_TOOLS)
3. Gate 前置 (keyword gate / FinalPackage)

**面试追问：**
- 「为什么 4 个不多给？」 → SOP 明确不暴露写/破坏操作
- 「怎么防越权？」 → 3 层 + Trace 审计
- 「HTTP vs stdio？」 → 当前 HTTP（Playwright 可测），未来 stdio

---

## 模块 10：Multi-Agent 设计

**核心文件：** `apps/api/app/services/agent_router.py` (NEW, S37)

**7 roles + 4 维 cost budget：**

7 roles: supervisor / keyword / retrieval / verification / feasibility / proposal / review

4 维 cost: max_agent_count=8 / max_llm_calls=20 / max_parallel_tasks=3 / max_rounds=5

**关键不变量：** 所有 agent 都不能直接写 evidence（schema 限制）

**面试追问：**
- 「什么时候拆？」 → 检索源 ≥ 5 / 评分模型 ≥ 3 / 模板 ≥ 5
- 「Supervisor 瓶颈？」 → 严格不调 LLM，只做调度
- 「成本怎么控？」 → 4 维硬限制 + 2 降级开关

---

## 模块 11：LLM Fallback

**核心文件：**
- `apps/api/app/services/llm.py` (统一入口)
- `apps/api/app/services/llm_content.py` (prompt 模板)
- `apps/api/app/services/keyword_search_assistant.py` (heuristic 兜底)

**双路径设计：**
- LLM JSON 模式失败 → heuristic 规则
- API 报错 → 默认候选列表

**面试追问：**
- 「LLM 挂掉怎么办？」 → heuristic 兜底 + 错误码返回
- 「为什么 95% 不需要 LLM？」 → 启发式规则已经够用

---

## 模块 12：测试金字塔

**核心目录：**
- `apps/api/tests/` — ~470 后端测试
- `apps/web/e2e/` — ~30 Playwright E2E

**测试类型：**
- 单元测试 (service 级别)
- 集成测试 (TestClient)
- E2E (Playwright + 真实 API)

**面试追问：**
- 「怎么防回退？」 → S31 baseline 专门测
- 「为什么不用 mutation testing？」 → 成本太高

---

## 模块 13：Trace 审计

**核心文件：** `apps/api/app/services/trace_store.py`

**存储：** `.runtime/traces/{project_id}.jsonl`

**关键事件类型：**
- mcp_tool_call / user_patch / gate / evidence_promotion / readiness_check / llm_call

**面试追问：**
- 「审计怎么用？」 → 任何 step 都能回放
- 「JSONL vs SQLite？」 → MVP 用 JSONL，调试方便

---

## 模块 14：RunEvent 持久化

**核心文件：** `apps/api/app/services/run_event.py` (NEW, S27)

**存储：** `.runtime/runs/{project_id}/{run_id}/events.jsonl`

**关键字段：** event_id / seq / step_key / event_type / status / payload / ts

**面试追问：**
- 「事件太多会爆炸吗？」 → 触发压缩（critical 100% 保留）

---

## 模块 15：School Templates

**核心文件：** `apps/api/app/services/report_templates.py`

**3 模板：**
- default — 默认
- engineering — 工程类
- cv_ai — 计算机视觉 / AI 类

**关键设计：** template_key 路由，每个模板独立章节结构

**面试追问：**
- 「怎么扩展新模板？」 → 加 Pydantic schema + section 配置

---

## 深挖入口建议

| 面试官说 | 推荐深挖 |
|---|---|
| 「讲讲你最满意的一个模块」 | 模块 2（证据治理）或模块 7（Readiness） |
| 「讲讲 RAG」 | 模块 3 + 模块 4 |
| 「讲讲 Agent 状态机」 | 模块 1 + 模块 5 + 模块 6 |
| 「讲讲多 Agent」 | 模块 10 |
| 「讲讲 MCP / 工具调用」 | 模块 9 |
| 「讲讲失败案例」 | 模块 8 |
| 「讲讲测试」 | 模块 12 |
| 「讲讲你怎么权衡的」 | 任何模块 + Known_Limitations 引用 |

---

> **项目深挖索引的核心：让面试官知道「这个项目值得聊的有很多」。**
> **不要试图在 3 分钟内讲完所有模块——选 1-2 个深挖。**
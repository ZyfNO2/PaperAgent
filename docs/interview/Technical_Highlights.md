# PaperAgent · 技术亮点收束（Session 40）

> 5 个核心亮点，覆盖：Agent 流程 / 证据治理 / 可回放工程闭环 / RAG 评估 / 导出硬拦截
> 每个亮点有：核心思想 / 项目证据 / 可展示文件 / 面试展开

---

## 亮点 1：多阶段科研证据 Agent Workflow

**核心思想：** 8 步 Step Deck 串成 pipeline，每步都有 Gate 校验，前一步没过下一步 409 拒。强顺序、强一致性、强可审计。

**为什么是亮点：**
- 不是 LLM 聊天框，是工程化 pipeline
- Gate 是硬约束，不是软提示
- 状态可恢复（4 层 Memory）

**项目证据：**
- `apps/api/app/api/v1/one_topic.py` — 主路由 ~1900 行，~35+ 端点
- `apps/api/app/schemas_*.py` — 11 个 Pydantic schema
- `apps/web/src/components/StepDeck.vue` — 前端 Step Deck

**可展示文件：**
- `apps/api/app/api/v1/one_topic.py:797` — `build_final_package` 路由
- `apps/api/tests/test_session31_full_chain_baseline.py` — 完整链路 baseline

**面试展开模板：**

> 「我做了一个 8 步 Step Deck：题目输入 → 关键词拆解 → 检索词生成 → 三线检索 → 候选评分 → 可行性裁决 → 证据晋升 → 报告草稿。每步都有 Gate 校验，前一步没完成下一步直接 409 拒。这样做的好处是**状态强一致**——你永远不会看到『报告生成但没有证据』这种不一致状态。」

**追问应对：**
- 「哪步最容易出错？」 → retrieval 步骤依赖外部 mock 数据源
- 「为什么是 8 步不是 5 步？」 → 因为证据晋升和报告草稿需要独立 gate

---

## 亮点 2：Candidate → Evidence 的证据治理闸门

**核心思想：** 5 级晋升（candidate → selected → url_verified → evidence → cited）+ URL 验证 + 前后端双 Gate。

**为什么是亮点：**
- 候选 ≠ 证据，URL 必须 HEAD 200 才能晋升
- 学术诚信底线，杜绝 LLM 编 URL
- 不可降级——evidence 永不被回退

**项目证据：**
- `apps/api/app/services/evidence.py` — evidence CRUD
- `apps/api/app/services/evidence_refs.py` — 引用构造
- `apps/api/app/services/verification.py` — URL 验证
- `apps/api/tests/test_session26_evidence_promotion.py`

**可展示文件：**
- `apps/api/app/services/evidence.py:376` — `update_review()`
- `apps/api/app/services/verification.py:80` — `verify_url()`

**面试展开模板：**

> 「证据治理是论文系统的底线。LLM 容易编 URL，所以我设计了 5 级晋升：候选 → 选中 → URL 验证 → 证据 → 引用。每一步都有 Gate 校验，**前后端双重拦截**。URL 必须 HTTP HEAD 返回 200，否则永远停在 candidate 状态，永远不会进报告。」

**追问应对：**
- 「URL 失效怎么办？」 → 降级回 candidate，从 EvidenceLedger 移除
- 「为什么不可降级？」 → 学术引用必须稳定，引用过的不许悄悄消失

---

## 亮点 3：RunEvent / Trace / Snapshot 的可回放工程闭环

**核心思想：** 4 层 Agent Memory (ShortContext / Transcript / ProjectMemory / EvidenceMemory) + RunEvent JSONL + Snapshot 重建 + critical 事件压缩不丢。

**为什么是亮点：**
- 刷新页面能自动 replay 恢复（< 200ms）
- 关键事件（user_patch / gate / evidence_promotion）100% 保留
- EvidenceMemory 独立层，永不被压缩

**项目证据：**
- `apps/api/app/services/project_memory.py` (NEW, S35)
- `apps/api/app/services/run_event.py` (S27)
- `apps/api/app/services/trace_store.py`
- `apps/api/tests/test_session35_agent_memory_replay.py` — 14 测试

**可展示文件：**
- `apps/api/app/services/project_memory.py:120` — `compress_transcript()`
- `apps/api/app/services/project_memory.py:200` — `replay_project()`

**面试展开模板：**

> 「我设计了 4 层 Agent Memory：ShortContext（浏览器运行时）/ Transcript（RunEvent JSONL）/ ProjectMemory（项目级 snapshot）/ EvidenceMemory（不可变证据）。关键事件压缩 100% 保留，EvidenceMemory 独立于 transcript 永不被压缩。**用户刷新页面能自动 replay 恢复**——cold start < 200ms，体验无感。」

**追问应对：**
- 「压缩会不会丢东西？」 → 6 类 critical 100% 保留
- 「为什么用 JSONL 不用 SQLite？」 → MVP 简单优先，调试方便
- 「Evidence 为什么单独一层？」 → 学术引用必须稳定

---

## 亮点 4：面试级 RAG Pipeline 与评估设计

**核心思想：** Hybrid (Sparse + Dense) + RRF 融合 + 5 因子 Rerank + 8 评估指标 + 5 个失败检测器。

**为什么是亮点：**
- 不是「接个 LangChain」，是 6 步显式 pipeline
- 评估不是花架子，能定位具体问题
- failure detector 是产品稳定性的关键

**项目证据：**
- `apps/api/app/services/rag_pipeline.py` (NEW, S34)
- `apps/api/app/services/rag_evaluator.py` (NEW, S34)
- `apps/api/tests/test_session34_rag_pipeline_eval.py` — 25 测试
- `apps/web/e2e/test_one_topic_session34_rag_eval.py` — 8 Playwright

**可展示文件：**
- `apps/api/app/services/rag_pipeline.py:60` — RRF 实现
- `apps/api/app/services/rag_evaluator.py:80` — `compute_ndcg()`

**面试展开模板：**

> 「RAG 不是『接个 LangChain』，是 6 步显式 pipeline：Query 扩展 → Sparse 检索 (BM25) → Dense 检索 (Embedding) → RRF 融合 → 5 因子 Rerank → 截断 top_k。评估用 8 个指标（nDCG@10、MRR、Recall、Coverage 等）+ 5 个失败检测器（empty_retrieval、low_recall、hallucinated_url 等）。**评估不是花架子，能定位具体问题**——比如 hallucinated_url 触发后会自动降级。」

**追问应对：**
- 「RRF 为什么比线性融合好？」 → Cormack 2009, 不需要 score 校准
- 「5 因子权重怎么定？」 → 启发式 0.4/0.2/0.2/0.1/0.1
- 「Embedding 真实环境用什么？」 → sentence-transformers / BGE

---

## 亮点 5：导出前 Readiness 与失败案例硬拦截

**核心思想：** 8 维 Readiness 检查（section_completeness / evidence_binding / template_fit / risk_disclosure / innovation_claim_safety / 等）+ hard-block 维度 + 16 个真实失败案例映射。

**为什么是亮点：**
- 不是「导出来再 review」，是「不满足不让导出」
- 夸大意词（13 个中英文词）直接阻断
- 风险章节缺失直接阻断
- 缺数据集、缺 baseline 命中硬否决

**项目证据：**
- `apps/api/app/services/readiness.py` — 8 维检查
- `apps/api/app/schemas_readiness.py` — schema
- `apps/api/tests/test_session32_readiness.py` — readiness 测试
- `docs/interview/Failure_Cases.md` — 16 案例

**可展示文件：**
- `apps/api/app/services/readiness.py:243` — `_check_innovation_claim_safety()`
- `docs/interview/Failure_Cases.md` — 完整 16 案例

**面试展开模板：**

> 「开题答辯老師必問『你這個方案可能遇到什麼問題』。PaperAgent 把 8 維 Readiness 作為導出前置條件：缺風險章節、誇大創新詞、無數據集、無 baseline ——都直接阻斷。**不是『導出來再 review』，是『不滿足不讓導出』**。這是工程系統對學術標準的內化。」

**追问应对：**
- 「哪一维最重要？」 → evidence_binding（硬约束）
- 「为什么不全 hard_block？」 → 保留 warn 提示，用户体验更友好
- 「夸大意词怎么检测？」 → 13 个中英文词 + 模式匹配

---

## 5 个亮点总结表

| # | 亮点 | 关键词 | 对应 Session |
|---|---|---|---|
| 1 | 多阶段 Workflow | Step Deck + Gate | S18-S27 |
| 2 | 证据治理 | Candidate → Evidence | S24-S26 |
| 3 | Memory + Replay | 4 层 + 压缩 | S35 |
| 4 | RAG 评估 | Pipeline + 8 指标 | S34 |
| 5 | Readiness 硬拦截 | 8 维 + 失败案例 | S32 + S39 |

---

## 面试开场引用

> 「我这个项目有 5 个比较有意思的技术亮点：(1) 多阶段 Agent Workflow，(2) 证据治理闸门，(3) 4 层 Agent Memory，(4) 面试级 RAG，(5) 导出前 Readiness 硬拦截。您想听哪个？」

---

## 选亮点策略

| 面试官类型 | 推荐亮点 |
|---|---|
| AI / NLP 方向 | 亮点 4 (RAG) + 亮点 3 (Memory) |
| 后端 / 系统 | 亮点 1 (Workflow) + 亮点 3 (Memory) |
| 安全 / 合规 | 亮点 2 (证据治理) + 亮点 5 (Readiness) |
| 产品 / 业务 | 亮点 5 (Readiness) + 亮点 2 (证据治理) |
| 全栈 | 亮点 1 (Workflow) + 亮点 4 (RAG) |

---

> **技术亮点的核心：5 个不多不少，每个都能展开 3-5 分钟。**
> **不要试图一次讲完 5 个——选 1-2 个深挖。**
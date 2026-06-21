# PaperAgent 面试 QA 卡片（30 题）

> 本文件包含 30 道面试 QA 卡片，分 6 大类别，每类 5 题。
> 内容基于 PaperAgent (OneTopic MVP) 真实项目架构，无虚构能力。
> 撰写语言：繁体中文。

---

## 目录

- [Category 1: RAG（检索增强生成）](#category-1-rag检索增强生成)
- [Category 2: Agent](#category-2-agent)
- [Category 3: Memory / Transcript](#category-3-memory--transcript)
- [Category 4: Tool Calling / MCP](#category-4-tool-calling--mcp)
- [Category 5: Evaluation / Testing](#category-5-evaluation--testing)
- [Category 6: Safety / Boundary](#category-6-safety--boundary)

---

## Category 1: RAG（检索增强生成）

### Q1: 你的 RAG 为什么不是简单向量库？

**问题：** 为什么你的检索系统不是直接调一个向量数据库就完事了？搞 7 层检索是不是过度设计？

**面试官想考什么：** 你理解「学术检索」和「通用搜索」的核心差异；你有没有思考过搜索策略的取舍。

**PaperAgent 怎么回答：** 学术开题场景的检索和问答式 RAG 不同——用户不是问一个事实，而是需要理解一个领域的结构。我们设计了三线检索（论文 / 数据集 / 工程代码），每条线下有 2-3 个 source adapter（OpenAlex、Semantic Scholar、arXiv、GitHub、HuggingFace、Kaggle）。检索结果经过归一化、跨源去重（DOI / arxiv_id / OpenAlex ID / 标题 Jaccard 相似度）、评分排序、Evidence Ledger 入池。不依赖单向量库的原因是学术文献存在大量别名、版本、相同论文不同源的问题，纯向量召回会漏掉关键 baseline。我们的去重实现在 `apps/api/app/services/retrieval/dedup.py`，使用多 key 归一化 + 标题 Jaccard > 0.92 + 年份校验。

**项目证据：** `apps/api/app/services/retrieval/orchestrator.py`（协调器）、`apps/api/app/services/retrieval/dedup.py`（去重）、`apps/api/app/services/one_topic.py` 的 `collect_evidence()`。

**可展示文件：** `apps/api/app/services/retrieval/dedup.py` 第 12-50 行的多 key 去重函数。`apps/api/app/services/retrieval/orchestrator.py` 第 1-15 行的 9 步协调流程。

**风险补充：** 目前只做了轻量归一化，没有做论文全名/缩写词典。如果用户写的是非标准缩写（如把「Faster R-CNN」写成「FRCNN」），匹配率会下降。可以补充同义词扩展层。


### Q2: 检索到了不相关结果怎么办？

**问题：** 搜索引擎返回了大量无关论文，你怎么过滤？有没有办法不让用户看到垃圾结果？

**面试官想考什么：** 你如何处理检索噪声；你是有 passive filter 还是有 human-in-the-loop。

**PaperAgent 怎么回答：** 我们的系统有三道防线。第一道是 relevance scoring——每篇论文经过 0-1 评分，低于 0.3 的不参与可行性判断，paper_type 标记为 "irrelevant" 的直接排除。第二道是 review_status 体系——自动检索的论文入池后状态是 "pending"，用户可以在证据工作台里手动标记为 "accepted" / "core" / "rejected" / "needs_check"。被标记为 "needs_check" 的证据在生成报告时不会作为 supports，但会列出 warning。第三道是 LLM rerank（Session 6）——当 prefer 参数不是强制 heuristic 时，会调用 LLM 对检索结果做二次过滤，把明显不相关的去掉。LLM 路径如果失败会自动 fallback 到 heuristic 规则，不会让服务挂掉。

**项目证据：** `apps/api/app/services/scoring.py`（评分）、`apps/api/app/schemas_evidence.py` 的 `ReviewStatus`（审核状态）、`apps/api/app/services/one_topic.py` 的 `collect_evidence()`（整合检索与评分）。

**可展示文件：** `apps/api/app/schemas_evidence.py` 第 16 行的 `ReviewStatus` 定义。

**风险补充：** 目前评分是基于规则的启发式（年份、citation 数、paper_type 映射权重），不是基于 LLM-as-judge。如果面试官追问为什么不调 LLM 逐条评，可以说成本太高，启发式在已测试的 8 个学术领域上准确率已足够。


### Q3: 如何处理多模态数据？

**问题：** 你的 RAG 只能查论文吗？数据集、代码、指标这些不同类型的数据怎么处理？

**面试官想考什么：** 你有没有考虑不同数据类型的不同结构；你的 schema 设计是否灵活。

**PaperAgent 怎么回答：** 我们的证据系统统一用 `EvidenceItem` 模型覆盖五种类型：paper、dataset、repo、note、custom。每种类型有不同的专用字段。Paper 有 DOI / arxiv_id / OpenAlex ID 做去重，Dataset 有 scale / modality / annotation 描述，Repo 有 has_readme / has_training_script / has_eval_script 等可复现性字段。检索时不同类型的适配器不同：论文走 OpenAlex + arXiv，数据集走 HuggingFace + Kaggle，代码走 GitHub。检索结果在 Evidence Ledger 统一管理，有证据晋升机制（auto → pending → accepted → core）。这个设计在 `schemas_evidence.py` 第 1-20 行有完整说明。

**项目证据：** `apps/api/app/schemas_evidence.py`（EvidenceItem 定义）、`apps/api/app/services/retrieval/adapters/`（各源适配器）。

**可展示文件：** `apps/api/app/schemas_evidence.py` 第 14 行的 `EvidenceType` 定义和第 17 行的 `WorkspaceLane` 定义。`apps/api/app/services/retrieval/orchestrator.py` 第 61-69 行的 source-to-type 映射表。

**风险补充：** 目前 repo 的可复现性检查只是表面字段，没有实际跑代码验证。如果真的需要验证 baseline 可复现，还需要 Docker + GPU runner，目前超出 MVP 范围。


### Q4: 检索延迟怎么控制？

**问题：** 如果同时搜 arXiv、GitHub、HuggingFace 等 7 个源，用户要等多久？怎么保证不超时？

**面试官想考什么：** 你有没有考虑过系统性能和用户体验；你是同步等还是异步流式。

**PaperAgent 怎么回答：** 我们采取了三个手段控制延迟。第一是并行检索——orchestrator 在 Session 14 重构后对所有 adapter 使用 asyncio.gather 并发调用，最慢的源不会拖慢所有源。第二是 heuristic fallback——如果 LLM 路径太慢或网络不可用，系统自动降级到启发式规则（内置了 40+ 方法词/对象词映射），确保不通网络也能跑。第三是 SSE 流式——POST `/analyze/stream` 会边跑边推 "step" 事件，用户不需要干等，前端会逐步骤展示进度。实测一次完整的 6 段分析（拆解 + 理解 + 检索 + 可行性 + 推荐 + 审核）同步模式大约 3-8 秒，流式模式第一屏在 500ms 内出结果。

**项目证据：** `apps/api/app/api/v1/one_topic.py` 的 SSE 端点、`apps/web/stream_client.js`（前端流式客户端）。

**可展示文件：** `apps/api/app/services/one_topic.py` 第 1407-1424 行的 `run_one_topic_stream()` SSE emit 逻辑。

**风险补充：** 目前没有做检索结果缓存。相同关键词第二次搜还是会重跑所有 adapter。短期可以加一个简单的 LRU 缓存，减少重复查询。


### Q5: 你的 RAG 怎么评估？

**问题：** 你怎么知道你的检索系统好用？有没有量化指标？

**面试官想考什么：** 你有没有做检索质量评估；你的测试方法是 qualitative 还是 quantitative。

**PaperAgent 怎么回答：** 我们通过三个层次评估。第一是 dedup 准确率——在 retrieval 单元测试中验证了 DOI / arxiv_id / 标题 Jaccard > 0.92 + 年份四种去重逻辑。第二是 baseline fixtures——Session 17 将 YOLO 和高风险 MLLM 两个完整案例固化为 regression baseline，每次代码变更后跑全量回归对比，防止检索行为退化。第三是 coverage analysis——Session 7 的 `/refs/coverage` 端点分析证据覆盖情况，展示哪些维度缺少证据。此外我们有 32 个 Playwright E2E 验收测试覆盖了 happy path 和 fail path，包含检索环节的 UI 断言。后端 pytest 共 390 个测试（Session 32 完工状态），E2E 测试 32+ 个文件。

**项目证据：** `apps/api/tests/test_session17_demo_baseline.py`（baseline fixtures）、`apps/api/app/services/evidence_refs.py`（coverage 分析）、`docs/testing/Test_Matrix.md`（完整测试矩阵）。

**可展示文件：** `apps/api/app/services/retrieval/dedup.py` 第 138-194 行的 `_is_duplicate()` 函数。

**风险补充：** 目前没有做 NDCG / Recall@K 等检索排序指标。这是一项工程投入——需要人工标注每个查询的 ground truth 相关论文集，超出了 MVP 范围。

---

## Category 2: Agent

### Q6: Agent 记忆怎么设计？

**问题：** 你的 Agent 怎么记住之前发生的事情？如果用户关掉页面再打开，状态还在吗？

**面试官想考什么：** Agent 的持久化策略；你是靠对话上下文还是真正的持久化存储。

**PaperAgent 怎么回答：** 我们的 Agent 记忆分两层。第一层是 Trace 事件流（Session 11）——每个用户操作、Agent 决策、系统事件都记录为 `TraceEvent`，包含 actor / action / target_type / before / after 等字段。Trace 持久化为 JSONL 文件（`data/trace/{project_id}.jsonl`），支持按 project_id 查询全量事件。第二层是 RunEvent 持久化（Session 27）——以 run 为单位记录所有流式步骤的事件，字段包含 event_id、seq、run_id、step_key、event_type、status、payload、ts。RunState 持久化到 state.json，支持重新打开页面后恢复到上次进度。每个 project_id 独立走，不跨项目混淆。

**项目证据：** `apps/api/app/schemas_trace.py`（TraceEvent）、`apps/api/app/schemas_run_event.py`（RunEvent、RunState）。

**可展示文件：** `apps/api/app/schemas_trace.py` 第 13-31 行的 `TraceEvent` 定义。`apps/api/app/schemas_run_event.py` 第 19-33 行的 `RunEvent` 定义和第 36-49 行的 `RunState` 定义。

**风险补充：** 当前持久化是本地 JSONL 文件，不是数据库。在高并发场景下文件锁会成为瓶颈。计划中的升级路径是迁移到 SQLite 或 PostgreSQL。


### Q7: 你的 Agent 是 Stateful 还是 Stateless？

**问题：** 每次请求是独立的还是有关联状态的？

**面试官想考什么：** 你对 Agent 架构中 state management 的理解；Stateless 和 Stateful 的取舍。

**PaperAgent 怎么回答：** 我们采用了每个 project_id 独立状态的设计，介于纯 Stateless 和全 Stateful 之间。核心分析流程（`POST /analyze`）本身是无状态的——给定相同输入返回相同输出。但后续操作是有状态的：证据工作台（证据添加/评分/审核）、Trace 持久化、Workspace Board 的 lane 切换都依赖 project_id 作为上下文键。这种设计的好处是：分析阶段可以水平扩展（Stateless），而交互阶段通过 project_id 隔离状态（Stateful per project）。RunState 的回放机制（Session 27）允许用户关闭页面后重新打开，通过 GET `/runs/{project_id}` 恢复上一次的状态。

**项目证据：** `apps/api/app/services/evidence.py` 第 50-64 行的 `_LEDGER` 和 `_get_project()` 惰性初始化。`apps/api/app/api/v1/one_topic.py` 的 `project_id` 参数设计。

**可展示文件：** `apps/web/run_state.js`（前端 run state 管理）、`apps/api/app/schemas.py` 第 42-45 行的 `project_id_override` 字段（支持 regenerate 沿用旧 project_id）。

**风险补充：** 内存存储意味着服务重启后状态丢失。虽然设计了 JSONL 持久化，但重启后需要主动触发 restore 操作，不是自动恢复。生产部署需要外部存储。


### Q8: 为什么不用复杂 Multi-Agent？

**问题：** 现在很流行 Multi-Agent 框架，为什么你的系统只用了一个 Agent？

**面试官想考什么：** 你对 Multi-Agent 的理解是否实事求是；能不能区分「需要 Multi-Agent」和「单 Agent + 阶段化」的适用场景。

**PaperAgent 怎么回答：** 我们评估过是否需要 Multi-Agent。结论是学术开题场景任务流程是确定的——拆解 → 检索 → 评估 → 推荐 → 审核——每个步骤的输入输出边界清晰，单 Agent + 阶段化流水线比 Multi-Agent 更容易调试和测试。我们的架构本质上是一个「阶段化 Agent」：每个阶段（Phase 01-08）有明确的输入 schema 和输出 schema，阶段间的依赖通过 409 拦截确保前序完成。如果需要，单 Agent 可以随时升级为 Multi-Agent（例如把审核步骤拆成一个独立的 Reviewer Agent），但目前 32 个 E2E 测试 + 390 个后端测试都验证了单 Agent 架构足够可靠。

**项目证据：** `apps/api/app/services/one_topic.py` 第 1350-1381 行的 `run_one_topic()` 顺序调用链：breakdown → understand → plan → collect → judge → recommend → review。

**可展示文件：** `apps/api/app/services/one_topic.py` 第 1350-1381 行的 6 段流水线代码。

**风险补充：** 单 Agent 的局限是无法并行处理独立子任务。例如收集论文证据和收集数据集证据目前是串行的。如果检索源数量继续增加，可以拆成独立 Worker 并行。


### Q9: 你的 Agent 怎么处理用户中断和修正？

**问题：** 用户发现 Agent 理解错了关键词，或者检索词不对，怎么办？能撤回重新来吗？

**面试官想考什么：** Human-in-the-loop 的设计；你有没有给用户控制权还是把用户当旁观者。

**PaperAgent 怎么回答：** 我们设计了三个层次的 Human-in-the-loop。第一层是 Gate 1+2（Session 3）——自动拆解关键词和构建检索计划后，不直接往下走，而是让用户确认/编辑。用户改完之后，系统跳过自动拆解步骤，直接用用户提供的内容继续。通过 `confirmed_keywords` 和 `confirmed_search_plan` 字段实现。第二层是 Workspace Board 的手动编辑（Session 9+25）——用户可以手动添加证据、修改 review_status、切换 workspace_lane、打回 rejected。这些操作都通过 `/evidence` 端点的 PATCH / DELETE 实现。第三层是 regenerate 机制——用户如果对最终结果不满意，可以带 `project_id_override` 重新请求，系统沿用已有 project_id 但在新的 run 中覆盖旧结果。Trace 事件流完整记录了所有用户修正操作（action="user_patch"），可追溯。

**项目证据：** `apps/api/app/schemas.py` 第 34-44 行的 `confirmed_keywords` / `confirmed_search_plan` / `project_id_override`。`apps/web/e2e/test_one_topic_session3_gates.py`（Gate 测试）。

**可展示文件：** `apps/api/app/schemas.py` 第 34-44 行的 Gate 字段定义。`apps/api/app/schemas_trace.py` 第 22 行的 `actor: TraceActor = "user"`。

**风险补充：** 目前 Gate 只在分析前介入，分析过程中没有中间暂停点。如果用户想修改分析中的某一步，只能等全部跑完再 regenerate。未来可以加入「任意步骤 checkpoint 暂停修改」的支持。


### Q10: Agent 的决策点在哪？

**问题：** 你的 Agent 在哪些环节真正做了决策？还是所有路径都是 if-else 写死的？

**面试官想考什么：** 你区分了「规则」和「决策」吗；Agent 的自主性在哪里体现。

**PaperAgent 怎么回答：** 我们的 Agent 主要有三个真实决策点。第一是 Feasibility 裁决（Session 28）——系统评估 7 个风险维度（EvidenceSupport、DataAvailability、BaselineReadiness、ExperimentalClarity、ScopeControl、ResourceFit、NoveltyDifferentiation）后输出 GO / CONDITIONAL / PIVOT / PARK / STOP 五种裁决。PIVOT 时会推荐三条路线（保守 / 平衡 / 进取）。第二是 Committee Review 审核（Session 30）——从 5 个视角（advisor / method / experiment / writing / risk）对开题报告草案做结构化审核，输出致命/高/中问题列表和 revision checklist。第三是 Readiness 检查（Session 32）——8 个维度检查报告是否达到导出标准，其中 4 个 hard-block 维度任一 fail 则禁止导出。这些决策点都结合了规则引擎和评分阈值，不是纯 LLM 黑箱，也不是纯 if-else。

**项目证据：** `apps/api/app/schemas_feasibility.py`（7 维风险、硬否决、PIVOT 路线）、`apps/api/app/services/review.py`（5 视角审核引擎）、`apps/api/app/services/readiness.py`（8 维 readiness 检查）。

**可展示文件：** `apps/api/app/schemas_feasibility.py` 第 39 行的 `FeasibilityVerdict = Literal["GO", "CONDITIONAL", "PIVOT", "PARK", "STOP"]`。`apps/api/app/services/review.py` 第 293-336 行的 `run_review()` 入口。

**风险补充：** 这三个决策点各自独立，之间没有联动。例如 Feasibility 已经是 STOP 了，后面的审核仍然会跑完。可以加一个 early exit 机制避免无效计算。

---

## Category 3: Memory / Transcript

### Q11: 你的 Trace 是怎么设计的？

**问题：** 你的 Trace 和普通的日志有什么不同？你记录了哪些信息？

**面试官想考什么：** 你对 observability 和 audit trail 的理解深度。

**PaperAgent 怎么回答：** Trace 不是普通日志——每个 TraceEvent 是可回放、可查询、可过滤的结构化事件。字段包括 trace_id、project_id、ts、actor（system / user / agent）、action、target_type、target_id、before、after、reason、source、session。最重要的是 `before` 和 `after` 字段——这让我们能精确知道每次操作改变了什么。例如用户修改了某个证据的 review_status 从 "pending" 到 "core"，Trace 会记录 before={review_status:"pending"}、after={review_status:"core"}、reason="用户手动提升"。Trace 持久化为 JSONL 文件，支持按 project_id 全量查询（GET `/trace`）、按证据 ID 查询时间线（GET `/evidence/{id}/timeline`）、以及统计摘要（GET `/trace/summary`）。

**项目证据：** `apps/api/app/schemas_trace.py`（TraceEvent 定义）、`apps/api/app/services/trace_store.py`（Trace 存储与查询）。

**可展示文件：** `apps/api/app/schemas_trace.py` 第 13-31 行的完整 `TraceEvent` 定义（13 个字段）。

**风险补充：** 目前 JSONL 文件没有轮转机制，一个活跃的 project 可能会产生大量事件文件。需要加入 max_events 限制或按时间段轮转。


### Q12: RunEvent 和普通日志有什么区别？

**问题：** 你的 RunEvent 和 TraceEvent 有什么区别？为什么同时需要两个？

**面试官想考什么：** 你对不同粒度的持久化需求的理解；Event Sourcing 的经验。

**PaperAgent 怎么回答：** RunEvent 和 TraceEvent 服务于不同的目的。RunEvent 关注「流的执行过程」——它以 run_id 为单位，记录一个分析流程从开始到结束的每个步骤事件，字段包括 step_key、event_type、status（pending → running → completed → failed → aborted）、payload。它是流式 SSE 的持久化版本，前端可以通过回放 RunEvent 重建完整的步骤展示。TraceEvent 关注「变更历史」——它不关心流式执行的细节，而是记录谁在什么时间对什么证据做了什么修改。简单说：RunEvent 是「流程日志」，TraceEvent 是「审计日志」。两者共存的必要性：前端流式恢复需要 RunEvent，用户操作追溯需要 TraceEvent。RunEvent 的 schema 在 `schemas_run_event.py`，TraceEvent 在 `schemas_trace.py`。

**项目证据：** `apps/api/app/schemas_run_event.py`（RunEvent、RunState、RunCreateRequest）。`apps/api/app/schemas_trace.py`（TraceEvent、TraceListResponse、TraceTimelineResponse）。

**可展示文件：** `apps/api/app/schemas_run_event.py` 第 19-33 行和第 36-49 行的 RunEvent + RunState 定义。

**风险补充：** 两个事件流目前没有关联索引——你无法从 RunEvent 直接跳到相关的 TraceEvent。可以增加一个 `trace_ids` 字段在 RunEvent 的 payload 中建立关联。


### Q13: 你记录了什么决策信息？

**问题：** 你怎么知道 Agent 为什么做了某个决策？比如为什么判定一个题目是 PIVOT？

**面试官想考什么：** 可解释 AI 和决策可追溯的设计。

**PaperAgent 怎么回答：** 每个决策点的输入和输出都有记录。在 Feasibility 裁决中，7 个风险维度的评分、每个维度的 evidence_refs、触发哪些硬否决规则、以及最终 verdict 都被记录。在 Committee Review 中，5 个视角发现的每一条 issue 都有 issue_id、severity、section_id、message、suggested_fix、evidence_refs。用户如果对决策有疑问，可以通过 Trace 查询特定证据的 timeline，看到它是从 "pending" 一步步晋升到 "core" 的，还是被 "rejected" 的。在 Readiness 检查中，8 个维度的每一条检查结果都有详细的 message 和 required_fix，hard-block 维度 fail 时会列出具体原因。

**项目证据：** `apps/api/app/schemas_feasibility.py`（RiskDimension、HardVeto）、`apps/api/app/services/review.py`（ReviewIssue 生成函数）、`apps/api/app/services/readiness.py`（ReadinessDimension）。

**可展示文件：** `apps/api/app/schemas_feasibility.py` 第 23-35 行的 `RiskDimension` 类（含 score、level、reason、missing_evidence 字段）。

**风险补充：** 目前决策理由都是结构化文本，没有存 LLM 的 raw response。如果要深入分析 LLM 路径的失败案例，需要补存 raw LLM 响应。


### Q14: Transcript 怎么支持调试和测试？

**问题：** 你怎么复现一个曾经出错的场景？能不能把一个失败案例变成测试用例？

**面试官想考什么：** 你有没有建立测试回放机制来防止 regression。

**PaperAgent 怎么回答：** 通过三层机制。第一层是 baseline fixtures（Session 17）——YOLO 目标检测和 MLLM 高风险选题两个案例的完整分析结果被固化为 JSON fixture，集成测试直接加载 fixture 断言关键字段存在且值合理，不依赖真实网络或 LLM。第二层是 demo smoke 脚本——`scripts/full_smoke.py` 按 Phase 01-04 跑完整的 happy path 和 blocked path，使用固定 seed 输入确保可重现。第三层是 Playwright 回放——32 个 Playwright E2E 测试模拟用户完整操作流（打开页面、输入题目、点击按钮、等待结果、断言 UI），Session 31 的 full_chain 测试覆盖了从输入到导出报告的全流程。失败案例通过加 Playwright 测试覆盖来防止回归。

**项目证据：** `apps/api/tests/test_session17_demo_baseline.py`、`scripts/full_smoke.py`、`apps/web/e2e/test_one_topic_session31_full_chain.py`。

**可展示文件：** `apps/web/e2e/conftest.py` 第 40-60 行的 `_require_servers` fixture（自动检查和启动服务器）。

**风险补充：** Playwright 测试需要真实浏览器和后端服务，CI 环境配置成本较高。可以补充纯 API 级别的 regression suite，减少对浏览器的依赖。


### Q15: 如何防止记忆无限膨胀？

**问题：** 如果用户在一个 project 里操作了 1000 次，你的 Trace 文件会不会无限变大？

**面试官想考什么：** 你在设计持久化时有没有考虑过存储上限和清理策略。

**PaperAgent 怎么回答：** 目前我们通过 per-project scoping 控制膨胀范围，不做全局记录。每个 project_id 独立存储 Trace 事件文件和 RunEvent 文件。但确实还没有实现自动轮转或上限截断——这是一个已知的 gap。设计中考虑了两种清理策略：一是按时间窗口（只保留最近 30 天的事件），二是按事件数量上限（超过 N 条后滚动丢弃最早的事件）。目前因为 MVP 阶段数据量小（单次分析产生的 TraceEvent 不超过 50 条）所以未触发问题。另外我们设计了 snapshot 机制——`/analyze` 每次跑完会保存一份关键段的 JSON snapshot，如果需要重建状态可以走 snapshot 而不是重放全部事件。

**项目证据：** `apps/api/app/services/evidence.py` 第 42-47 行的 `latest_snapshot` 缓存。`apps/api/app/services/evidence.py` 第 199+ 行的 `save_snapshot()` / `get_snapshot()`。

**可展示文件：** `apps/api/app/services/one_topic.py` 第 1384-1400 行的 `_save_response_snapshot()` 函数。

**风险补充：** 确实是已知 gap。生产部署前需要实现事件轮转策略。可以借鉴 logrotate 的思路，或者迁移到数据库按时间索引自动清理。

---

## Category 4: Tool Calling / MCP

### Q16: 你的工具调用是怎么设计的？

**问题：** 你的 Agent 用到了哪些外部工具？调用链是什么结构？

**面试官想考什么：** 你有没有真正集成外部 API；你理解 function calling 的调用-验证-提取模式吗。

**PaperAgent 怎么回答：** 我们的工具调用链遵循 search_engine → fetch → verify → extract 的四步模式。第一步是检索层：arXiv（论文）、OpenAlex（论文元数据）、GitHub（代码仓库）、HuggingFace（数据集）、Kaggle（竞赛/数据集）。每个 adapter 封装了特定 API 的调用细节。第二步是 URL 验证：`services/verification.py` 对检索到的 URL 做平台解析（识别 GitHub / arXiv / HF / Kaggle）、域名格式检查、可选的 HTTP 状态检查。第三步是卡片化（Session 15）：对 PDF、图片、网页、URL 进行结构化提取，转换为 MaterialCard 存入证据池。第四步是证据引用：`services/evidence_refs.py` 根据 review_status、verification_status、workspace_lane、paper_type 等多维权重计算 ref_priority，决定该证据在报告中的引用方式。

**项目证据：** `apps/api/app/services/retrieval/adapters/`（各源 adapter）、`apps/api/app/services/verification.py`（URL 验证）、`apps/api/app/services/evidence_refs.py`（引用权重公式）。

**可展示文件：** `apps/api/app/services/retrieval/orchestrator.py` 第 61-69 行的 source-to-candidate-type 映射数组。`apps/api/app/services/verification.py` 第 37-42 行的平台正则解析。

**风险补充：** 目前 API 调用没有统一的重试和超时策略。各 adapter 自己处理错误，异常直接抛到上层。应该加入统一的 retry with backoff 包装器。


### Q17: Function Calling 失败怎么办？

**问题：** 如果调 arXiv API 超时了，或者 GitHub API 返回 429，你的系统会崩溃吗？

**面试官想考什么：** 你对错误处理和 graceful degradation 的设计经验。

**PaperAgent 怎么回答：** 不会崩溃，因为每个外部调用都有 heuristic fallback。LLM 路径整体采用「LLM 优先、失败降级」策略（`prefer` 参数支持 "auto" / "llm" / "heuristic"）。当 `prefer=auto` 时，先尝试 LLM，如果 LLM 调用失败（超时、API key 无效、模型返回异常）就自动降级到 heuristic 规则。Heuristic 规则内置了 40+ 学术方法词（YOLO / Transformer / ViT / BERT 等）、中英文对象映射表、以及学术领域的通用检索模板，不依赖任何外部 API 也能产出合理的检索词。arXiv 检索失败时，系统会使用内置的占位论文数据继续后续流程，只是在 Feasibility 判定时会标注 paper_status 为 "需要补充"。URL 验证如果网络不可用，不会阻断流程，而是标记为 "partial" + warning。

**项目证据：** `apps/api/app/services/one_topic.py` 第 46-60 行的 `_METHOD_HINTS` 内置词典。`apps/api/app/services/verification.py` 第 7-9 行的设计原则「无网络 → partial + warning, 不阻断」。

**可展示文件：** `apps/api/app/services/one_topic.py` 第 46-377 行的启发式拆解函数和内置映射表。

**风险补充：** Heuristic fallback 的输出质量有限，复杂题目（跨领域、新术语）的拆解可能不准确。目前通过 Session 31 的 full_chain baseline 来监控 heuristic 路径的回归表现。


### Q18: 怎么保证外部工具调用的安全性？

**问题：** 如果用户提供了一条恶意 URL，你的系统会去访问吗？有没有 SSRF 防护？

**面试官想考什么：** 对安全性的考虑；SSRF（Server-Side Request Forgery）防护意识。

**PaperAgent 怎么回答：** 我们的 URL 验证系统有三层安全防护。第一层是平台正则解析（`verification.py` 的 `parse_url()`）——只识别 GitHub、arXiv、HuggingFace、Kaggle 这四个平台域名，不符合任何已知模式的 URL 会被归为 "generic" 并标记为 "needs_check"。第二层是 verification_status 约束——verification_status 为 "failed" 的证据不得作为 supports（`evidence_refs.py` 第 13-15 行硬规则），assistant_intake + unverified 的证据也不得作为 supports。第三层是 readiness 检查中的 reference_integrity 维度——所有参考资源必须有至少 1 条 review_status 为 "accepted" 或 "core" 的才能通过导出检查。我们不使用 MCP 机制做 URL 访问，而是通过 CDP（Chrome DevTools Protocol）在用户浏览器环境中做 URL 验证，避免服务端直接请求外部资源。

**项目证据：** `apps/api/app/services/verification.py`（URL 解析与验证）、`apps/api/app/services/evidence_refs.py` 第 13-15 行的硬规则注释。

**可展示文件：** `apps/api/app/services/verification.py` 第 37-42 行的四个平台正则规则。`apps/api/app/services/evidence_refs.py` 第 12-16 行的 supports 约束注释。

**风险补充：** 目前的安全模型依赖正则匹配和 review 状态机，不是沙箱执行。攻击者可以提供一个指向内网 IP 但域名伪装成 github.com 的 URL（如 github.com@192.168.1.1）。需要补充 URL 的 host 解析验证。


### Q19: 你的工具调用链有多长？

**问题：** 你的 Agent 会不会出现工具递归调用？调用链最长有多深？

**面试官想考什么：** 你是否有控制工具调用的深度和广度；你理解 agentic loop 的复杂度管理。

**PaperAgent 怎么回答：** 我们的调用链一般是 2-3 层：第一层是关键词拆解和检索计划生成，第二层是并行检索（多个 adapter 同时执行），第三层是评分和证据入池。我们没有设计递归调用——这是刻意的架构决定。支持并行调用（多个 adapter 通过 asyncio.gather 并发执行），但不支持工具递归（不会出现「为验证一条结果而去调用另一个工具」的链式递归）。这样做的原因是学术开题场景的流程是确定性的 DAG，不是探索性的问题求解。如果将来需要探索性推理（例如「这篇论文引用了哪篇？再去查那篇」），我们会增加显式的 max_depth 参数来控制递归深度。

**项目证据：** `apps/api/app/services/one_topic.py` 第 1350-1381 行的 `run_one_topic()` 线性流程。`apps/api/app/services/retrieval/orchestrator.py` 的 asyncio.gather 并发调用。

**可展示文件：** `apps/api/app/services/retrieval/orchestrator.py` 第 1-13 行的协调器职责注释（9 步，无递归）。

**风险补充：** 没有递归意味着无法做引用链追踪（citation chain）。如果用户问「这篇 baseline 论文引用了哪些后续工作」，目前不支持。这是一个可以拓展的方向，但不是 MVP 范围。


### Q20: 和 MCP 的关系？

**问题：** 你的系统用 MCP（Model Context Protocol）吗？和 MCP 有什么关系？

**面试官想考什么：** 你对 MCP 的理解；你区分了「当前架构」和「可扩展性」的能力。

**PaperAgent 怎么回答：** 当前系统不强制使用 MCP。我们的工具调用（arXiv Search、GitHub API、HuggingFace 等）是通过 Python 代码中的 adapter 直接调 HTTP API 实现的，不需要 MCP 层。但系统架构上可以接入 MCP——如果我们想引入第三方 MCP server 来扩展检索源（例如接入某个大学图书馆的私有检索系统），可以把 adapter 替换为 MCP client。URL 验证部分我们使用 CDP（Chrome DevTools Protocol）在用户浏览器中完成，不是通过 MCP Server。设计原则是「不绑定特定协议」，检索层通过 adapter 模式（`apps/api/app/services/retrieval/adapters/__init__.py` 的 REGISTRY）支持新源的注册。

**项目证据：** `apps/api/app/services/retrieval/adapters/arxiv_search.py`（arXiv adapter）、`apps/api/app/services/retrieval/adapters/__init__.py`（adapter 注册表）。

**可展示文件：** `apps/api/app/services/retrieval/adapters/__init__.py` 的 `REGISTRY` 字典。

**风险补充：** adapter 模式虽然扩展性好，但每个 adapter 的错误处理和重试策略是自己实现的，没有统一的中间件层。接入 MCP 后可以标准化工具调用的生命周期管理。

---

## Category 5: Evaluation / Testing

### Q21: 如何评估一个 Agent 项目？

**问题：** 你怎么证明你的 Agent 项目是「好的」？用什么指标？

**面试官想考什么：** 你有系统性的评估方法，不是靠「看起来不错」。

**PaperAgent 怎么回答：** 我们通过三个层面的定量评估。第一层是测试覆盖率——390 个后端 pytest 测试 + 32+ 个 Playwright E2E 测试文件。后端测试覆盖了每个 Phase 的 schema 验证、端点响应、业务逻辑、边界条件（空输入、无网络、LLM 失败）。Playwright 测试覆盖了完整的用户操作流和 UI 断言。第二层是 baseline regression（Session 17 + Session 31）——YOLO 目标检测和 MLLM 高风险选题两个案例的完整分析结果固化为 JSON fixture，每次代码变更后跑全量回归对比，确保不退化。具体检查内容包括：关键词拆分包含 "YOLO"、evidence_summary 非空、feasibility_verdict 存在、review 有 verdict 等。第三层是 smoke 测试——`scripts/full_smoke.py` 验证 Phase 01-04 的 happy path 和 blocked path 均能正常工作。

**项目证据：** `apps/api/tests/`（28 个测试文件）、`apps/web/e2e/`（33 个测试文件）、`scripts/full_smoke.py`、`docs/testing/Test_Matrix.md`。

**可展示文件：** `docs/testing/Test_Matrix.md` 第 13-31 行的后端测试矩阵（Session 01-17 的一览表）。

**风险补充：** 目前缺乏用户满意度调查或 A/B 测试数据。指标都是内部测试通过的，没有真实用户的使用数据。可以计划在发布后收集用户反馈和完成率统计。


### Q22: 你的 Playwright 测试覆盖了什么？

**问题：** 32 个 Playwright 测试文件听起来很多，具体测了什么？

**面试官想考什么：** E2E 测试的覆盖面是否合理；你分的清单元测试和集成测试的边界。

**PaperAgent 怎么回答：** Playwright E2E 测试覆盖了四类场景。第一是 happy path——标准输入 → 看到完整分析结果 → 证据工作台可用 → 导出报告。对应 `test_one_topic_happy_path.py` 和 `test_one_topic_session31_full_chain.py`。第二是 fail path——无数据集题目（`test_one_topic_no_dataset.py`）、高风险题目（Session 4 pivot）、LLM 不可用时的 heuristic fallback（Session 6）、模板不匹配（Session 19）。第三是 regression——每个 Session 的测试文件独立，Session 31 的 full_chain 包含 10 条详细断言。第四是 UI 交互——Gate 1+2 的用户编辑（Session 3）、Workspace Board 的拖拽和 lane 切换（Session 9+25）、Step Deck 的步骤展示（Session 21）、证据晋升（Session 26）。

**项目证据：** `apps/web/e2e/test_one_topic_happy_path.py`（核心 happy path）、`apps/web/e2e/test_one_topic_no_dataset.py`（无数据集 fail path）、`apps/web/e2e/test_one_topic_session31_full_chain.py`（完整链路）。

**可展示文件：** `apps/web/e2e/test_one_topic_session31_full_chain.py` 第 67-220 行的 10 个测试方法。

**风险补充：** Playwright 测试需要 Python + Node.js 双环境，配置有些复杂。另外测试运行时间较长（完整的 E2E suite 大约 5-8 分钟），不适合作为代码提交的前置钩子。


### Q23: Baseline fixtures 为什么重要？

**问题：** 你提到 baseline fixtures，为什么不能直接跑集成测试测全部？

**面试官想考什么：** 你对 regression testing 在 LLM 项目中的挑战的理解。

**PaperAgent 怎么回答：** Baseline fixtures 的重要性在于解决 LLM 项目特有的「非确定性」问题。如果每次测试都调真实 LLM，输出会因模型更新、prompt 微调、随机种子而变，测试结果不稳定。Baseline fixtures 将 LLM 路径的一次输出固化，后续测试不再调 LLM，而是断言固定输出是否被错误修改。例如 YOLO 案例的 baseline 断言：keyword_breakdown.method_keywords 必须包含 "YOLO"、evidence_summary.paper_count >= 3、feasibility.verdict 存在。如果某次代码修改不小心破坏了关键词拆分逻辑（比如把 "YOLO" 拆丢了），baseline 测试会第一时间发现。另外 Session 17 的 baseline 还包含一个高风险跨领域案例（MLLM + 数字孪生），确保风险检测逻辑不被退化。

**项目证据：** `apps/api/tests/test_session17_demo_baseline.py`（YOLO + MLLM 双 case baseline）、`apps/api/tests/test_session31_full_chain_baseline.py`（完整链路 baseline）。

**可展示文件：** `apps/api/tests/test_session17_demo_baseline.py` 中的 baseline fixture 加载逻辑。

**风险补充：** Baseline 会随时间过时——如果模型升级或者新增了更好的检索源，旧的 baseline 约束可能需要调整。需要定期 review baseline 断言是否仍然合理。


### Q24: 怎么保证测试可重复？

**问题：** 你的测试结果不稳定的情况下（LLM 输出变化、网络不稳定），你怎么保证测试是可信的？

**面试官想考什么：** 你在处理非确定性系统测试上的工程经验。

**PaperAgent 怎么回答：** 我们通过三个手段保证可重复性。第一是 seed input——所有测试使用固定输入，例如固定 raw_topic="YOLO 钢材表面缺陷检测"，不随机生成。第二是 heuristic-only path——baseline fixtures 测试走纯 heuristic 路径（`prefer="heuristic"`），不依赖任何外部 API 或 LLM，彻底消除不确定性。第三是 mock mode——RunEvent 的 POST `/runs` 支持 `mock_mode=True`，在 mock 模式下完全不调 LLM 和外部 API，使用预设数据模拟所有步骤。此外 Playwright 测试使用固定的 viewport（1400x1400）、固定的等待策略（wait_for_load + 显式断言）减少 flakiness。对于网络相关的测试（如 API 超时），使用独立的 fail-case 测试文件（`test_one_topic_no_dataset.py`）而非在 happy path 中模拟网络故障。

**项目证据：** `apps/api/app/schemas_run_event.py` 第 58 行的 `mock_mode: bool`。`apps/api/app/services/one_topic.py` 第 29 行的 `prefer` 参数。

**可展示文件：** `apps/api/app/schemas.py` 第 28-30 行的 `prefer` 参数定义（auto / llm / heuristic）。

**风险补充：** Heuristic-only 路径虽然可靠，但它只能验证「不调 LLM」时的行为。如果 LLM 路径有 bug，heuristic-only 测试是检测不到的。需要额外加 LLM path 的独立 mock 测试。


### Q25: 你测了哪些错误路径？

**问题：** 除了正常流程，你测了哪些「用户搞砸了」的情况？

**面试官想考什么：** 边界情况和错误处理测试的完备性。

**PaperAgent 怎么回答：** 我们测试了 6 大类错误路径。一是 no_dataset——题目没有可用的公开数据集（如超冷门题目），验证可行性裁决是否能正确输出 "PARK" 或 "PIVOT"（`test_one_topic_no_dataset.py`）。二是 LLM failures——API key 无效、模型超时、返回格式错误，验证 heuristic fallback 是否能正确激活（`test_session6_llm_path.py`）。三是 template mismatch——报告模板与学校要求不匹配，验证 readiness 检查能否检测到模板章节缺失（`test_session32_readiness.py`）。四是 URL unreachable——URL 验证失败，验证 verification_status=failed 的证据不被 supports（`test_session10_verification.py`）。五是 timeouts——测试整个管道在外部依赖挂掉时的行为。六是 schema validation——空输入、错误类型、缺少必填字段等，验证 FastAPI Pydantic 校验是否能正确返回 422。

**项目证据：** `apps/web/e2e/test_one_topic_no_dataset.py`（无数据集路径）、`apps/web/e2e/test_one_topic_session18_error_states.py`（错误状态测试）。

**可展示文件：** `apps/web/e2e/test_one_topic_session18_error_states.py` 的错误场景测试列表。

**风险补充：** 目前没有测并发冲突——例如两个用户同时编辑同一个 project 的证据。由于是单进程内存存储，这个问题不会在生产中暴露，但未来迁移到数据库后需要补充并发测试。

---

## Category 6: Safety / Boundary

### Q26: 创新点夸大怎么检测？

**问题：** 学生写开题报告时喜欢用「首创」「国际领先」这种词，你们怎么处理？

**面试官想考什么：** 你有没有防止学术不端和夸大宣传的机制。

**PaperAgent 怎么回答：** 我们在多个层次检测夸大性语言。第一层在 Proposal Draft 生成阶段（`schemas_proposal_draft.py`）——定义了 9 个中文夸大词（首创、第一、填补空白、国际领先、国内首次、revolutionary、first ever、state-of-the-art、novel breakthrough），`_validate_no_inflation()` 函数检查所有 innovation_points 的 title 和 description，发现夸大词即报错。第二层在 Readiness 检查（`services/readiness.py`）——定义了 9 个中文夸大词检测（首创、首次、完全解决、彻底解决、革命性、颠覆性、国际领先、填补空白、零的突破），innovation_claim_safety 维度会扫描创新点章节内容，发现夸大词维度状态设为 fail。第三层在 export 前——innovation_claim_safety 是 4 个 hard-block 维度之一，fail 时整体 export_allowed = False，直接阻止有夸大用词的报告被导出。

**项目证据：** `apps/api/app/schemas_proposal_draft.py` 第 43-47 行的 `INFLATED_WORDS`。`apps/api/app/services/readiness.py` 第 56-59 行的 `_INFLATED_WORDS` 和第 243-278 行的 `_check_innovation_claim_safety()`。

**可展示文件：** `apps/api/app/services/readiness.py` 第 56-59 行的夸大词列表和第 265-273 行的检测逻辑。

**风险补充：** 夸大词检测目前是关键词匹配，有误报和漏报的风险。例如「第一次使用 Transformer 做 X 任务」不是夸大但包含「第一」。也检测不到高级包装的夸大（如「前所未有的性能提升」）。可以升级为 LLM 语义判断。


### Q27: URL 验证怎么做的？

**问题：** 你的系统会去访问用户提供的 URL 吗？怎么确保 URL 是安全的？

**面试官想考什么：** 对联网 Agent 的安全意识；URL 验证的工程实现。

**PaperAgent 怎么回答：** URL 验证由 `services/verification.py` 实现。验证过程分四步：第一步是平台解析——通过正则匹配识别 URL 属于哪个平台（GitHub、arXiv、HuggingFace、Kaggle 或 generic），提取关键 ID。第二步是格式验证——检查 URL 结构是否合法。第三步是可选的 HTTP 状态检查——如果网络可用且 URL 不是已知平台（generic），会做一次 HEAD 请求检查 URL 是否可达，但不下载内容。第四步是 verification_status 赋值——输出 unified / verified / failed / partial / skipped。关键安全规则（`evidence_refs.py` 第 13 行）：verification_status=failed 的证据不得作为 supports，assistant_intake + unverified 不得作为 supports。URL 验证设计上不绕过付费数据库、不深爬、不下载全文。

**项目证据：** `apps/api/app/services/verification.py`（完整的 URL 验证逻辑）、`apps/api/app/services/evidence_refs.py` 第 12-16 行的硬规则注释。

**可展示文件：** `apps/api/app/services/verification.py` 第 49-80 行的 `parse_url()` 函数和第 37-42 行的四个平台正则。

**风险补充：** 目前不做实际文件下载验证——我们说一个 DOI 是有效的，但没有验证这个 DOI 对应的论文是否真的存在。完全验证需要跨域请求，工程成本较高。


### Q28: 导出前检查拦什么？

**问题：** 用户导出开题报告前，你们有哪些检查？什么情况下会禁止导出？

**面试官想考什么：** 出口控制和质量管理；你对「报告质量门禁」的理解。

**PaperAgent 怎么回答：** 我们设计了 8 个维度的 Readiness 检查（Session 32）。4 个 hard-block 维度一旦 fail 直接禁止导出：section_completeness（缺少必要章节）、reference_integrity（没有已验证的参考资源）、school_template_fit（模板要求的章节缺失）、innovation_claim_safety（创新点含夸大用词）。4 个软性维度会 warn 但不会硬阻止：evidence_binding（证据绑定不够）、risk_disclosure（可行性与风险章节为空）、workload_clarity（工作量章节条目不足）、format_basic（Markdown 长度不够）。整体判断逻辑：存在任一 hard-block fail 则 export_allowed = False。Readiness 检查结果以 `ReadinessReport` 结构返回，包含每个维度的 status、message、required_fix、section_refs，方便用户定位问题。

**项目证据：** `apps/api/app/schemas_readiness.py`（ReadinessReport、ReadinessDimension）。`apps/api/app/services/readiness.py` 第 311-353 行的 `check_readiness()` 函数。

**可展示文件：** `apps/api/app/services/readiness.py` 第 62-65 行的 hard-block 维度集合和第 330-352 行的整体 verdict 逻辑（hard_blocks + export_allowed）。

**风险补充：** Readiness 检查目前是「全有或全无」——只要有一个 hard-block fail 就全面禁止导出，没有部分导出或降级导出选项。可以设计「带 warning 导出」模式，让导师判断是否放行。


### Q29: 怎么防止模型幻觉污染报告？

**问题：** LLM 生成的报告内容可能含有幻觉——引用不存在的论文、编造数据。你们怎么控制？

**面试官想考什么：** 你对 LLM 落地中「幻觉」这个核心问题的工程应对方案。

**PaperAgent 怎么回答：** 我们在三个层面控制幻觉污染。第一层是 evidence_refs 绑定——所有 ProposalSection 的内容必须绑定 evidence_refs 或 marked as missing_evidence。`validate_proposal()` 函数（`schemas_proposal_draft.py` 第 147 行）强制每个章节至少有一个 evidence_refs、selected_refs 或 missing_evidence，不允许凭空写内容。第二层是 confidence 约束——没有证据的章节 confidence 不能设为 "high"（`_validate_confidence()` 函数），防止 LLM 对无支撑的内容表现出高置信度。第三层是 Light Review 检测——light_review（`one_topic.py` 第 1197 行）的 5 维审核中包含对 evidence binding 的检查，发现关键结论没有证据支撑时会写入 revision checklist。再加上 readiness 检查中的 evidence_binding 和 reference_integrity 两个维度，确保导出前所有关键内容都有可信引用。

**项目证据：** `apps/api/app/schemas_proposal_draft.py` 第 67-77 行的 `ProposalSection`（含 evidence_refs、selected_refs、candidate_refs、missing_evidence 字段）。第 147-183 行的 `validate_proposal()`。

**可展示文件：** `apps/api/app/schemas_proposal_draft.py` 第 67-77 行的 `ProposalSection` 定义（4 个绑定字段）。`apps/api/app/services/readiness.py` 第 104-130 行的 `_check_evidence_binding()`。

**风险补充：** Evidence binding 只能约束「有引用」，不能约束「引用正确」。如果 LLM 引用了一篇真实存在但不相关的论文，这个引用不会触发任何检查。需要一个证据相关性验证层。


### Q30: 高风险题目怎么处理？

**问题：** 如果学生选了一个明显做不出来的题目（如「基于量子计算的学术论文自动生成系统」），你怎么处理？

**面试官想考什么：** 风险评估和防浪费机制；Agent 能不能拒绝回答。

**PaperAgent 怎么回答：** 高风险题目通过多层评估和退化路线来处理。第一层是 Feasibility 7 维风险评估（Session 28）——从 EvidenceSupport、DataAvailability、BaselineReadiness、ExperimentalClarity、ScopeControl、ResourceFit、NoveltyDifferentiation 七个维度打分，每个维度 0-100。硬否决规则（无数据集 → 不得 GO、无指标 → 不得 GO、无 baseline → 不得 GO）自动触发。第二层是 5 档裁决——GO、CONDITIONAL、PIVOT、PARK、STOP。PIVOT 时会推荐 3 条具体路线（保守/平衡/进取）。STOP 会直接建议换题。第三层是 Evidence Deficiency Detection——FeasibilitySummary 的 missing_evidence 字段列出所有缺少的证据类型，让用户知道缺什么。我们在 Session 4 的 E2E 测试（`test_one_topic_session4_pivot.py`）中专门测试了一个跨领域高风险题目（MLLM + 数字孪生），验证系统能正确检测到无数据集、无 baseline 并输出 PIVOT。

**项目证据：** `apps/api/app/schemas_feasibility.py`（7 维风险 + 硬否决 + PIVOT 路线）。`apps/api/app/services/one_topic.py` 第 774 行的 `judge_feasibility()`。`apps/web/e2e/test_one_topic_session4_pivot.py`。

**可展示文件：** `apps/api/app/schemas_feasibility.py` 第 23-51 行的 RiskDimension + HardVeto 定义。`apps/api/app/schemas_feasibility.py` 第 39 行的 `FeasibilityVerdict`。

**风险补充：** 目前的 7 维评分是纯启发式规则（论文数量、数据集有无、baseline 有无），没有 LLM 参与评估。LLM 可以更好地理解题目本质风险（例如「两领域不兼容」比「无数据集」更致命），但会引入不确定性和延迟。目前的选择是宁可漏报不可误报。

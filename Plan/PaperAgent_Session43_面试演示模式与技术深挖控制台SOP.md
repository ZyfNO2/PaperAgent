# PaperAgent Session 43 SOP：面试演示模式与技术深挖控制台

## 0. 下一步方向判断

Session 42 的前端工作台已经基本完成：左侧 LLM 对话、中央 Step 工作区、右侧证据 Trace、对话式修改预览、stale 传播都已经落地。下一步不建议继续扩展毕业论文业务功能，也不建议继续单独写面试材料。

更合适的方向是：**把当前项目改造成一个面试可演示、可解释、可深挖、可定位代码的 Agent 项目展示体。**

换句话说，Session 43 要做的是：

```text
普通用户工作台
→ 面试演示模式
→ 技术深挖入口
→ 可验证测试证据
→ 简历 / QA / Demo 材料和真实 UI 对齐
```

## 1. 为什么下一步做这个

### 1.1 S42 后的真实状态

从 `Plan/reports/Session_42_WorkbenchChatEdit_验收报告.md` 看，当前状态可以概括为：

- 前端工作台主交互已完成；
- 旧 Step 1-5 重复卡片已从主路径隐藏；
- 对话入口和修改预览已接入；
- stale 传播已生效；
- Trace 分组折叠已落地；
- Step 6 导出区保留；
- 但后端 `18181` 未正常访问，导出链路没有完整端到端验收；
- Python 侧 e2e 仍出现 `13 skipped`，自动化验收信号不够硬；
- MiniMax 子代理环境损坏，暂时不能依赖它产出报告。

因此下一步如果继续加功能，会把不稳定点越堆越深。面试导向下，最重要的是能回答：

```text
你这个项目到底能不能稳定演示？
你说的 RAG / Agent / Memory / Trace 在哪里能看到？
你怎么证明这些不是 PPT？
面试官追问某个模块时，你能不能马上打开代码和测试？
```

### 1.2 面试项目的短板已经不是材料，而是“材料和可运行界面之间的桥”

S33-S40 已经有大量面试材料：

- `docs/interview/Project_OnePager.md`
- `docs/interview/Architecture_Diagram.md`
- `docs/interview/Interview_QA_Cards.md`
- `docs/interview/Interview_QA_Cards_Extended.md`
- `docs/interview/Demo_Script_3min.md`
- `docs/interview/Demo_Script_10min.md`
- `docs/interview/Project_DeepDive_Index.md`
- `docs/interview/Technical_Highlights.md`
- `docs/interview/Known_Limitations_For_Interview.md`
- RAG / Memory / MCP / Multi-Agent 系列 Explainer

但现在的问题是：

- 面试材料在 `docs/interview`；
- 用户演示在前端工作台；
- 代码证据在 `apps/api`、`apps/web`；
- 测试证据在 pytest / Playwright；
- 失败案例在报告和 docs；
- 它们还没有形成一个“面试官一问，我就能点开”的展示入口。

所以 Session 43 应该把这些东西连起来。

## 2. Session 43 总目标

新增一个“面试演示模式 / Interview Mode”，让 PaperAgent 能在 3 分钟或 10 分钟内稳定展示：

1. 项目解决什么问题；
2. 工作台如何从题目走到证据和开题建议；
3. RAG / Agent / Trace / Memory / MCP / Gate 分别在哪里体现；
4. 每个亮点对应哪些代码、测试、文档；
5. 当前有哪些真实限制，如何诚实解释；
6. 遇到面试官深挖时，从 UI 直接跳到对应 Deep Dive 资料。

本轮核心交付不是“再写一堆文档”，而是：

```text
一个能面试演示的 UI 模式
+ 一份可点击的技术深挖索引
+ 一条可跑通的稳定 Demo Case
+ 一组面试验收测试
```

## 3. 产品形态

### 3.1 增加 Interview Mode

在前端新增一个轻量入口：

```text
普通模式 | 面试模式
```

或使用 URL 参数：

```text
http://127.0.0.1:18182/?mode=interview
```

Interview Mode 打开后，页面不改变核心功能，只增加面试辅助层：

- 顶部出现“3 分钟 Demo / 10 分钟 Demo / 技术深挖 / 已知限制”切换。
- 工作台关键区域出现可选讲解标注。
- 每个关键模块可打开“面试解释卡”。
- 每张解释卡都链接到真实代码、测试、文档。

### 3.2 面试演示总览

建议在工作台上方或侧边增加一个紧凑的 Interview Bar：

```text
Interview Mode
[3min Demo] [10min Demo] [RAG] [Memory] [MCP] [Trace] [Failure] [Tests]
```

点击后不跳走主页面，而是打开右侧或底部抽屉。

### 3.3 技术深挖抽屉

新增 `Deep Dive Drawer`，用于回答面试官追问。

内容结构：

```text
技术点：RAG Pipeline
一句话解释：把候选资源检索拆成 QueryPlan、Candidate、Rerank、Evidence 晋升和评估。
面试官可能问：
- 为什么不用纯向量库？
- RRF 是怎么做的？
- 你怎么评估检索效果？
可展示代码：
- apps/api/app/services/rag_pipeline.py
- apps/api/app/services/rag_evaluator.py
可展示测试：
- apps/api/tests/test_session34_*.py
相关文档：
- docs/interview/RAG_Design_Explainer.md
- docs/interview/Deep_Dive_QA_RAG.md
当前边界：
- Embedding / 真向量库暂未接入，当前重点是可解释检索与评估闭环。
```

## 4. 面试模式必须覆盖的 8 个模块

### 4.1 Workflow / Step Workbench

要展示：

- 分步 Gate；
- 用户确认；
- 横向 Step；
- LLM 对话；
- 证据 Trace；
- stale 传播。

面试解释：

> 我没有做一键生成报告，而是把论文开题拆成 Human-in-the-loop 的多阶段 Agent Workflow。每一步都可确认、可回看、可回放，避免模型一次性跑偏。

### 4.2 RAG / Evidence Retrieval

要展示：

- 关键词拆解；
- 检索计划；
- 论文 / 数据集 / 工程候选；
- 候选资源到证据的差异；
- RAG 评估指标入口。

面试解释：

> PaperAgent 的检索不是“搜到就算证据”，而是 Candidate -> Verified Candidate -> Evidence 的治理链路。面试里可以重点讲 RAG Pipeline、Rerank 和 Evaluation。

### 4.3 Evidence Governance

要展示：

- 可用证据；
- 待核验证据；
- 不推荐证据；
- 用户通过对话 reject / restore；
- Trace 保留原因。

面试解释：

> 这个项目最核心的工程边界是 Candidate != Evidence。LLM 可以建议，但不能无确认地把候选写入最终报告。

### 4.4 Agent Memory / Trace / Replay

要展示：

- Trace 分组；
- 用户确认；
- 修改记录；
- stale 传播；
- RunEvent / Transcript 资料入口。

面试解释：

> Trace 不是普通日志，而是 Agent Memory 的一部分。它支持回放、审计和后续压缩摘要。

### 4.5 Tool Boundary / MCP

要展示：

- 哪些工具可以读；
- 哪些工具不能写；
- 写操作必须 Gate；
- 工具调用进入 Trace。

面试解释：

> PaperAgent 对外部 Agent 是 read-mostly 暴露。检索、读候选、读 Trace 可以开放，写 Evidence / 删除 / 导出必须有 Gate。

### 4.6 LLM Interaction / Workspace Command

要展示：

- 用户用自然语言修改关键词；
- 系统生成修改预览；
- 用户确认后应用；
- 后续步骤 stale。

面试解释：

> 这是把“聊天”变成“可审计工作台操作”的最小实现。LLM 不是直接改数据，而是生成 WorkspaceCommand，经过用户确认后再应用。

### 4.7 Failure / Limitation

要展示：

- URL 验证失败；
- 数据集不足；
- 证据不足不能导出；
- 后端未启动时如何提示；
- 当前真实限制。

面试解释：

> 我会主动展示失败案例，因为 Agent 项目不只是 happy path。边界、降级和诚实表达是这个项目的设计重点。

### 4.8 Tests / Baseline

要展示：

- 当前测试数量；
- 后端测试；
- Playwright；
- skipped / blocked 项；
- 如何修复和解释。

面试解释：

> 面试时我不只讲功能，还能展示测试金字塔和已知 blocked 项。S42 暴露的后端未启动和 e2e skipped 要在 S43 收敛。

## 5. 实施任务

### Task 1：S42 遗留验证收口

目标：

- 面试演示前先修复最容易露怯的稳定性问题。

执行要求：

- 确认后端 `18181` 启动方式。
- 补一次 Step 6 导出端到端 smoke。
- 明确 `pytest e2e 13 skipped` 的原因。
- 如果短期不能修，写入 `Known_Limitations_For_Interview.md` 或本轮报告。

验收：

- 前端 `18182` 可访问。
- 后端 `18181` 可访问，或页面有清晰离线提示。
- Step 6 导出至少有一次 smoke 结果。
- skipped 项有明确解释，不是沉默跳过。

### Task 2：Interview Mode 入口

目标：

- 增加面试模式入口。

执行要求：

- 支持 URL 参数或 UI toggle。
- 默认不影响普通用户模式。
- 开启后显示 Interview Bar。
- Interview Mode 状态不写入业务数据。

验收：

- 普通模式 UI 不受干扰。
- `?mode=interview` 能打开面试辅助层。
- 关闭后回到普通工作台。

### Task 3：稳定 Demo Case

目标：

- 面试时不依赖临场输入和不稳定检索。

执行要求：

- 固化一个 Demo 题目，例如：`基于 YOLO 的道路裂缝检测`。
- 固化对应关键词、候选论文、数据集、工程、可行性结论。
- Demo Case 可一键加载。
- Demo Case 明确标注是演示数据还是实时数据。

验收：

- 点击“加载 Demo Case”后 10 秒内进入可讲状态。
- Step 1-5 内容完整。
- Trace 和 LLM 对话有合理历史。
- 不误导为实时检索结果。

### Task 4：技术深挖抽屉

目标：

- 面试官问到某个模块时，能直接打开对应解释。

执行要求：

- 建立模块索引：
  - Workflow
  - RAG
  - Evidence
  - Memory
  - MCP
  - Multi-Agent
  - Failure
  - Tests
- 每个模块包括：
  - 一句话解释；
  - 面试官可能追问；
  - 可展示代码；
  - 可展示测试；
  - 相关文档；
  - 当前边界。

验收：

- 至少 8 个模块可打开。
- 每个模块至少有 1 个代码路径、1 个测试路径、1 个文档路径。
- 不出现“只讲概念没有证据”的模块。

### Task 5：工作台热点标注

目标：

- 让 UI 本身能辅助讲解。

执行要求：

- 面试模式下，在关键区域显示小型标注：
  - Step Gate；
  - LLM 对话；
  - WorkspaceCommand；
  - Evidence Trace；
  - stale；
  - Export Readiness。
- 标注默认简短，点击展开。

验收：

- 标注不会遮挡正常操作。
- 每个标注都能连接到 Deep Dive 模块。
- 普通模式不显示这些标注。

### Task 6：Demo 脚本和 UI 对齐

目标：

- 让 `docs/interview/Demo_Script_3min.md` 和 `Demo_Script_10min.md` 不再只是文档，而能对应真实 UI 步骤。

执行要求：

- 在 Interview Mode 中提供 3min / 10min 脚本 checklist。
- 每一项脚本对应一个 UI 高亮区域。
- 脚本中记录预计耗时。

验收：

- 用户能按 3min 脚本完成一轮演示。
- 用户能按 10min 脚本完成深挖演示。
- 脚本中的每个动作都能在 UI 中找到。

### Task 7：面试材料同步更新

目标：

- S41-S43 的新工作台能力进入面试材料。

需要更新：

- `docs/interview/Project_OnePager.md`
- `docs/interview/Architecture_Diagram.md`
- `docs/interview/Technical_Highlights.md`
- `docs/interview/Project_DeepDive_Index.md`
- `docs/interview/Known_Limitations_For_Interview.md`
- `docs/interview/Demo_Script_3min.md`
- `docs/interview/Demo_Script_10min.md`

必须新增或更新的表述：

- Step Workbench；
- LLM 对话式 WorkspaceCommand；
- Trace 折叠；
- stale 传播；
- Interview Mode；
- S42 遗留限制。

验收：

- 面试材料不再停留在 S40 旧状态。
- 新 UI 能在材料中被解释。
- 当前限制诚实记录。

### Task 8：面试技术开关矩阵

目标：

- 把 RAG、Agent、Memory、SubAgent、MCP 等面试高频技术做成可开关能力。
- 默认用户路径保持轻量，面试或技术深挖时再打开重模块。

设计原则：

```text
能讲清楚的技术才打开；
和当前项目强相关的技术默认启用；
较重、较炫但非主链路必需的技术默认关闭；
所有关闭项都要能解释“为什么不用、什么时候用、打开后成本是什么”。
```

建议新增一个 `Interview Tech Switches` 面板：

| 开关 | 默认 | 面试用途 | 项目关联度 | 打开成本 | 关闭时说明 |
|---|---|---|---|---|---|
| `rag_chunking` | 开 | 展示论文/网页/报告切分策略 | 高 | 低 | 不关闭，属于 RAG 基础 |
| `rag_hybrid_search` | 开 | 展示关键词 + 稀疏/语义召回思路 | 高 | 中 | 当前可用轻量实现，不依赖真向量库 |
| `rag_rerank` | 开 | 展示 RRF / 规则重排 / 权重调节 | 高 | 中 | 面试重点，建议保留 |
| `vector_db` | 关 | 讨论 Milvus/Qdrant/FAISS 扩展 | 中 | 高 | 当前数据量小，先用可解释检索 |
| `langgraph_runtime` | 关 | 展示可迁移到 StateGraph 的设计 | 中 | 高 | 当前用自研轻量状态机，避免过度工程 |
| `human_in_loop_interrupt` | 开 | 展示用户确认 Gate | 高 | 低 | 与开题场景强相关 |
| `subagent_router` | 关 | 展示未来多 Agent 路由 | 中 | 高 | 当前单流程更稳定，SubAgent 只做设计预留 |
| `memory_snapshot` | 开 | 展示项目状态恢复 | 高 | 中 | 与 Trace/Replay 强相关 |
| `memory_compression` | 关 | 展示长上下文压缩 | 中 | 中 | 当前流程短，先保留接口 |
| `mcp_tools` | 关 | 展示外部 Agent 工具边界 | 中 | 中 | 面试深挖时打开，默认不暴露写工具 |
| `cost_control` | 关 | 展示多模型/多 Agent 成本治理 | 中 | 中 | 当前 MVP 不需要实时成本调度 |

验收：

- Interview Mode 中能看到技术开关矩阵。
- 每个开关都有：用途、当前状态、为什么默认开/关、面试解释。
- 关闭重技术不会影响普通选题主流程。
- 打开开关时，如果只是设计预留，必须标注 `design-only`，不能伪装成已完整实现。

### Task 9：RAG 面试技术栈显性化

目标：

- 把 RAG 从“检索候选资源”讲成面试可深挖的 pipeline。

必须覆盖：

1. Query Understanding：从题目拆方法、任务、对象。
2. Chunking：对论文摘要、网页、项目 README、数据集说明做切分。
3. Metadata Extraction：提取年份、来源、任务、方法、数据集、代码可用性。
4. Retrieval：关键词检索、规则召回、可选语义召回。
5. Hybrid Fusion：多路召回融合，例如 RRF 或规则加权。
6. Rerank：按关键词覆盖、URL 可访问、复现信号、数据集可用性、近期性重排。
7. Evidence Promotion：Candidate 到 Evidence 的确认门。
8. Evaluation：Recall@K、MRR、citation coverage、evidence precision。

在 UI 中的呈现方式：

```text
RAG Deep Dive
├─ 切分策略
├─ 查询改写
├─ 召回通道
├─ 重排权重
├─ 候选到证据
└─ 评估指标
```

面试解释：

> 当前 PaperAgent 不把 RAG 简化成“调一个向量库”。它更强调学术选题场景里的可解释检索：题目拆解、候选来源、证据晋升和失败原因都要可追踪。向量库是可替换组件，不是项目核心卖点。

验收：

- Deep Dive 中有 RAG Pipeline 图。
- 每一层都有当前实现状态：`implemented` / `lightweight` / `design-only`。
- 能解释为什么当前不默认启用重向量库。

### Task 10：Agent 模式设计显性化

目标：

- 把当前 Step Workbench 映射到 LangGraph 式 Agent 架构，但不强行引入重依赖。

参考 LangGraph 思路：

- `StateGraph`：把流程拆成节点和状态迁移。
- `interrupt` / `Command`：人工确认后恢复执行。
- `checkpoint`：保存线程状态，用于恢复和 replay。
- `stream`：每一步流式输出。
- `subgraph`：复杂模块可以独立成子图。
- `supervisor`：未来多 Agent 路由与调度。

PaperAgent 当前映射：

| LangGraph 概念 | PaperAgent 当前对应 | 默认策略 |
|---|---|---|
| StateGraph | Step 1-5 状态机 | 轻量自研实现 |
| interrupt | 用户确认 Gate | 默认启用 |
| Command resume | 确认后进入下一步 | 默认启用 |
| checkpoint | Project State / Trace / Snapshot | 默认启用或轻量实现 |
| stream | LLM 思维 / 对话流式输出 | 默认启用 |
| subgraph | RAG / Feasibility / Proposal 子流程 | design-only |
| supervisor | Multi-Agent Router | design-only |

实现要求：

- Interview Mode 中提供 `Agent Architecture` 深挖卡。
- 明确写出“当前没有强制接 LangGraph Runtime，而是保留可迁移映射”。
- 如果后续接 LangGraph，只作为可选 runtime，不替换主业务状态机。

面试解释：

> 我没有为了面试硬接 LangGraph，而是先把流程设计成能映射到 LangGraph 的形状：状态、节点、人工中断、恢复、流式事件和 checkpoint 都有对应物。这样既能讲清现代 Agent 架构，又避免在 MVP 阶段引入过重依赖。

验收：

- Deep Dive 中能展示 `PaperAgent State Machine -> LangGraph Mapping`。
- 能回答“为什么现在不用 LangGraph runtime”。
- 能回答“如果要接 LangGraph，会替换哪一层”。

### Task 11：Memory 管理与上下文压缩纳入面试矩阵

目标：

- 把 Trace、RunEvent、对话、证据、Snapshot 统一成面试可讲的 Memory 体系。

Memory 层次：

```text
Working Memory
  当前 Step、当前输入、当前待确认问题

Conversation Memory
  LLM 对话、用户追问、WorkspaceCommand 预览

Trace Memory
  每一步状态变化、工具调用、用户确认、失败记录

Evidence Memory
  已确认 Evidence、被拒绝 Evidence、证据来源、引用关系

Project Snapshot
  可恢复的项目状态摘要

Compressed Memory
  长流程压缩摘要，保留关键证据和用户决定
```

开关建议：

| Memory 能力 | 默认 | 说明 |
|---|---|---|
| Working Memory | 开 | 当前工作台必须依赖 |
| Conversation Memory | 开 | S42 对话式编辑需要 |
| Trace Memory | 开 | 可追溯与面试解释核心 |
| Evidence Memory | 开 | Candidate != Evidence 的证据层 |
| Project Snapshot | 开或轻量 | 支持恢复和 Demo Case |
| Compressed Memory | 关 | 长上下文优化，先设计预留 |
| Vector Memory | 关 | 不和当前主线强绑定，面试时作为扩展讲 |

必须解释：

- 什么东西可以压缩；
- 什么东西不能压缩；
- Evidence Memory 不能被普通对话压缩丢失；
- 用户确认记录不能被删除；
- 删除证据是软删除，Trace 必须保留。

面试解释：

> PaperAgent 的记忆不是“把聊天历史全塞回 prompt”。我把记忆分成工作记忆、对话记忆、Trace 记忆、证据记忆和项目快照。真正不能丢的是证据和用户确认，普通对话可以压缩，证据链不能压缩掉。

验收：

- Deep Dive 中新增 `Memory Management` 模块。
- Memory 模块能展示哪些开、哪些关。
- 能解释上下文压缩边界。
- 能解释刷新或恢复后哪些状态必须保留。

### Task 12：SubAgent 与 Multi-Agent 设计边界

目标：

- 把 SubAgent / Multi-Agent 做成面试可讲的扩展设计，但默认不启用重编排。

建议角色：

```text
Supervisor
├─ KeywordAgent
├─ RetrievalAgent
├─ EvidenceVerifierAgent
├─ FeasibilityAgent
├─ ProposalDraftAgent
└─ ReviewAgent
```

默认策略：

- 普通模式：不用 Multi-Agent，保持单流程稳定。
- Interview Mode：展示 Multi-Agent 设计图和路由策略。
- 技术深挖：允许打开 `subagent_router=design-only`。
- 不允许 SubAgent 直接写 Evidence。

必须回答：

- 为什么现在不拆成多 Agent？
- 什么时候应该拆？
- Supervisor 怎么避免成为瓶颈？
- 子 Agent 冲突时怎么处理？
- 成本和延迟怎么控制？
- 哪些写操作必须回到主流程 Gate？

验收：

- Multi-Agent 深挖卡明确标注当前是设计预留。
- 不把 design-only 说成 implemented。
- 能展示每个 Agent 的输入、输出、权限边界。

### Task 13：普通模式与面试模式的技术降级策略

目标：

- 让重技术可以人为关闭，避免项目为了面试变慢、变脆、变复杂。

需要定义三档运行配置：

```text
lite
  普通用户默认模式：轻量状态机 + 规则/RAG 基线 + Gate + Trace

interview
  面试演示模式：打开 Deep Dive、技术开关、Demo Case、解释卡

full
  技术深挖模式：可打开 design-only / heavy 模块说明，但不默认进入真实执行
```

配置示例：

```json
{
  "mode": "interview",
  "rag_chunking": true,
  "rag_hybrid_search": true,
  "rag_rerank": true,
  "vector_db": false,
  "langgraph_runtime": false,
  "human_in_loop_interrupt": true,
  "subagent_router": false,
  "memory_compression": false,
  "mcp_tools": false
}
```

验收：

- UI 能显示当前模式。
- 能解释每个关闭项。
- 关闭重模块不影响主线 Demo。
- 打开重模块时如果没有真实实现，必须显示 `设计预留，不参与当前执行`。

## 6. Playwright 测试要求

建议新增：

```text
apps/web/e2e/test_one_topic_session43_interview_mode.py
```

### 测试 1：Interview Mode 可打开

断言：

- `?mode=interview` 显示 Interview Bar。
- 普通模式不显示 Interview Bar。

### 测试 2：Demo Case 可加载

断言：

- 点击 Demo Case 后，Step 1-5 有内容。
- Trace 有历史事件。
- LLM 对话有过程消息。

### 测试 3：Deep Dive 抽屉可打开

断言：

- RAG 模块可打开。
- Memory 模块可打开。
- MCP 模块可打开。
- 每个模块包含代码 / 测试 / 文档路径。

### 测试 4：脚本 checklist 与 UI 联动

断言：

- 点击 3min Demo 第一项，高亮工作台输入区或 Step 区。
- 点击 RAG 项，高亮证据检索或相关模块。

### 测试 5：普通模式不受影响

断言：

- 普通模式下没有面试辅助标注。
- 普通模式下原 Step Workbench 功能仍可用。

### 测试 6：导出链路 smoke

断言：

- 后端可用时，Step 6 导出按钮能返回结果。
- 后端不可用时，页面显示清晰错误，不出现静默失败。

### 测试 7：技术开关矩阵

断言：

- Interview Mode 中能看到 RAG / Agent / Memory / MCP / SubAgent 相关开关。
- 每个开关显示当前状态：`on` / `off` / `design-only`。
- 关闭 `vector_db`、`langgraph_runtime`、`subagent_router` 后，主线 Demo 仍可跑。
- design-only 模块不能触发真实执行。

### 测试 8：RAG 深挖层次

断言：

- RAG Deep Dive 至少显示：Chunking、Retrieval、Hybrid Fusion、Rerank、Evaluation。
- 每一层都显示当前实现状态。
- 向量库关闭时，有“为什么当前不默认启用”的解释。

### 测试 9：Agent / LangGraph 映射

断言：

- Agent Deep Dive 显示 StateGraph / interrupt / checkpoint / streaming / subgraph / supervisor 的映射。
- 当前实现被标注为轻量状态机，而不是伪装成真实 LangGraph runtime。
- human-in-the-loop Gate 被标注为默认启用。

### 测试 10：Memory 管理边界

断言：

- Memory Deep Dive 显示 Working / Conversation / Trace / Evidence / Snapshot / Compressed Memory。
- Evidence Memory 标注为不可被普通压缩丢弃。
- 用户确认记录标注为不可删除。
- Compressed Memory 和 Vector Memory 默认关闭或 design-only。

## 7. 人工验收脚本

### 7.1 3 分钟演示验收

流程：

1. 打开 Interview Mode。
2. 加载 Demo Case。
3. 按 3min checklist 演示：
   - 项目目标；
   - Step Workbench；
   - 证据 Trace；
   - 对话式修改；
   - 导出前检查。

通过标准：

- 3 分钟内能讲清项目价值。
- 不需要临时翻文档找材料。
- 每个讲点能在 UI 中看到。

### 7.2 技术深挖验收

流程：

1. 打开 Deep Dive。
2. 分别点击 RAG、Memory、MCP、Failure、Tests。

通过标准：

- 每个模块都有代码路径。
- 每个模块都有测试路径。
- 每个模块都有文档路径。
- 每个模块都有边界说明。

### 7.3 面试官追问模拟

模拟问题：

```text
你这个项目的 RAG 怎么评估？
你的文档/论文是怎么切分的？
为什么现在不用真向量库？
为什么没有直接上 LangGraph？
如果未来接 LangGraph，替换哪一层？
Human-in-the-loop 在哪里体现？
SubAgent 为什么默认不启用？
你怎么管理 Agent 记忆？
什么内容能压缩，什么不能压缩？
为什么 LLM 不能直接写证据？
Trace 和普通日志有什么区别？
用户修改关键词后，后续结果怎么处理？
你这个项目最大的限制是什么？
如果后端挂了，前端怎么表现？
```

通过标准：

- 每个问题都能从 Interview Mode 找到回答入口。
- 回答不夸大。
- 能指到代码、测试或文档。

## 8. 本次不做

本次不做：

- 不继续新增毕业论文业务功能。
- 不重写 RAG。
- 不真正拆 Multi-Agent。
- 不修复 MiniMax 子代理环境，除非它阻塞主验收。
- 不把 Interview Mode 做成复杂后台系统。
- 不做视觉炫技。

本轮只做一件事：**把已有能力变成面试现场能讲、能点、能证伪的项目展示入口。**

## 9. 面试解释

### 面试官可能会问

```text
你这个项目看起来功能很多，怎么证明不是散的？
你怎么向别人展示你的技术难点？
如果我问 RAG / Memory / MCP，你能现场打开代码吗？
你的 demo 是真实跑的还是 mock 的？
```

### 为什么这样设计

S33-S40 已经有面试材料，但材料和可运行界面之间缺少桥。S41-S42 又把工作台 UI 做起来了，所以 S43 应该把两条线合并：让 UI 成为面试材料的入口，让面试材料反过来解释 UI 背后的工程设计。

### PaperAgent 的回答

> 我把 PaperAgent 做成了两种模式：普通用户模式用于真实选题，Interview Mode 用于项目演示和技术深挖。面试时我可以用同一个 Demo Case 展示 Step Workbench、RAG、Evidence Gate、Trace、WorkspaceCommand 和导出前检查；如果面试官追问某个模块，我能从 UI 直接打开对应代码、测试和设计文档。

### 项目证据

- UI：Step Workbench、Interview Mode、Deep Dive Drawer。
- 文档：`docs/interview/*`。
- 测试：S34-S42 后端与 Playwright 测试。
- 报告：`Plan/reports/Session_42_WorkbenchChatEdit_验收报告.md`。

### 边界

- Demo Case 可以是固化演示数据，但必须明确标注。
- 后端未启动时不能假装导出成功。
- 未接真实向量库、真实 URL 验证、真实 Multi-Agent 的地方必须诚实说明。
- LangGraph / SubAgent / Vector DB / Memory Compression 这类重技术必须可关闭。
- design-only 能力只能作为架构预留展示，不能在面试材料中写成已完整落地。

## 10. 验收报告要求

建议报告命名：

```text
Plan/reports/Session_43_InterviewMode_TechDeepDive_验收报告.md
```

报告必须包含：

- Interview Mode 截图。
- Demo Case 加载截图。
- Deep Dive 抽屉截图。
- 3min / 10min checklist 截图。
- RAG / Memory / MCP 至少 3 个技术模块的代码 / 测试 / 文档链接。
- 技术开关矩阵截图。
- RAG Chunking / Retrieval / Rerank / Evaluation 深挖截图。
- Agent / LangGraph 映射截图。
- Memory 管理与压缩边界截图。
- Step 6 导出 smoke 结果。
- e2e skipped 项解释或修复结果。
- 已知限制更新说明。

## 11. 完成判定

只有满足以下条件，Session 43 才算通过：

- 可以打开 Interview Mode。
- 可以一键加载稳定 Demo Case。
- 可以按 3 分钟脚本完成演示。
- Deep Dive 至少覆盖 8 个技术模块。
- 每个技术模块都有代码、测试、文档证据。
- RAG 技术栈能讲清切分、检索、融合、重排和评估。
- Agent 设计能讲清轻量状态机、LangGraph 映射、human-in-the-loop、SubAgent 边界。
- Memory 设计能讲清 Working / Conversation / Trace / Evidence / Snapshot / Compression 的边界。
- 较重技术具备可关闭开关，关闭后主线 Demo 不受影响。
- design-only 能力有明确标注，不夸大实现状态。
- S42 的 Step 6 导出链路有 smoke 结论。
- e2e skipped 项有明确解释或被修复。
- `docs/interview` 至少同步更新 S41-S43 的新能力。
- 报告中包含面试解释和当前边界。

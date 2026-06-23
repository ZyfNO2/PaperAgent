# PaperAgent 面试导向需求清单

> 日期：2026-06-21  
> 目标：把 PaperAgent 从“毕业开题工具”包装成一个能应对大模型 / Agent / RAG / AI 工程岗位面试深挖的项目。  
> 资料来源：本地 B 站分析 Markdown 为主，近期 GitHub / 网络调研为辅。

---

## 1. 已验收事项

上一份用户体验测试方案：

```text
Plan/PaperAgent_用户使用体验测试与人性化改造方案.md
```

验收结论：

```text
通过。
它已经覆盖首屏 UX、流式交互、论文复现、数据集/工程判断、创新点发现、可行性、开题报告、委员会复核、全流程测试。
下一阶段不再重复写用户体验细节，而是转向“面试导向包装与技术深挖”。
```

当前项目最新进展：

```text
Session 25-32 已有验收报告；
S31 已有全链路 baseline；
S32 已有导出前 readiness 与模板合规检查；
但 S31 全量回归仍有 1 个既有失败项 test_session6_llm_path.py，需要在面试前说明或修复。
```

---

## 2. 本地资料提炼

### 2.1 公司面经：`G:/Agent/bilibili-analysis/01-公司面经`

高频面试要求：

```text
1. 不是只问八股，会围绕项目细节连续追问；
2. Agent 记忆、上下文恢复、Transcript、压缩策略是近期高频；
3. RAG 不能只讲“向量库 + 相似度”，要讲 Hybrid Search、Rerank、评估、GraphRAG / Agentic RAG；
4. 多 Agent 不能为了多而多，要说明复杂度、Supervisor 瓶颈、并行、投票、路由错误如何补救；
5. 模型选型、量化、KV Cache、推理加速要能讲一套可落地策略；
6. 工具调用失败、Function Calling / MCP、安全权限是 Agent 项目必问；
7. 面试官会问“什么让 AI 做，什么不让 AI 做”。
```

PaperAgent 对应需求：

```text
必须能讲清：为什么 Candidate 不能直接变 Evidence；
必须能讲清：为什么需要 keyword gate、candidate gate、readiness gate；
必须能讲清：RunEvent / Trace / EvidenceRef 三者关系；
必须能讲清：PaperAgent 是单 Agent、Supervisor、多 Agent 还是可扩展混合架构；
必须能讲清：如果子 Agent 膨胀，怎么做层级路由和并行评审。
```

### 2.2 Agent / RAG 项目实战：`G:/Agent/bilibili-analysis/02-Agent_RAG项目实战`

高频工程要求：

```text
1. 项目架构本身就是 RAG 面试题的活体答案；
2. Hybrid Search = BM25 + Dense Embedding；
3. Rerank = CrossEncoder / LLM Rerank；
4. Evaluation = Ragas / DeepEval / 自定义命中率、引用准确率；
5. MCP Server 是加分项；
6. 多模态处理可先做 image-to-text，降低复杂度；
7. 配置驱动与可插拔组件是面试亮点；
8. DEV_SPEC 是单一事实来源。
```

PaperAgent 对应需求：

```text
把论文/数据集/工程检索包装为 Modular RAG Pipeline；
明确 Retriever / Reranker / Verifier / Reporter 的接口；
补 RAG 评估指标：Recall@K、MRR、Citation Coverage、Evidence Precision；
把已有 CandidateResource / EvidenceRef 作为 RAG 输出结构；
考虑新增 MCP Server 入口，暴露 search_topic_evidence / get_project_trace / export_proposal。
```

### 2.3 ClaudeCode / OpenClaw / Harness：`G:/Agent/bilibili-analysis/03-ClaudeCode_OpenClaw_Harness技术`

高频 Agent 架构要求：

```text
1. 四层记忆：指令文件、短期对话上下文、Session Memory、Memdir 长期记忆；
2. Transcript 是会话账本，用于恢复；
3. 压缩不是清空，而是瘦身后恢复文件/工具上下文；
4. 写入机制要有触发条件、锁、异步整理；
5. 权限系统、安全审查、SubAgent 架构都是面试追问点；
6. “学习经典 Agent 架构，再设计自己的 Agent 项目”是面试包装路线。
```

PaperAgent 对应需求：

```text
把 RunEventStore 讲成 PaperAgent 的 Transcript；
把 ProjectMemory 讲成跨会话长期记忆；
把 Trace / Evidence / FinalPackage 讲成可恢复上下文；
把 readiness hard block 讲成权限/安全审查；
把 Session SOP + reports 讲成 Harness 式工程闭环。
```

### 2.4 大模型自学与面试方法：`G:/Agent/bilibili-analysis/04-大模型自学与面试方法`

面试包装要求：

```text
1. 项目要能挂简历；
2. 项目要能讲出工程目标、架构、技术难点、测试、指标；
3. 简历亮点要挂钩开源项目和近期热点；
4. 不要只说“做了一个工具”，要说“解决了什么可验证问题”；
5. 学习路线要覆盖基础知识、典型架构、个人项目。
```

PaperAgent 对应需求：

```text
简历表述应从“开题报告助手”升级为“科研证据 Agent 工作台”；
面试讲法应强调：多阶段 RAG、证据门控、流式可回放、候选到证据晋升、报告合规检查；
项目需要补架构图、指标页、失败案例、演示脚本。
```

---

## 3. 近期网络调研

### 3.1 大模型学习 / 八股 / 面试相关高热仓库

> GitHub 元数据查询时间：2026-06-21。`updated_at` 会随 Star/Issue 等活动变化，`pushed_at` 更接近代码最近提交。

| 仓库 | Stars | pushed_at | 可借鉴点 |
|---|---:|---|---|
| [mlabonne/llm-course](https://github.com/mlabonne/llm-course) | 80.2k | 2026-02-05 | LLM Fundamentals / Scientist / Engineer 三段式路线，适合做 PaperAgent 面试知识地图 |
| [datawhalechina/happy-llm](https://github.com/datawhalechina/happy-llm) | 31.4k | 2026-05-06 | 从零构建大模型，适合补 Transformer、Attention、训练/推理八股 |
| [datawhalechina/self-llm](https://github.com/datawhalechina/self-llm) | 31.0k | 2026-06-17 | 本地部署、LoRA/全参微调、多模型教程，适合补推理部署与微调讲法 |
| [liguodongiot/llm-action](https://github.com/liguodongiot/llm-action) | 24.6k | 2026-05-25 | 大模型工程化、应用落地经验，适合补项目工程化表达 |
| [datawhalechina/llm-cookbook](https://github.com/datawhalechina/llm-cookbook) | 24.3k | 2025-06-12 | 吴恩达大模型课程中文化，适合补 Prompt、RAG、Agent 入门讲法 |
| [NLP-LOVE/ML-NLP](https://github.com/NLP-LOVE/ML-NLP) | 17.7k | 2026-01-09 | ML/NLP 面试理论基础，适合补传统八股底座 |
| [datawhalechina/llm-universe](https://github.com/datawhalechina/llm-universe) | 13.3k | 2026-02-24 | 大模型应用开发、知识库、RAG、评估与优化 |
| [InternLM/Tutorial](https://github.com/InternLM/Tutorial) | 2.0k | 2026-04-22 | LLM/VLM 实战营，适合补实战训练营式演示路径 |

### 3.2 Agent / RAG 工程热门仓库

| 仓库 | Stars | pushed_at | 可借鉴点 |
|---|---:|---|---|
| [langchain-ai/langchain](https://github.com/langchain-ai/langchain) | 139.8k | 2026-06-21 | Agent engineering platform，讲 Agent/RAG 生态必须知道 |
| [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) | 87.5k | 2026-06-17 | MCP Server 生态，适合 PaperAgent 后续做工具入口 |
| [microsoft/autogen](https://github.com/microsoft/autogen) | 59.1k | 2026-04-15 | 多 Agent 编程框架，适合讲协作、对话、工具调用 |
| [mem0ai/mem0](https://github.com/mem0ai/mem0) | 59.0k | 2026-06-20 | AI Agent memory layer，适合对标记忆模块 |
| [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 54.1k | 2026-06-20 | 多角色 Agent 编排，适合讲角色协作和任务拆分 |
| [run-llama/llama_index](https://github.com/run-llama/llama_index) | 50.2k | 2026-06-20 | 文档 Agent / OCR / RAG 平台，适合对标科研文档检索 |
| [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 35.3k | 2026-06-21 | Resilient agents、checkpoint、time travel |
| [qdrant/qdrant](https://github.com/qdrant/qdrant) | 32.5k | 2026-06-21 | 向量数据库，适合 RAG 存储层答题 |
| [chroma-core/chroma](https://github.com/chroma-core/chroma) | 28.5k | 2026-06-20 | AI search infrastructure |
| [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | 27.3k | 2026-06-19 | 轻量多 Agent workflow |
| [deepset-ai/haystack](https://github.com/deepset-ai/haystack) | 25.6k | 2026-06-19 | Production-ready RAG / pipeline / agent workflow |
| [camel-ai/camel](https://github.com/camel-ai/camel) | 17.2k | 2026-06-17 | Multi-agent framework 与 human-in-the-loop |

---

## 4. PaperAgent 面试需求

### 4.1 必须能讲的项目一句话

```text
PaperAgent 是一个面向毕业论文开题场景的科研证据 Agent 工作台。
它把题目输入拆成关键词、检索计划、候选论文/数据集/工程、证据晋升、可行性裁决、开题报告草稿和导出前合规检查，并用 Trace / RunEvent / EvidenceRef 保证过程可追溯。
```

### 4.2 必须能画出的架构

```text
User Topic
  -> Step Deck / Streaming UI
  -> Keyword Gate
  -> Query Plan
  -> CandidateResource
  -> Workspace SelectedResource
  -> URLVerified
  -> Evidence Promotion Gate
  -> EvidenceRef
  -> Feasibility Judge
  -> Proposal Draft
  -> Committee Review
  -> Export Readiness
  -> FullChain Baseline
```

### 4.3 必须能回答的八股映射

| 面试点 | PaperAgent 回答材料 |
|---|---|
| RAG 为什么不是简单向量库 | QueryPlan + Candidate + EvidenceRef；后续补 Hybrid Search / Rerank / Eval |
| 如何避免幻觉 | Candidate != Evidence；URLVerified；EvidenceRef；ReportQuality / Readiness hard block |
| Agent 记忆怎么做 | RunEventStore、TraceStore、FinalPackage、Session reports；后续补 ProjectMemory |
| 工具调用如何管控 | PromptProtocol.isToolAllowed；keyword gate；evidence promotion gate |
| Function Calling / MCP | 后续可将 search_topic_evidence / get_trace / export_report 暴露为 MCP tools |
| 多 Agent 怎么设计 | 当前是单 Agent + Gates；后续可扩展 Supervisor + Retriever/Verifier/Reviewer 子 Agent |
| 子 Agent 过多怎么办 | 层级路由、并行候选、投票复核、失败降级、限制顺序深度 |
| 如何评估 | S17/S31 baseline、pytest、Playwright、Readiness、Evidence Precision、Citation Coverage |
| 如何做流式 | StepDeck + RunEvent + token_delta/card_delta + replay |
| 如何做安全 | 禁止任意 JS、action whitelist、Evidence gate、readiness hard block |
| 如何做部署/稳定性 | FastAPI、静态前端、runtime jsonl、测试矩阵、错误状态、回放 |
| 模型选型 | LLM 可降级 heuristic；模型负责建议，程序负责证据规则 |

---

## 5. 简历需求

建议项目名：

```text
PaperAgent：面向毕业论文开题的科研证据 Agent 工作台
```

建议简历描述：

```text
设计并实现一个多阶段科研证据 Agent 工作台，支持题目关键词拆解、论文/数据集/工程候选检索、候选到证据晋升、可行性裁决、开题报告草稿生成与导出前合规检查；通过 RunEvent/Trace/EvidenceRef 实现过程可回放与证据可追溯，使用 pytest + Playwright 构建全链路回归基线。
```

可量化亮点：

```text
1. 多阶段流程：keyword -> query_plan -> candidate -> evidence -> proposal -> review；
2. 多重 Gate：keyword gate、candidate gate、promotion gate、readiness gate；
3. 回归基线：S17 + S31 双基线；
4. 测试闭环：后端 pytest + 前端 Playwright；
5. 安全边界：Candidate != Evidence，LLM 不直接写 supports；
6. 可观测性：Trace / RunEvent / replay；
7. 面试加分：对齐 RAG、Agent memory、MCP、工具调用、评估体系。
```

---

## 6. 面试短板清单

当前还需要补强：

```text
1. RAG 真实 Hybrid Search / Rerank / Eval 还没有形成面试级闭环；
2. RunEventStore 真实持久化与 replay 需要稳定；
3. ProjectMemory / Transcript 需要显式设计，贴合 ClaudeCode 记忆面试；
4. MCP Server 暴露工具还没做；
5. 面试演示脚本、架构图、问答卡片还没有统一生成；
6. test_session6_llm_path.py 既有失败项需处理或记录为已知风险；
7. 需要把模型选型、降级策略、量化/KV Cache/LoRA 等八股与项目讲法绑定。
```


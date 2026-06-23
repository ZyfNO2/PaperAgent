# PaperAgent 面试导向长期改进 SPEC

> 日期：2026-06-21  
> 主依据：`G:/Agent/bilibili-analysis` 四组 Markdown。  
> 辅助依据：近期高热 GitHub 仓库与大模型面试趋势。  
> 目标：把 PaperAgent 长期改造成“能演示、能讲、能被深挖”的大模型应用项目。

---

## 1. 产品定位升级

旧定位：

```text
毕业开题报告助手
```

新定位：

```text
面向毕业论文开题的科研证据 Agent 工作台：
以多阶段 RAG、证据晋升、可回放 Agent 流程和导出前合规检查，帮助学生把一个题目变成可验证、可调整、可追溯的开题方案。
```

---

## 2. 长期技术主线

```text
Agent Workflow
  + Modular RAG
  + Evidence Governance
  + Memory / Transcript
  + MCP Tools
  + Evaluation / Baseline
  + Interview Story Pack
```

---

## 3. 模块 SPEC

### 3.1 Interview Story Pack

目的：

```text
让项目能直接用于简历、面试自我介绍、项目深挖。
```

产物：

```text
docs/interview/Project_OnePager.md
docs/interview/Architecture_Diagram.md
docs/interview/Interview_QA_Cards.md
docs/interview/Demo_Script.md
docs/interview/Failure_Cases.md
```

必须回答：

```text
为什么做；
用户是谁；
核心链路；
技术难点；
如何评估；
如何防幻觉；
如何恢复；
如何扩展多 Agent；
线上怎么稳定；
失败案例怎么处理。
```

### 3.2 Modular RAG

参考：

```text
llm-universe：RAG 入门与评估；
02-Agent_RAG项目实战：Hybrid Search、Rerank、Evaluation；
Haystack / LlamaIndex / LangChain：模块化 pipeline。
```

目标：

```text
把论文、数据集、工程检索从“候选卡”升级为可配置 RAG pipeline。
```

接口：

```text
Retriever
Reranker
Verifier
EvidenceBuilder
Evaluator
```

指标：

```text
Recall@K
MRR
Citation Coverage
Evidence Precision
URLVerified Rate
Candidate-to-Evidence Conversion Rate
```

### 3.3 Agent Memory / Transcript

参考：

```text
ClaudeCode 记忆模块：四层记忆 + Transcript + 压缩 + 写入机制；
mem0：AI Agent memory layer；
LangGraph：checkpoint / time travel。
```

目标：

```text
把 PaperAgent 的 RunEvent / Trace / Reports 体系包装成可讲的记忆系统。
```

新增概念：

```text
Transcript：RunEvent JSONL；
SessionMemory：当前项目状态摘要；
ProjectMemory：跨会话项目记忆；
EvidenceMemory：已确认 EvidenceRef；
Compression：长流程压缩摘要；
Replay：从 Transcript 恢复 UI。
```

### 3.4 Tool Boundary / MCP

参考：

```text
MCP Servers 高热仓库；
公司面经中 Function Calling / MCP 高频追问；
S23 PromptProtocol 已有 isToolAllowed。
```

目标：

```text
将 PaperAgent 能力暴露为 MCP tools，并保持权限边界。
```

工具：

```text
search_topic_evidence
get_candidate_resources
promote_candidate_to_evidence
get_project_trace
generate_proposal_draft
check_export_readiness
```

权限：

```text
未过 keyword gate 不能 search；
未 URLVerified 不能 promote；
未 report_quality 不能 export；
任意工具调用必须写 Trace。
```

### 3.5 Multi-Agent Expansion

当前：

```text
单流程 Agent + Gates。
```

长期：

```text
Supervisor
  -> KeywordAgent
  -> RetrievalAgent
  -> VerificationAgent
  -> FeasibilityAgent
  -> ProposalAgent
  -> ReviewAgent
```

面试必须能讲：

```text
为什么现在不用复杂 Multi-Agent；
何时拆；
怎么避免 Supervisor 成为瓶颈；
怎么并行；
怎么投票；
怎么处理路由错误；
怎么控制成本。
```

### 3.6 Evaluation / Baseline

当前：

```text
S17 baseline；
S31 full-chain baseline；
pytest + Playwright。
```

增强：

```text
RAG retrieval benchmark；
Evidence precision benchmark；
Report section coverage benchmark；
Hallucination check；
Human review rubric；
Latency dashboard。
```

---

## 4. 面试八股映射到功能

| 八股 | 项目功能 |
|---|---|
| Transformer / Attention | 作为背景知识，不强行塞项目 |
| KV Cache / 量化 | 用于解释模型部署与推理成本，不作为核心实现 |
| LoRA / QLoRA | 说明可选：学校模板/评审语气微调，但当前不用 |
| RAG | QueryPlan / Candidate / EvidenceRef |
| Hybrid Search | 后续 Modular RAG |
| Rerank | 候选排序升级 |
| Agent Memory | RunEvent / Transcript / ProjectMemory |
| Function Calling | Tool Boundary / MCP |
| Multi-Agent | 可扩展 Supervisor 架构 |
| Safety | JS 禁止、action whitelist、Evidence gate |
| Evaluation | S17/S31 baseline、pytest、Playwright、readiness |

---

## 5. 长期 Session 建议

```text
Session 33：面试导向项目叙事与架构材料
Session 34：RAG 面试级检索评估与 Hybrid/Rerank 设计
Session 35：Agent Memory / Transcript / Replay 强化
Session 36：MCP Server 最小工具暴露
Session 37：Multi-Agent 可扩展设计与成本控制
Session 38：面试问答卡片与 Demo 脚本
Session 39：失败案例库与反问追问准备
Session 40：简历项目包装与技术亮点收束
```

---

## 6. 长期验收标准

```text
1. 面试官问 RAG，能展示检索、重排、证据、评估；
2. 面试官问 Agent 记忆，能展示 Transcript、Replay、ProjectMemory；
3. 面试官问工具调用，能展示 isToolAllowed、MCP tools、Trace；
4. 面试官问多 Agent，能展示可扩展架构与为什么当前不拆；
5. 面试官问测试，能展示 S17/S31 baseline、pytest、Playwright；
6. 面试官问风险，能展示 Candidate != Evidence、Readiness hard block；
7. 面试官问简历，能用 2 分钟讲清项目价值和技术难点。
```


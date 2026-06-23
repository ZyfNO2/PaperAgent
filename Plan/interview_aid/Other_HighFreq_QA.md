# 其它高频问题速答（面经其它/补充主题）

> 日期：2026-06-23
> 性质：口语速答，补充主题：面经里被归为「其它」（不在 RAG/多 Agent/量化/记忆/幻觉/MCP/模型/微调八大主题里）的高频问题。这些题小红书等场明确列出但深度常被忽略。
> 用法：每题给标准答 + 项目挂钩。别空着不答。

---

## 1. Python 异步方法是如何实现的？/ 异步如何通知事件完成？

### 标准答
Python 异步基于 `asyncio` 事件循环 + `coroutine`（用 `async def` 定义的函数，返回的是协程对象，不直接执行）。`await` 把控制权交回事件循环，等 `Future` 完成再恢复。事件循环单线程轮询 I/O 就绪状态，避免线程切换开销。
通知完成有两条路：
- `Future`/`Task` 设 `result` 或 `exception` →唤醒所有 `await` 它的协程。
- 回调式：`future.add_done_callback(fn)`，完成时回调；或 `asyncio.Event.set()` 唤醒所有 `event.wait()` 的协程。

### 项目挂钩
PaperAgent 的流式（Step Deck + RunEvent token_delta/card_delta）本质是异步推送：后端生成 →前端 SSE/WebSocket 流式接收 →事件完成时发收尾事件。这是「异步 + 完成通知」的真实落地。

### 追问可能问
- 「async/await 和多线程区别？」：单线程协作式 vs 多线程抢占；I/O 密集用 async，CPU 密集用多进程（GIL）。「asyncio.gather 并发」：多协程并发跑，等齐完成。

## 2. 常见 AI coding 工具对比（2026）

| 工具 | 定位 | 长处 | 适合 |
|---|---|---|---|
| **Cursor** | AI IDE，本地文件上下文 | Composer 多文件、多文件理解、Agent 模式 | 个人开发全能 |
| **Claude Code** | 终端 CLI Agent + Harness | 长任务自治、Skill / 如现成、权限系统严谨、MCP 深度集成 | 工程化长流程、论文与 commit |
| **GitHub Copilot** | IDE 全 / Chat | 官方集成、补全强、行内快 | 工程师日常补全 |
| **Codeium / Windsurf** | IDE 全 + Cascade agent | 免费 / 低价、企业部署 | 团队企业 |

### 讲法（被问「你熟悉哪些 AI coding 工具」）:
> 我以 Claude Code 为主——它把 Agent、Harness、Skill、权限编排到一起，工程纪律强。PaperAgent 工作台借鉴了它的 WorkspaceCommand 先预览再确认、Trace 可回放、readiness hard block 这些设计点。日常补全也用 Cursor/Copilot。我选逻辑是：长流程垂直度用 Claude Code，散代码改用 Cursor，行内补全用 Copilot。

## 3. 提示词工程技巧（2026 简）

- **Zero/Few-shot**：给 0/几个示例再问。Few-shot 要「同分布、逆序偏置」。
- **Chain-of-Thought (CoT)**：让模型逐步推理。CoT 比直接答在多步任务上稳。
- **ReAct**：Reason + Act，Thought→Action→Observation→Thought 循环，工具调用的标准范式。
- **Structured Output**：JSON schema 约束输出（OpenAI/Anthropic 都原生支持），降低解析失败率。
- **Self-consistency**：采多样本多数投票，提精度。
- **工具调用 / Function Calling**：结构化描述工具，模型选调。

### 项目挂钩
PaperAgent PromptProtocol 是这三条的现实落地：action whitelist + forbidden pattern + WorkspaceCommand 预览。这不是「为了让模型聪明」，是「把模型输出约束成可审计动作」。讲法要区别。

## 4. A2A（Agent2Agent）协议介绍

### 是什么（2026 点）
Google 提出的开放协议，让不同 Agent 互相发现、协商、委派任务。对标 MCP（MCP 是「Agent ↔ 工具」，A2A 是「Agent ↔ Agent」）。

### 条件组成（够讲）
- Agent Card：`/.well-known/agent.json` 描述能力。
- Tasks：长期任务对象，跨同步/异步。
- Messaging：Agent 之间结构化消息（JSON-RPC 2.0 over HTTP/SSE）。

### 项目挂钩
PaperAgent 当前没接 A2A（诚实说）。讲法是「MCP 是我和工具之间的接口，A2A 是 Agent 之间，我当前主链路单 Agent + Gate 暂不需要；多 Agent 演进时会评估 A2A 作为 Agent 间标准协议（design-only）」。

## 5. 你在项目中遇到的最难的问题是什么？怎么解决？（项目深挖套话）

### 套话框架（STAR 变体）
1. 场景：什么场景、什么约束。
2. 任务：要解决什么。
3. 行动：你做了什么决策、为什么这个取舍。
4. 结果：量化结果 + 怎么复盘。

### PaperAgent 可用的「最难」候选（选最贴你面的那条）
- **候选 A（证据治理）**：「最难的是 Candidate → Evidence 的边界——模型天生想直接 evidence。我解决是软删除留 Trace + URL Verified + readiness hard block，LLM 只给建议。结果是 evidence 可回放、不误晋升。」
- **候选 B（状态一致性）**：「最难是用户改前序步骤后，后续变 stale 的一致性管理。我解决是状态依赖图 + stale 传播 + 导出前 readiness 检查。结果是改了不会出脏报告。」
- **候选 C（流式可审计）**：「最难是让流式不只是好看而是可审计——我解决是 RunEventStore + token_delta/card_delta + replay。结果能回放整次决策。」

挑一个深讲，别三个都浅说。

## 6. Agent 评估指标（面经常问）

- **任务完成率**：端到端是否达成目标。
- **工具调用准确率**：选对具 / 参数 / 时机的比例。
- **效率**：均步数 / 均 token / 均时延。
- **安全性**：越权 / 泄露 / 异常调用次数。
- **回放一致性**：同输入多次跑是否一致（可复现）。

### 项目挂钩
PaperAgent Session 17 baseline + Readiness 指标 + Evidence Precision / Citation Coverage（对应 RAG 升设计 §4）。「我把 RAG 评估拆成 Recall@K / MRR / Citation Coverage / Evidence Precision 四个，对标 Ragas faithfulness 但自建不引重依赖。」

---

## 7. 诚实提醒

这些题答案别背成八股——面试官随口追一句就露。每题把「项目挂钩」对上真实代码/文档，讲出来才硬。
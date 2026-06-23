# Deep Dive Q&A — Agent 架构（Session 38 补充）

> 面试时被连续追问 Agent 细节时，怎么稳定输出？
>
> **当前不足**：本文档基于 Mock 数据，未接入真实 LLM；Multi-Agent 仅做设计，未真正实现。

---

## Q1: 什么是 Agent？你的项目用了什么 Agent 模式？

**短答：** Agent = LLM + 工具 + 状态机。PaperAgent 用单流程 + Gate 决策，**不盲目拆多 Agent**。

**深答：**
- 单 Agent：1 个 LLM 循环调用工具
- Multi-Agent：多个 LLM 协调（Supervisor / Worker）
- PaperAgent：**单流程**（keyword → retrieve → verify → feasibility → proposal），强顺序、Gate 强约束

**项目证据：**
- `docs/interview/MultiAgent_Expansion_Design.md`

---

## Q2: 为什么不用多 Agent？

| 拆多 Agent 的成本 | 单流程的优势 |
|---|---|
| 7+ LLM 调用（贵 5-10x） | 1-2 个 LLM 调用 |
| 路由错误传播 | 单一线性流程 |
| 证据一致性难保证 | Gate 强约束 |
| 调试难 | Trace 一目了然 |

**关键论点：** 选题流程**强顺序**，拆分后子 Agent 之间还是串行依赖，省不了 LLM 调用。

---

## Q3: 什么时候会拆？

3 个触发条件：
1. 检索源 ≥ 5 个（并行收益 > 成本）
2. 评分模型 ≥ 3 个（投票有意义）
3. 模板类型 ≥ 5 个（路由分支多）

---

## Q4: 你的 Agent 状态机是什么样的？

**8 个 Step Deck：**
1. raw_intake (D 评级拦截)
2. keyword_review (Gate 1)
3. query_plan (Gate 2)
4. retrieval (SOP 三线)
5. candidate_scoring
6. feasibility (Gate 3)
7. evidence_promotion
8. proposal_draft

每个 step 是 `Step Deck` 状态，由前端追踪。

---

## Q5: 怎么处理工具调用失败？

**3 层降级：**
1. **工具级降级** — heuristic fallback
2. **状态级降级** — 回到上一个 step
3. **流程级降级** — 重置项目

**关键：** 失败不静默，每次失败都写 Trace。

---

## Q6: Agent 的状态存在哪？

**4 层 Agent Memory：**
1. **ShortContext** — 浏览器 step deck 运行时
2. **Transcript** — RunEvent JSONL，可 replay
3. **ProjectMemory** — 项目级摘要
4. **EvidenceMemory** — 不可变证据

---

## Q7: 怎么防止 Agent 走偏？

**关键设计：**
- Gate 校验（D 评级拒入、keyword gate、未晋升拒晋升）
- max_llm_calls 限制
- Read-only agents（不能直接写 evidence）
- 失败降级

**项目证据：**
- `apps/api/app/services/agent_router.py` — 7 roles, 4-dim cost budget

---

## Q8: Agent 怎么和 LLM 通信？

**接口：**
- `llm_call(step_key, prompt, **kwargs)` 统一入口
- JSON 模式输出
- Heuristic fallback（LLM 挂掉用规则）

**为什么 JSON 模式？**
- 解析稳定
- 可校验
- 可测试

---

## Q9: 你怎么评估 Agent 表现？

**指标：**
- **Trace 完整性** — 每个 step 都有 event
- **Gate 拦截率** — 多少 D 评级被拦住
- **LLM 调用次数** — 成本
- **成功完成率** — end-to-end success
- **用户 patch 次数** — 多少需要人工修

---

## Q10: Agent 和 LLM 有什么区别？

| 维度 | LLM | Agent |
|---|---|---|
| 输入 | 单次 prompt | 状态 + 工具 + prompt |
| 输出 | 文本 | 动作 + 文本 |
| 状态 | 无 | 有（memory + step deck） |
| 工具 | 无 | 有 |
| 决策 | 模型自己 | 工具 + 模型 + 规则 |

**PaperAgent 把 Agent 当成"状态机 + 工具 + LLM"，而不是"无脑 LLM 调用"。**

---

## Q11: 多 Agent 路由错了怎么办？

**3 道防线：**
1. 静态路由表 + 置信度阈值（< 阈值回退 Supervisor）
2. Gate 二次校验
3. 投票共识（多 agent 复核）

---

## Q12: Supervisor 会不会成瓶颈？

**会，所以严格限制：**
- 不直接生成证据
- 不调 LLM（除路由外）
- 不修改状态
- 只做流程控制 + 调度 + 降级

**缓解：** 子 agent 之间通过消息总线通信，不经过 Supervisor。

---

## Q13: Agent 怎么审计？

**Trace 自动写：**
- `mcp_tool_call` 记录所有 MCP 调用
- `user_patch` 记录用户修正
- `gate` 记录所有 Gate 决策
- `evidence_promotion` 记录证据晋升
- `llm_call` 记录 LLM 调用

**审计面板：** 任何 step 都能回放。

---

## Q14: Agent 成本怎么控制？

**4 维硬限制：**
- max_agent_count = 8
- max_llm_calls = 20
- max_parallel_tasks = 3
- max_rounds = 5

**2 个降级开关：**
- fallback_to_single_agent
- early_stop_on_gate_blocked

---

## Q15: 你怎么和 LangGraph 区别？

| 维度 | LangGraph | PaperAgent Agent |
|---|---|---|
| 状态管理 | 框架托管 | 自己设计 4 层 |
| 成本控制 | 框架无 | 4 维硬限制 |
| Gate | 需手写 | 内置 |
| 审计 | 需手写 | Trace 自动 |
| 失败降级 | 需手写 | 内置 should_fallback |

---

## Q16: Agent 怎么和 RAG 协作？

**PaperAgent 模型：**
1. RAG 检索出候选 → Agent 看到候选列表
2. Agent 用 LLM 评分
3. Agent 决定晋升 Evidence
4. Evidence 进 Agent 状态

**RAG 是工具，Agent 是协调者。**

---

## Q17: Agent 怎么和 MCP 协作？

**3 个 MCP 工具由 Agent 调用：**
- search_topic_evidence
- get_candidate_resources
- get_project_trace
- check_export_readiness

**关键：** Agent 调 MCP 走 Gate + Trace，**不能绕过**。

---

## Q18: 你的 Agent 怎么扩展？

**渐进路径：**
1. 阶段 1：单流程 + Gate（当前）
2. 阶段 2：Retrieval + Verification 拆并行
3. 阶段 3：完整 Supervisor + 6 子 Agent

**已就位：** 7 roles + 静态路由 + 成本预算 + 投票 + 降级。

---

## Q19: 怎么避免 LLM 编造？

**3 层防护：**
1. **RAG 约束** — 候选列表限定
2. **Gate 校验** — URL 必须 verified
3. **Trace 审计** — 任何生成都有据可查

---

## Q20: Agent 怎么和人类协作？

**Patch 机制：**
- 用户可对任何 step 改结果
- 改完写 `user_patch` 事件
- Agent 不自动覆盖用户决策

**关键：** Agent 是助手，决策权在人。

---

> **面试重点：** PaperAgent Agent 的核心是**「状态机 + 工具 + LLM」**，不是「LLM 随便调」。每一步都有 Gate 校验 + Trace 审计 + 失败降级。Multi-Agent 路径已就位但不强拆。

---

## Q21: 多 Agent 之间怎么通信？(ACP)

**PaperAgent 的设计：**

当前主线不走多 Agent 通信。但如果需要，设计层已定义 ACP 协议：

- Agent A 发 `ACPMessage` 给 Agent B
- 类型包括 `task_request`, `evidence_candidate`, `verification_report` 等
- 写操作强制 `requires_human_gate = true`
- 所有通信写入 Trace，可审计

**关键约束：**

```
Main Agent ──→ Retrieval Agent (读)
Main Agent ──→ Verifier Agent (读)
Main Agent ──→ Evidence 写入 (强制 Gate)
                                └── 不经过 ACP，直接走 Human Gate
```

**面试表达：**

> 多 Agent 通信我用 ACP 的消息模型约束——每条消息知道谁发的、谁收的、什么类型、能不能绕过用户确认。但这不是当前 runtime，是通信治理层的设计。详见 `Plan/design/ACP_Interop_And_Agent_Communication.md`。

## Q22: 当前 Single-Agent 到 Multi-Agent 的演进路径？

**PaperAgent 的渐进路径：**

1. **阶段 1（当前）**：Single-Agent + Gate → 顺序执行 + 用户确认
2. **阶段 2（lightweight）**：将检索和验证拆为并行子 Agent → 通过 ACP task_request 通信
3. **阶段 3（design-only）**：完整 Supervisor + 6 子 Agent → Supervisor 通过 ACP 消息总线调度

**为什么阶段 1 就够了？**

选题流程是强顺序的——你不可能在还没确定选题时就开始写报告。强顺序意味着子 Agent 之间大部分是串行依赖，拆多 Agent 收益有限。我选择把 Gate 和 Trace 做扎实，而不是为了面试拆出 5 个没什么实际并行度的子 Agent。

**阶段 2 的触发条件：**
- 检索源 ≥ 5 个
- 评分模型 ≥ 3 个
- 模板类型 ≥ 5 个

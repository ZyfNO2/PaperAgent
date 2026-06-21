# Multi-Agent 扩展设计面试讲解（Session 37）

> PaperAgent 当前**单流程**为主，但设计了清晰的**多 Agent 扩展路径**。
> 本文档解释「为什么现在不拆」+「未来怎么拆」+「成本怎么控」+「路由错了怎么办」。

---

## 1. 一句话定位

PaperAgent 当前用单流程 + Gate 决策，因为选题流程强顺序、证据规则要求一致性。**Multi-Agent 扩展设计已就位**：定义 7 个 Agent Role、静态路由表、成本预算、投票共识、降级回退。需要并行时，渐进切到 Supervisor + 子 Agent 模式，不需要重写核心。

---

## 2. 为什么现在不拆？

| 拆多 Agent 的成本 | 单流程的优势 |
|---|---|
| 7+ 个 LLM 调用（贵 5-10x） | 1-2 个 LLM 调用 |
| 路由错误传播 | 单一线性流程 |
| 调试难（哪个 agent 错了？） | Trace 一目了然 |
| 证据一致性难保证 | Gate 强约束 |
| Supervisor 容易成瓶颈 | 没有 Supervisor |

**关键论点：** 选题流程**强顺序**（keyword → retrieve → verify → feasibility → proposal），拆分后子 Agent 之间还是串行依赖，省不了 LLM 调用。

---

## 3. 什么时候拆？

```
强顺序任务（keyword→retrieve→verify）         → 单流程
                                          ↓
并行候选任务（多源检索、多模型评分）         → Multi-Agent
                                          ↓
低成本投票任务（复核、草稿评估）             → Multi-Agent + 投票
                                          ↓
复杂分支决策（不同学校模板）                 → Multi-Agent + 路由
```

**渐进路径：**

1. **阶段 1（当前）**：单流程 + Gate
2. **阶段 2（近）**：Retrieval + Verification 拆成多 Agent 并行
3. **阶段 3（远）**：完整 Supervisor + 6 子 Agent

---

## 4. 7 个 Agent 角色

| Role | 职责 | 可写 Evidence | 成本权重 |
|---|---|---|---|
| **SupervisorAgent** | 流程控制 | ❌ | 1 |
| **KeywordAgent** | 题目拆解 | ❌ | 2 |
| **RetrievalAgent** | 候选资源检索 | ❌ | 3 |
| **VerificationAgent** | URL 验证 + 晋升前检查 | ❌ | 2 |
| **FeasibilityAgent** | 风险裁决 | ❌ | 2 |
| **ProposalAgent** | 报告草稿 | ❌ | 3 |
| **ReviewAgent** | 委员会复核 | ❌ | 2 |

**关键不变量：** **所有 Agent 都不能直接写 evidence / modify supports**。这是和 LangChain Agents / AutoGPT 的根本差异 —— 状态变更必须经 Gate。

---

## 5. 路由表

静态路由：`task_type` → 首选 agent：

```python
TASK_TYPE_TO_ROLE = {
    "keyword_decompose": ("keyword", 0.7),
    "candidate_retrieve": ("retrieval", 0.7),
    "url_verify": ("verification", 0.8),
    "feasibility_decide": ("feasibility", 0.7),
    "proposal_draft": ("proposal", 0.7),
    "review_check": ("review", 0.6),
    "trace_query": ("supervisor", 0.5),
    "memory_replay": ("supervisor", 0.5),
}
```

**为什么静态表而不是 LLM 路由？**

- 节省 1 个 LLM 调用
- 可测试、可审计
- 路由决策本身有 Trace

---

## 6. 成本控制

```python
class CostBudget(BaseModel):
    max_agent_count: int = 8         # 最多 8 个 agent 实例
    max_llm_calls: int = 20          # 最多 20 次 LLM 调用
    max_parallel_tasks: int = 3      # 最多 3 个并行
    max_rounds: int = 5              # 最多 5 轮迭代
    fallback_to_single_agent: bool = True
    early_stop_on_gate_blocked: bool = True
```

**4 个硬限制 + 2 个降级开关：**

- 超 `max_llm_calls` → 停止
- 超 `max_rounds` → 停止
- 超 `max_parallel_tasks` → 排队
- Gate 阻塞 + `early_stop_on_gate_blocked` → 立即回退
- 成本超限 + `fallback_to_single_agent` → 回退到单流程

---

## 7. 投票共识

多个 agent 给出 decision：`approve` / `reject` / `warn`

**规则：** 简单多数（approve > reject 且 approve > warn）

```python
def tally_votes(task_type, votes):
    dist = {v.decision: count(v.decision for v in votes)}
    if approve > reject and approve > warn:
        final = "approve"
    elif reject > approve:
        final = "reject"
    else:
        final = "warn"
```

**投票只用于低成本判断**（复核 / 草稿评估），不用于高风险动作（晋升证据、删除项目）。

---

## 8. 失败降级

3 层降级：

```
1. 路由置信度低 → 回退 SupervisorAgent
2. 成本超限 → fallback_to_single_agent = True 时回退单流程
3. Gate 阻塞 → early_stop_on_gate_blocked = True 时立即停止
```

**关键设计：** 降级**有 Trace 记录**，不静默。

---

## 9. 路由错误处理

| 情况 | 应对 |
|---|---|
| 路由置信度低 | 回到 Supervisor 重路由 |
| 高风险 action | 必须过 Gate，不能直接调 |
| 两个 Agent 冲突 | 以 EvidenceRef / Readiness 为准 |
| 投票成本太高 | 只对低成本任务投票 |
| Agent 想直接写 supports | **硬禁止**（schema 限制） |

---

## 10. Supervisor 会不会成瓶颈？

**会，所以严格限制 Supervisor 的职责：**

- ❌ 不直接生成证据
- ❌ 不直接调 LLM（除路由外）
- ❌ 不修改状态
- ✅ 只做：流程控制、子 agent 调度、降级决策

**缓解策略：**

- Supervisor 的 LLM 调用尽量少（路由用静态表）
- 子 agent 之间可以直接通信（消息总线），不经过 Supervisor
- 长时间运行的 plan 拆成多 Supervisor

---

## 11. 面试常见追问

### Q1: 为什么不用多 Agent？

> 「当前选题流程是强顺序（keyword → retrieve → verify → feasibility → proposal），拆多 Agent 子 Agent 之间还是串行依赖，省不了 LLM 调用。当并行候选、低成本投票任务增多时，再渐进拆。」

### Q2: 如果子 Agent 膨胀到 20 个怎么办？

3 个硬约束：
- `max_agent_count = 8` 防止 agent 数量爆炸
- `max_rounds = 5` 防止无限循环
- `max_llm_calls = 20` 控制成本

超限立即停止 + 回退单流程。

### Q3: Supervisor 会不会成瓶颈？

Supervisor 严格不调 LLM（除路由），不做状态变更，只做调度。子 agent 之间通过消息总线通信。长时间 plan 拆成多 Supervisor。

### Q4: 分类路由错了怎么办？

3 道防线：
1. 静态路由表 + 置信度阈值（< 阈值回退 Supervisor）
2. Gate 二次校验（高风险 action 必须过 Gate）
3. 投票共识（多 agent 复核）

### Q5: 多 Agent 成本怎么控制？

- 4 维硬限制（agent_count / llm_calls / parallel / rounds）
- 2 个降级开关（fallback_to_single / early_stop_on_gate）
- 静态路由表节省 1 个 LLM 调用
- 投票只用于低成本任务

### Q6: 你的 Multi-Agent 和 LangGraph / AutoGen 有什么差异？

| 维度 | LangGraph / AutoGen | PaperAgent Multi-Agent |
|---|---|---|
| 状态变更 | 灵活 | **必须经 Gate** |
| 成本控制 | 框架无 | 4 维硬限制 |
| 路由 | LLM 路由（贵） | 静态表（快） |
| 投票 | 需手写 | 内置 `tally_votes` |
| 失败降级 | 需手写 | 内置 `should_fallback` |
| 调试 | Trace 弱 | 强 Trace 集成 |

### Q7: 证据一致性怎么保证？

- 所有 Agent **不能直接写 evidence**（schema 限制）
- 状态变更必须经 Gate
- 多 agent 冲突时以 EvidenceRef / Readiness 为准
- Review Agent 做最终复核

### Q8: 什么时候会真正落地多 Agent？

- 检索源 ≥ 5 个（并行检索收益 > 成本）
- 评分模型 ≥ 3 个（投票有意义）
- 模板类型 ≥ 5 个（路由分支多）

---

## 12. 设计产物

- `apps/api/app/schemas_agent_plan.py` — AgentRole / RouteDecision / CostBudget / AgentVote / AgentPlan
- `apps/api/app/services/agent_router.py` — 静态路由 + 成本检查 + 投票 + 降级
- `apps/api/tests/test_session37_multi_agent_design.py` — 28 个后端测试
- `apps/web/e2e/test_one_topic_session37_multi_agent.py` — 5 个 Playwright 测试
- `docs/interview/MultiAgent_Expansion_Design.md` — 本文档

---

## 13. 未来扩展

- 动态路由（LLM 路由表更新）
- 跨 session 共享 agent 状态
- Agent 评估面板（每个 agent 的成功率、成本、延迟）
- 自动降级阈值（基于历史数据）
- 子 agent 通信消息总线
- 异步 agent（长时间任务后台跑）

---

> **面试重点强调：** PaperAgent 的 Multi-Agent 设计是**渐进可扩展**的，不是「为了拆而拆」。当前单流程是合理的工程选择，多 Agent 路径已就位、成本控制可测、失败降级有 Trace。
# PaperAgent Session 37 SOP：Multi-Agent 可扩展设计与成本控制

> 日期：2026-06-21  
> 前置：S33-S36 已有项目叙事、RAG、Memory、MCP。  
> 本轮目标：不盲目重构为多 Agent，而是补一套可讲、可测、可渐进落地的 Multi-Agent 扩展设计。

---

## 1. 面试解释

### 面试官可能会问

```text
为什么不用多 Agent？
如果子 Agent 膨胀到 20 个怎么办？
Supervisor 会不会成为瓶颈？
分类路由错了怎么办？
多 Agent 成本怎么控制？
```

### 为什么需要这么改

公司面经中多 Agent 架构是高频深挖点，尤其会追问 Supervisor 压力、路由错误、并行投票和成本。PaperAgent 当前单流程更稳，但必须能说明未来怎么扩展，为什么现在不拆。

### PaperAgent 的回答

```text
当前 PaperAgent 使用单流程 + Gate，是因为选题流程强顺序、证据规则要求一致性。
当检索、验证、复核任务并行增多时，再拆成 Supervisor + RetrievalAgent + VerificationAgent + ReviewAgent。
扩展时使用层级路由、并行候选、少量投票、成本预算和失败降级。
```

---

## 2. 设计产物

```text
docs/interview/MultiAgent_Expansion_Design.md
apps/api/app/schemas_agent_plan.py
apps/api/app/services/agent_router.py
apps/api/tests/test_session37_multi_agent_design.py
```

---

## 3. Agent 角色

```text
SupervisorAgent：流程控制，不直接生成证据；
KeywordAgent：题目拆解；
RetrievalAgent：候选资源检索；
VerificationAgent：URLVerified / Evidence 晋升前检查；
FeasibilityAgent：风险裁决；
ProposalAgent：报告草稿；
ReviewAgent：委员会复核。
```

---

## 4. 成本控制

```text
max_agent_count；
max_llm_calls；
max_parallel_tasks；
max_rounds；
fallback_to_single_agent；
early_stop_on_gate_blocked。
```

---

## 5. 路由错误处理

```text
1. 路由置信度低时回到 Supervisor；
2. 高风险 action 需要 Gate；
3. 两个 Agent 冲突时以 EvidenceRef / Readiness 为准；
4. 投票只用于低成本判断；
5. 不让 Agent 直接写 supports。
```

---

## 6. 测试

```text
1. agent role schema 可序列化；
2. route_task 能把 retrieval 分给 RetrievalAgent；
3. 低置信路由返回 Supervisor；
4. max_llm_calls 超限时停止；
5. VerificationAgent 不能直接生成 supports；
6. fallback_to_single_agent 可用；
7. MultiAgent 解释文档存在；
8. 当前单流程不回退。
```

---

## 7. 验收标准

```text
1. 可扩展设计文档完成；
2. 最小 router schema 可测；
3. 成本控制可测；
4. 路由错误处理可解释；
5. 不引入复杂重构；
6. 完工报告包含“面试解释”。
```

---

## 8. 完工报告

```text
Plan/reports/Session_37_MultiAgent_Expansion_CostControl_验收报告.md
```


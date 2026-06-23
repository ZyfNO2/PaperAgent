# PaperAgent Session 35 SOP：Agent Memory / Transcript / Replay 强化

> 日期：2026-06-21  
> 前置：S27 已规划真实 RunEvent，S31 已有全链路 baseline。  
> 本轮目标：把 RunEvent / Trace / Project State 整理成面试可讲的 Agent 记忆系统，对齐 ClaudeCode 记忆资料中的 Transcript、压缩、恢复。

---

## 1. 面试解释

### 面试官可能会问

```text
你的 Agent 记忆怎么做？
上下文超过限制怎么办？
刷新页面或断流后怎么恢复？
你怎么区分短期记忆和长期记忆？
压缩会不会丢关键信息？
```

### 为什么需要这么改

你给的 ClaudeCode 资料强调，近期 Agent 面试会深挖记忆、Transcript、压缩和会话恢复。PaperAgent 已经有 Trace、RunEvent、reports，但需要把这些概念统一成一个清楚的记忆架构。

### PaperAgent 的回答

```text
PaperAgent 使用四层记忆：
1. ShortContext：当前 Step Deck 的 runState；
2. Transcript：RunEvent JSONL，记录每一步事件；
3. ProjectMemory：项目级摘要，记录题目、关键词、候选、证据、报告状态；
4. EvidenceMemory：已确认 EvidenceRef 和 URLVerified 结果。
```

---

## 2. 新增文档与代码

```text
docs/interview/Agent_Memory_Explainer.md
apps/api/app/schemas_memory.py
apps/api/app/services/project_memory.py
apps/api/app/services/transcript_replay.py
apps/api/tests/test_session35_agent_memory_replay.py
apps/web/e2e/test_one_topic_session35_memory_replay.py
```

---

## 3. 记忆层级

```text
ShortContext
  当前浏览器状态，刷新可能丢失

Transcript
  RunEvent JSONL，可 replay

ProjectMemory
  项目摘要，跨 session 保留

EvidenceMemory
  EvidenceRef、URLVerified、PromotionResult，最高可信
```

---

## 4. 压缩策略

```text
当 RunEvent 超过阈值：
1. 保留 gate / user_patch / evidence_promotion / readiness 等关键事件；
2. token_delta 合并成摘要；
3. card_delta 保留最终状态；
4. 生成 ProjectMemorySnapshot；
5. replay 时先加载 snapshot，再加载后续 events。
```

---

## 5. 测试

后端：

```text
1. Transcript 可写入；
2. Replay 后 Step 状态一致；
3. token_delta 可压缩；
4. gate 事件不会被压缩丢失；
5. EvidenceMemory 不被普通压缩覆盖；
6. ProjectMemorySnapshot 可序列化；
7. 压缩前后 readiness 结果一致；
8. S31 baseline 不回退。
```

Playwright：

```text
S35-PW-1：运行到候选页后刷新可恢复；
S35-PW-2：Trace 面板显示 replay 来源；
S35-PW-3：压缩后关键词 Gate 仍可追溯；
S35-PW-4：EvidenceRef 仍可追溯 Candidate；
S35-PW-5：断流后显示恢复按钮；
S35-PW-6：Agent_Memory_Explainer 文档存在。
```

---

## 6. 验收标准

```text
1. 四层记忆概念落地；
2. Transcript replay 可用；
3. 压缩策略不丢关键 gate；
4. 面试解释文档完整；
5. 后端测试通过；
6. Playwright 通过；
7. 完工报告包含“面试解释”。
```

---

## 7. 完工报告

```text
Plan/reports/Session_35_AgentMemory_TranscriptReplay_验收报告.md
```


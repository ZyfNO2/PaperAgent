# PaperAgent 面试导向改造执行规范

> 日期：2026-06-21  
> 作用：约束 Session 34 之后的所有改造。后续每次实现功能时，都必须同时补“面试解释”，说明为什么这样改、面试官会追问什么、项目如何回答。

---

## 1. 总原则

PaperAgent 后续不再只按“功能完成”推进，而要按“功能 + 面试解释 + 可演示证据”推进。

每个 Session 都必须回答：

```text
1. 这次改造对应哪类面试问题？
2. 为什么当前项目需要这个能力？
3. 它借鉴了用户提供资料中的哪个观点？
4. 面试官追问时怎么解释？
5. 代码和测试中哪里能证明？
6. 这个改造没有做什么，边界是什么？
```

---

## 2. 本地资料映射

| 本地资料 | 后续改造重点 |
|---|---|
| `01-公司面经` | 项目深挖、Agent 架构、RAG、MCP、工具调用失败、多 Agent 成本 |
| `02-Agent_RAG项目实战` | Hybrid Search、Rerank、RAG Evaluation、MCP Server、可插拔架构 |
| `03-ClaudeCode_OpenClaw_Harness技术` | 记忆、Transcript、压缩、恢复、权限、安全、SubAgent |
| `04-大模型自学与面试方法` | 简历包装、项目叙事、自我介绍、面试问答、工程亮点 |

---

## 3. 每次改造必须新增的面试说明

每个 Session 的完工报告必须增加一节：

```text
## 面试解释

### 面试官可能会问
- ...

### 为什么要这么设计
- ...

### PaperAgent 的回答
- ...

### 项目证据
- 文件：
- 测试：
- Demo：

### 边界
- ...
```

如果没有这一节，该 Session 不建议验收通过。

---

## 4. 代码改造的面试约束

```text
1. RAG 改造必须能讲清召回、重排、评估；
2. Agent 改造必须能讲清状态、记忆、工具、权限；
3. UI 改造必须能讲清为什么降低认知负担；
4. 证据改造必须继续保持 Candidate != Evidence；
5. 工具调用改造必须有 isToolAllowed / Trace；
6. 多 Agent 改造必须说明为什么不是过度设计；
7. 测试必须覆盖 happy path 和 blocked path；
8. 任何失败案例都不能被粉饰，要能成为面试亮点。
```

---

## 5. 后续 Session 顺序

```text
Session 34：RAG 面试级检索评估与 Hybrid/Rerank 设计
Session 35：Agent Memory / Transcript / Replay 强化
Session 36：MCP Server 最小工具暴露与权限边界
Session 37：Multi-Agent 可扩展设计与成本控制
Session 38：面试问答卡片与 Demo 脚本系统化
Session 39：失败案例库与反问追问准备
Session 40：简历项目包装与技术亮点收束
```

执行建议：

```text
S34-S36 是技术硬实力；
S37 是架构设计讨论能力；
S38-S40 是面试表达和作品收束。
```


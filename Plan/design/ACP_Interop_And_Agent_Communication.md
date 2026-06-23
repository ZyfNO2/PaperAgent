# ACP 互操作与 Agent 通信治理设计

> 日期：2026-06-23
> 定位：design-only — 不接 runtime，不参与当前主链路执行
> 对应 Session：44（ACP 协议互操作与 Agent 通信治理）

---

## 1. ACP 口径约定

PaperAgent 统一口径：

```text
默认 ACP = Agent Communication Protocol
补充 ACP-Control = Agent Control / Admission Control 设计参考
```

| 术语 | 含义 | PaperAgent 状态 |
|------|------|----------------|
| **MCP** | Agent-to-Tool 工具调用协议 | S36 最小工具暴露，可展示 |
| **A2A** | Agent-to-Agent 任务委派 + 能力发现 | design-only |
| **ACP** | Agent-to-Agent Messaging + 异步流 + 多模态内容 | design-only |
| **ACP-Control** | 行为准入 + 能力授权 + 不可抵赖审计 | design-only |

**为什么 ACP 当前是 design-only？**

PaperAgent 主线是 Single-Agent + Gate + Trace，多 Agent 协作还不是真实瓶颈。当前顺序强、Gate 强的选题流程不需要 Agent 间消息总线。ACP runtime 会增加消息路由、鉴权、重试、序列化、版本兼容成本，在收益未验证前不适合引入。

---

## 2. MCP / A2A / ACP 边界

### 2.1 协议对比表

| 维度 | MCP | A2A | ACP | ACP-Control |
|------|-----|-----|-----|-------------|
| 解决什么 | Agent 调工具 | Agent 发现彼此、委派任务 | Agent 间消息、异步流、多模态交换 | 行为准入、能力授权、审计 |
| 通信方向 | Agent → 工具 | Agent ↔ Agent | Agent ↔ Agent (消息总线) | Agent → 控制层 |
| 消息模型 | JSON-RPC 请求/响应 | Task 对象 + 协商 | ACPMessage + Artifact | 策略检查 + 审计记录 |
| 状态 | 无状态 | 有状态（Task 生命周期） | 有状态（session/run） | 无状态（检查点） |
| 传输 | stdio/SSE/HTTP | HTTP/SSE | 消息队列 / HTTP / WS | HTTP 中间件 |
| PaperAgent 状态 | 可展示（S36） | design-only | design-only | design-only |

### 2.2 三层协议栈

```
┌──────────────────────────────────────────────────────────┐
│                   用户界面 / Step Workbench                │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│              Main Agent (单流程 + Gate)                    │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ MCP Client  │  │ A2A Client   │  │ ACP Client     │  │
│  │ (Agent→Tool)│  │ (design-only)│  │ (design-only)  │  │
│  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘  │
└─────────┼────────────────┼──────────────────┼────────────┘
          │                │                  │
┌─────────▼────┐  ┌───────▼────────┐  ┌──────▼─────────────┐
│ MCP Tools    │  │ A2A Agent      │  │ ACP Message Bus    │
│ (4 最小工具)  │  │ (设计预留)     │  │ (设计预留)          │
└──────────────┘  └────────────────┘  └─────┬──────────────┘
                                            │
                      ┌─────────────────────┼─────────────────────┐
                      │                     │                     │
               ┌──────▼──────┐     ┌────────▼──────┐    ┌────────▼──────┐
               │ Retrieval   │     │ Evidence     │    │ Review       │
               │ Agent       │     │ Verifier     │    │ Agent        │
               └─────────────┘     └───────────────┘    └───────────────┘
```

---

## 3. ACP 消息模型

### 3.1 ACPMessage

```text
ACPMessage
├─ message_id: string (UUID v4)
├─ session_id: string
├─ run_id: string
├─ from_agent: string
├─ to_agent: string | "*" (广播)
├─ message_type: MessageType (见 3.2)
├─ intent: string (描述这次通信的目的)
├─ payload: dict (类型特定的载荷)
├─ artifacts: Artifact[] (可选，见 3.3)
├─ trace_refs: string[] (关联的 Trace event ID 列表)
├─ requires_human_gate: boolean (跨 Agent 通信是否仍需要用户确认)
├─ created_at: datetime
├─ ttl_seconds: int (超时放弃)
└─ security: ACPSecurity
    ├─ signature: string (发送方签名)
    ├─ allowed_by_policy: boolean
    └─ reviewed_by_human: boolean
```

### 3.2 消息类型

| message_type | 用途 | 示例 |
|---|---|---|
| `task_request` | 请求另一个 Agent 执行任务 | "检索 bridge 数据集" |
| `task_status` | 返回任务状态 | running / blocked / completed / failed |
| `task_result` | 返回任务结果 | 检索结果列表 |
| `evidence_candidate` | 传递候选证据 | 论文摘要 + URL |
| `verification_report` | 传递验证结果 | URL 可用性 + 内容校验 |
| `proposal_patch` | 提交报告修改建议 | "§3.2 补充引用" |
| `workspace_command` | 对工作台元素提出增删改查建议 | 同 WorkspaceCommand |
| `human_gate_request` | 请求用户确认 | "是否采纳这条引用？" |
| `human_gate_result` | 用户确认 / 拒绝 / 修改 | gate_approved / gate_rejected / gate_patched |
| `trace_event` | 写入 Trace 的事件 | 子 Agent 的完整操作记录 |
| `error_event` | 子 Agent 失败、超时、权限拒绝 | error_code + error_detail |

### 3.3 Artifact 类型

| artifact_type | 示例 | 用途 |
|---|---|---|
| `paper` | 论文标题、摘要、URL、DOI、引用数 | 科研场景最常见 |
| `dataset` | 数据集名称、下载页、许可、样本规模 | 数据检索 |
| `repo` | GitHub 项目、stars、recent commit、license | 代码资源 |
| `webpage` | 普通网页、抓取摘要、可信度评分 | 资料验证 |
| `image` | base64 编码 / URL 引用、MIME type | 图表、截图 |
| `pdf_excerpt` | PDF 片段、页码范围、摘要 | 规范/论文片段 |
| `trace_slice` | 某一步 Trace 摘要、时间范围 | 跨 Agent 审计 |
| `proposal_section` | 开题报告某一节草稿 | 协作编辑 |

---

## 4. ACP 与现有能力映射

| PaperAgent 现有能力 | ACP 映射 | 当前状态 |
|---|---|---|
| Step Workbench | `task_request` + `task_status` | implemented → ACP 映射 design-only |
| WorkspaceCommand | `workspace_command` | implemented → ACP 映射 design-only |
| Human Gate | `human_gate_request` + `human_gate_result` | implemented → ACP 映射 design-only |
| EvidenceCard / 晋升 | `evidence_candidate` | lightweight → ACP 映射 design-only |
| URLVerified / 可用性 | `verification_report` | lightweight → ACP 映射 design-only |
| Trace | `trace_event` | implemented → ACP 映射 design-only |
| Report Draft | `proposal_patch` + `proposal_section` | lightweight → ACP 映射 design-only |
| SubAgent Router | `task_request` + `task_result` | design-only |

---

## 5. Human Gate 不可绕过原则

**最高优先级规则**：ACP 消息不能绕过 Human Gate。

```
Agent A ──task_request──→ Agent B
                              │
                    ┌─────────▼─────────┐
                    │ requires_human     │
                    │ _gate = true?      │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ 是 → 等待用户确认   │
                    │ 否 → 直通继续执行   │
                    └───────────────────┘
```

- 写证据、修改报告、删除数据的 ACP 消息强制 `requires_human_gate = true`
- 读操作（检索、查询状态）可以 `requires_human_gate = false`
- `security.reviewed_by_human` 必须在用户确认后才设为 `true`
- Trace 记录所有 Human Gate 事件，包括谁在什么时候确认了什么

---

## 6. Trace / Audit

所有 ACP 消息落地到 Trace：

```text
TraceEvent:
  event_type = "acp_message"
  target_id = message_id
  actor = f"{from_agent} → {to_agent}"
  payload = {
    "message_type": ...,
    "intent": ...,
    "requires_human_gate": ...,
    "gate_result": ... (human_gate_result 消息特有),
  }
  result = "ok" | "rejected" | "failed" | "timeout"
```

包括被拦截的消息（`allowed_by_policy = false`）也写入 Trace，用于安全审计。

---

## 7. 安全风险

| 风险 | 缓解措施 | 状态 |
|------|----------|------|
| Agent 绕过 Gate 直接写证据 | `requires_human_gate` 强制 | design-only |
| 消息伪造 / 身份冒充 | `security.signature` | design-only |
| 消息丢失 / 超时 | `ttl_seconds` + 重试 | design-only |
| 循环消息（A→B→A） | 检测 `trace_refs` 去重 | design-only |
| 子 Agent 泄露 Trace 数据 | `trace_refs` 访问控制 | design-only |
| 多 Agent 一致性问题 | 由 Main Agent 全权仲裁 | design-only |

---

## 8. 面试回答模板

### Q: MCP / A2A / ACP 有什么区别？

> 我把它们分成三层。MCP 是 Agent 调工具，比如读候选证据、读 Trace、检查导出 readiness；A2A 是 Agent 和 Agent 之间的任务委派和发现，比如把"检索数据集"委托给另一个 Agent；ACP 更偏通信层，关注多 Agent 之间怎么传消息、传状态、传多模态结果，以及异步流式返回。PaperAgent 当前主链路是 Single-Agent + Gate，所以 MCP 是最贴近当前实现的，A2A 和 ACP 暂时作为 design-only 扩展位，不默认启用。

### Q: PaperAgent 为什么当前只做 MCP，不接 ACP？

> 因为当前主链路的选题流程是顺序强、Gate 强的。一个 Agent 顺序执行 Step 1→5，每一步都有 Gate 确认，不需要 Agent 间消息总线。MCP 只需要做 Agent→Tool 的最小暴露就够了。接 ACP 意味着要管理多 Agent 的消息路由、鉴权、重试、序列化，在没有验证多 Agent 协作的收益之前，我觉得不应该为了面试把系统做重。

### Q: 如果要接 ACP，你会接在哪一层？

> 我会在 Main Agent 和子 Agent 之间加一层轻量 ACP Message Bus。Main Agent 通过 ACP 向 RetrievalAgent 发 `task_request`，RetrievalAgent 通过 `task_status` 报告进度，通过 `task_result` 返回结果，通过 `evidence_candidate` 传递候选证据。所有涉及写操作的 ACP 消息必须走 Human Gate。Trace 记录所有 ACP 通信。

### Q: ACP 消息怎么保证不会绕过 Human Gate？

> 每条 ACPMessage 有一个 `requires_human_gate` 字段。写证据、修改报告、删除数据强制设为 `true`。Gate 确认前 `security.reviewed_by_human` 为 `false`，下游 Agent 不会执行。Trace 记录所有 Gate 事件——谁、什么时间、确认了什么。

### Q: 多 Agent 通信怎么写 Trace？

> 每条 ACPMessage 生成一个 `acp_message` Trace 事件。发送、接收、Gate 确认、结果返回各一个事件，通过 `trace_refs` 串联。这样从 Main Agent 到子 Agent 的整条调用链可追溯。

### Q: ACP 和 WorkspaceCommand 有什么关系？

> WorkspaceCommand 是用户或 Agent 对工作台元素的修改建议，ACP 是 Agent 间通信协议。如果子 Agent 想修改工作台，它通过 ACP 发 `workspace_command` 类型的消息给 Main Agent，Main Agent 再通过现有的 WorkspaceCommand 机制生成预览让用户确认。ACP 不替代 WorkspaceCommand，而是作为它的传输层。

### Q: ACP-Control / admission control 和普通权限有什么区别？

> 普通权限检查是"能不能调这个接口"，ACP-Control 是"以什么能力、在什么条件下、做什么操作"。比如一个 Agent 可能有"检索"权限但没有"晋升证据"权限——这不是 API 级别的控制，而是 Agent 能力级别的控制。ACP-Control 检查 Agent 的身份声明、能力范围、操作意图，然后才决定是否放行。这在多 Agent 场景中比简单 RBAC 更细粒度。

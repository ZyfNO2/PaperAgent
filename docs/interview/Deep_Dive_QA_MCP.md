# Deep Dive Q&A — MCP / Tool 暴露（Session 38 补充）

> 面试时被连续追问 MCP 细节时，怎么稳定输出？
>
> **当前不足**：HTTP transport 而非 stdio/sse；没有 Rate Limiting；没有真实 MCP SDK 集成。
>
> **核心文件：** `apps/api/app/mcp/server.py`、`apps/api/app/mcp/tools.py`、`apps/api/app/mcp/permissions.py`、`apps/api/app/api/v1/mcp.py`、`docs/interview/MCP_FunctionCalling_Explainer.md`

---

## Q1: MCP 是什么？和 Function Calling 区别？

**短答：**
- **Function Calling**: 模型调用工具的格式（OpenAI / Anthropic）
- **MCP**: 工具、宿主、客户端之间的**标准协议**（JSON-RPC）

| 维度 | Function Calling | MCP |
|---|---|---|
| 协议层 | 模型 ↔ 工具 | 工具 ↔ 宿主 |
| 互操作 | 锁定单一厂商 | 跨模型、跨客户端 |
| 资源描述 | 简单 schema | tools/resources/prompts/sampling |
| 适用 | 单次 API 调用 | 长会话、IDE 集成 |

---

## Q2: 你的 MCP server 暴露了几个 tool？

**4 个最小 tool：**
- `search_topic_evidence` — 检索已批准 evidence
- `get_candidate_resources` — 列出候选资源
- `get_project_trace` — 读 trace（脱敏）
- `check_export_readiness` — 导出前检查

**为什么只 4 个？** SOP 明确：晋升证据、生成报告、删除项目、写文件**不暴露**。

---

## Q3: 哪些 tool 明确禁止暴露？

**6 个高风险 tool 永不被 MCP 调：**
- `promote_candidate_to_evidence`
- `generate_proposal_draft`
- `delete_project`
- `write_file`
- `shell_exec`
- `modify_evidence`

**理由：** 这些动作需要用户显式确认，不应该让外部 Agent 自动触发。

---

## Q4: 你的权限检查几层？

**3 层：**
1. **白名单** — 工具必须在 manifest
2. **黑名单** — 高风险永远拒
3. **Gate 前置** — keyword gate / FinalPackage 状态

```
tool_call(req)
   ↓
1. check_tool_allowed (manifest + forbidden)
   ↓
2. check_permission (keyword gate / FinalPackage)
   ↓
3. execute impl
   ↓
4. write Trace
   ↓
return response
```

---

## Q5: tool 调用失败怎么处理？

**业务错误用 `success=false` + `error.code` 表达，不抛 HTTPException。**

| Code | 含义 |
|---|---|
| `forbidden_tool` | 黑名单 / 不在 manifest |
| `permission_denied` | 前置条件不满足 |
| `missing_dependency` | 缺参数 |
| `internal_error` | 实现异常 |

**关键：** 业务失败和 transport 错误**分开**，客户端能区分。

---

## Q6: 怎么审计谁调了什么？

**所有调用通过 `append_trace(...)` 写 Trace：**
- `action="mcp_tool_call"`
- `target_id=tool_name`
- `actor=external_agent`
- `reason` 包含 ok/fail + 原因

**包括 forbidden 拒绝** —— 安全审计可追溯「谁尝试调 write_file」。

---

## Q7: Trace 数据怎么脱敏？

**`sanitize_trace_data` 递归脱敏绝对路径：**

```python
_ABS_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\|/)[^\s\"']{4,}"
)
def sanitize(data):
    # 替换为 <redacted-path>
```

**Windows + Unix 都覆盖**，递归处理 dict / list / str。

---

## Q8: 怎么防止 Agent 调危险工具？

**3 道闸门：**
1. **Manifest 白名单** — 只暴露安全的 tool
2. **黑名单 FORBIDDEN_TOOLS** — 高风险永远拒
3. **Gate 前置条件** — keyword gate / FinalPackage 必须先有

**schema 限制 + runtime 检查 + Trace 审计** 三层防护。

---

## Q9: MCP transport 怎么选？

| Transport | 优点 | 缺点 | 适用 |
|---|---|---|---|
| stdio | 简单，IDE 友好 | 需启动进程 | CLI 工具 |
| SSE | 适合长会话 | 服务器推送复杂 | 长任务 |
| HTTP | 通用，Playwright 可测 | 需自己实现 session | MVP / 测试 |

**PaperAgent 当前 HTTP（便于 Playwright + 测试），未来可包 stdio / sse。**

---

## Q10: 怎么升级到真正的 MCP transport？

**当前架构：**
```python
mcp_server.call_tool(req) -> MCPToolCallResponse
mcp_server.get_manifest() -> MCPServerManifest
```

**升级到 stdio：**
```python
# 解析 JSON-RPC → 调 call_tool → 返回 JSON-RPC 响应
```

**Tool schema 已 Pydantic 描述，可直接转 MCP JSON Schema。**

---

## Q11: 你的 MCP 怎么和 Agent 协作？

**3 个 MCP 工具由 Agent 调用：**
- Agent 想检索 → `search_topic_evidence`
- Agent 想看进度 → `get_project_trace`
- Agent 想导出 → `check_export_readiness`

**关键：** Agent 调 MCP 走 Gate + Trace，**不能绕过**。

---

## Q12: 怎么计费 / 限流？

**当前：** 不限流（仅审计）。

**未来：**
- 每个 actor 限速（token bucket）
- LLM 成本分摊到 MCP 调用
- 计费面板
- 异常检测

---

## Q13: 跨项目共享 tool 吗？

**当前：** 每个 project_id 独立。

**未来：**
- 跨 project EvidenceRef 共享
- 全局候选池
- 协作工作流

---

## Q14: 你的 MCP 设计哲学？

**3 条：**
1. **最小暴露** — 只暴露读 / 检查，不暴露写 / 破坏
2. **Gate 不可绕过** — 所有 tool 都走 keyword gate / FinalPackage
3. **审计可追溯** — 所有调用（包括 forbidden）写 Trace

**核心论点：** MCP 不是「把 API 包一层」，而是「把安全边界、审计、权限 Gate 做进协议层」。

---

## Q15: 你的 MCP 和 OpenAI Function Calling 区别？

| 维度 | OpenAI FC | PaperAgent MCP |
|---|---|---|
| 客户端 | OpenAI | 任何 MCP 客户端 |
| 协议 | 私有 | 标准 JSON-RPC |
| 权限 | 客户端实现 | 服务端 manifest + Gate |
| 审计 | 需手写 | Trace 自动 |
| 黑名单 | 需手写 | FORBIDDEN_TOOLS |
| 工具市场 | OpenAI 生态 | 跨厂商 |

---

## Q16: 你的 MCP 和 LangChain Tools 区别？

| 维度 | LangChain Tools | PaperAgent MCP |
|---|---|---|
| 协议 | Python 函数 | 标准协议 |
| 权限边界 | 编程式 | manifest + Gate |
| 审计 | 自行实现 | Trace 自动 |
| 黑名单 | 自行实现 | FORBIDDEN_TOOLS |
| 客户端 | LangChain 生态 | MCP 兼容 |

---

## Q17: 怎么支持 Tools 之外的资源（Resources）？

**MCP 协议还有 Resources / Prompts / Sampling。**

**未来扩展：**
- Resources: project_id → 完整快照
- Prompts: 预制 prompt 模板
- Sampling: 反向调客户端 LLM

**当前 PaperAgent 暂不实现这些，重点是 tools。**

---

## Q18: 怎么支持 streaming？

**当前：** 同步调用，返回完整 result。

**未来：**
- 长任务用 SSE streaming
- partial result 增量返回
- 客户端订阅

**项目证据：** `server.py` 的 `call_tool` 返回 `duration_ms`，可扩展 streaming。

---

## Q19: MCP 怎么和现有 Gate 协作？

**permission.requires_keyword_gate** → 检查 `project_memory.get_latest_snapshot` 是否有 verdict

**permission.requires_final_package** → 检查 `final_package.build_final_package_summary`

**Gate 状态变化时 MCP 调用实时反映。**

---

## Q20: 你的 MCP 怎么做到"高安全"？

**5 个措施：**
1. **白名单** — manifest 限定
2. **黑名单** — FORBIDDEN_TOOLS
3. **Gate** — 状态前置
4. **审计** — Trace 自动
5. **脱敏** — 绝对路径替换

**设计原则：** 默认拒绝，显式允许。

---

> **面试重点：** PaperAgent MCP 不是「接了个协议」，而是「把安全边界、审计、权限 Gate 都做进协议层」。和 OpenAI FC / LangChain Tools 的核心差异是「安全做进协议层 vs 留给业务方」。

---

## Q21: MCP / A2A / ACP 有什么区别？

| 协议 | 解决什么 | PaperAgent 状态 | 类比 |
|---|---|---|---|
| MCP | Agent 调工具 | S36 最小工具暴露，可展示 | 工具接口标准化 |
| A2A | Agent 发现、委派任务、协作 | design-only | 任务分派 |
| ACP | Agent 间消息、异步流、多模态证据交换 | design-only | 消息总线 |

**推荐回答：**

> 我把它们分成三层。MCP 是 Agent 调工具；A2A 是 Agent 发现并委派任务；ACP 是消息治理层——关注多 Agent 之间怎么传消息、传状态、传多模态结果。PaperAgent 当前是 Single-Agent + Gate，所以 MCP 是最贴近的，A2A 和 ACP 作为 design-only 扩展位。协议边界表在 `Plan/design/ACP_Interop_And_Agent_Communication.md`。

## Q22: ACP 在 PaperAgent 中的具体落点？

**当前状态：design-only + schema-ready + interview-visible**

已定义但不接入 runtime：

- **ACPMessage**：`message_id`, `from/to_agent`, `message_type`, `payload`, `artifacts`, `requires_human_gate`, `security`
- **消息类型**：11 种（`task_request`, `evidence_candidate`, `verification_report`, `workspace_command`, `human_gate_request` 等）
- **Artifact 类型**：8 种（`paper`, `dataset`, `repo`, `webpage`, `image`, `pdf_excerpt`, `trace_slice`, `proposal_section`）
- **Human Gate 不可绕过**：写操作强制 `requires_human_gate = true`
- **Trace 全量记录**：所有 ACP 通信（包括被拦截的）写入 Trace

**面试表达：**

> ACP 在 PaperAgent 中是通信治理层。我定义了完整的消息模型和 artifact 类型，但不接入 runtime——因为主线是 Single-Agent，不需要 Agent 间消息总线。这样做的好处是：面试能讲清协议边界，又不把系统做重。详见 `Plan/design/ACP_Interop_And_Agent_Communication.md`。
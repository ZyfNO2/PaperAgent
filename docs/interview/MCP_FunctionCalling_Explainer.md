# MCP Server 与 Function Calling 面试讲解（Session 36）

> 解释 PaperAgent 如何把核心能力暴露为 MCP tools，让外部 Agent 可复用，
> 同时保留 Gate 边界、Trace 审计、禁止高风险操作。

---

## 1. 一句话定位

PaperAgent MCP Server 通过最小 4 个 tools 把「检索证据 / 读候选资源 / 看 Trace / 检查导出就绪」暴露给外部 Agent，所有调用走 Gate + Trace，**禁止** promote_candidate / generate_proposal / delete_project / write_file 等高风险动作。

---

## 2. MCP vs Function Calling

| 维度 | Function Calling | MCP |
|---|---|---|
| 协议层 | 模型 ↔ 工具（OpenAI/Anthropic 各自格式） | 工具 ↔ 宿主（标准 JSON-RPC） |
| 互操作 | 锁定单一厂商 | 跨模型、跨客户端 |
| 资源描述 | 简单 JSON schema | tools / resources / prompts / sampling |
| 适用 | 单次 API 调用 | 多 tool 长会话、IDE 集成 |

**面试回答模板：**

> 「Function Calling 是模型调用工具的格式；MCP 是工具、宿主、客户端之间的标准协议。PaperAgent 同时支持 —— 内部用 Function Calling 风格调用，外部 Agent 用 MCP transport 调用同一份能力。」

---

## 3. 暴露的 4 个最小 Tools

```
search_topic_evidence       → 检索已批准 evidence (需 keyword gate)
get_candidate_resources     → 列出候选资源 (只读)
get_project_trace           → 读 trace 事件流 (只读 + 脱敏)
check_export_readiness      → 检查可导出性 (需 FinalPackage)
```

**不暴露（高风险）：**

```
promote_candidate_to_evidence  → 证据晋升，需用户确认
generate_proposal_draft         → 报告生成，需用户审阅
delete_project                  → 破坏性
write_file / shell_exec         → 任意写
```

---

## 4. Permission Boundary 设计

每个 tool 都有 `ToolPermission` 声明：

```python
class ToolPermission(BaseModel):
    requires_keyword_gate: bool = False
    requires_final_package: bool = False
    read_only: bool = True
    writes_trace: bool = True
    notes: str = ""
```

**3 道闸门：**

1. **白名单** — 工具必须在 manifest 中
2. **黑名单** — 写/破坏性工具永远拒绝
3. **前置条件** — keyword gate / FinalPackage 状态

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
return MCPToolCallResponse
```

---

## 5. Trace 集成

**所有 tool 调用都写 Trace** —— 即使是 forbidden 拒绝：

```python
append_trace(
    project_id=req.arguments["project_id"],
    action="mcp_tool_call",
    target_id=req.tool_name,
    reason=f"MCP tool '{req.tool_name}' from {req.actor}: ok/fail (reason)",
    actor="agent" if req.actor == "external_agent" else "system",
)
```

**为什么禁止工具也要写 Trace？**

- 安全审计可追溯「谁尝试调 write_file」
- 检测滥用模式（高频 forbidden 调用）
- 满足合规要求

---

## 6. Trace 数据脱敏

`get_project_trace` 返回的内容会经过 `sanitize_trace_data` 递归脱敏：

```
原始: "Reading C:\Users\ZYF\secret\file.txt"
脱敏: "Reading <redacted-path>"
```

**脱敏规则：**
- Windows 路径：`[A-Za-z]:\...`
- Unix 路径：`/...`
- 至少 4 字符避免误伤
- 递归处理 dict / list / str

---

## 7. 调用示例

### 7.1 Manifest

```bash
GET /api/v1/mcp/manifest
```

返回：

```json
{
  "server_name": "paperagent-mcp",
  "version": "0.1.0",
  "tool_count": 4,
  "tools": ["search_topic_evidence", ...],
  "forbidden_tools": ["write_file", "delete_project", ...]
}
```

### 7.2 调用工具

```bash
POST /api/v1/mcp/call
{
  "tool_name": "search_topic_evidence",
  "arguments": {"project_id": "p1", "top_k": 5},
  "actor": "external_agent"
}
```

成功：

```json
{
  "tool_name": "search_topic_evidence",
  "success": true,
  "result": {"items": [...], "total": 5},
  "trace_event_id": "mcp_a3f9b2c4d1",
  "duration_ms": 12
}
```

失败（permission_denied）：

```json
{
  "tool_name": "search_topic_evidence",
  "success": false,
  "error": {
    "code": "permission_denied",
    "message": "tool 'search_topic_evidence' requires keyword_review gate..."
  },
  "trace_event_id": "mcp_..."
}
```

---

## 8. 错误码体系

| Code | 含义 |
|---|---|
| `forbidden_tool` | 工具在黑名单 / 不在 manifest |
| `permission_denied` | 前置条件不满足 |
| `missing_dependency` | 缺少必要参数（如 project_id） |
| `internal_error` | 实现异常 |

**关键设计：** 业务错误用 `success=false` + `error.code` 表达，**不抛 HTTPException**。这样客户端能区分 "transport 错误" vs "tool 业务拒绝"。

---

## 9. 工具失败怎么办？

3 层降级：

1. **permission_denied** → 客户端应检查 Gate 状态，提示用户先过 Gate
2. **internal_error** → 实现层异常，Trace 已记录，可重试或回退
3. **transport error** → HTTP 5xx，客户端应退避重试

**关键不变量：** 工具失败**不丢失审计信息** —— Trace 总会被写。

---

## 10. 面试常见追问

### Q1: MCP 和 Function Calling 选哪个？

```
如果只针对单一模型 API → Function Calling 够用。
如果想让多个客户端/IDE 复用同一份工具 → MCP 更合适。
PaperAgent 选择两个都支持：内部用 Function Calling 风格（FastAPI 直接调），
外部 Agent 用 MCP transport（HTTP + JSON-RPC）。
```

### Q2: 怎么防止 Agent 调危险工具？

3 道闸门：

1. **Manifest 白名单** — 只暴露安全的 tool
2. **黑名单 FORBIDDEN_TOOLS** — 高风险永远拒
3. **Gate 前置条件** — keyword gate / FinalPackage 必须先有

### Q3: 工具调用失败怎么办？

- Trace 永远记录（成功 + 失败 + forbidden）
- 业务失败用 `success=false` + `error.code`，HTTP 200
- 客户端根据 code 决定重试 / 提示用户 / 放弃

### Q4: 怎么审计谁调了什么？

所有调用通过 `append_trace(...)` 写入 `.runtime/traces/{project_id}.jsonl`：
- `action="mcp_tool_call"`
- `target_id=tool_name`
- `actor=external_agent`
- `reason` 包含 ok/fail + 原因

### Q5: 为什么不暴露 promote_candidate？

晋升证据涉及：
- 改变 Evidence 状态
- 影响下游 Gate
- 影响导出报告

这些动作需要**用户显式确认**，不应该让外部 Agent 自动触发。MCP 只暴露「读 + 检查」类动作。

### Q6: MCP server 怎么和现有 Gate 协作？

- `permission.requires_keyword_gate` → 检查 `project_memory.get_latest_snapshot` 是否有 verdict
- `permission.requires_final_package` → 检查 `final_package.build_final_package_summary`
- Gate 状态变化时 MCP 调用实时反映

### Q7: 未来怎么升级到真正的 MCP transport？

现在用 HTTP transport（FastAPI 路由），便于 Playwright / 测试访问。未来要做 stdio / sse 时：
- `server.py` 已封装 `call_tool` 和 `get_manifest`
- 只需在 stdio 入口解析 JSON-RPC，调 `mcp_server.call_tool`
- Tool schema 已 Pydantic 描述，可直接转换为 MCP JSON Schema

---

## 11. 与 LangChain / Anthropic Tool Use 对比

| 维度 | LangChain Tools | Anthropic Tool Use | PaperAgent MCP |
|---|---|---|---|
| 协议 | Python 函数 | JSON schema | MCP / HTTP |
| 权限边界 | 编程式 | 无内置 | manifest + Gate |
| 审计 | 自行实现 | 无内置 | Trace 自动 |
| 黑名单 | 自行实现 | 无内置 | FORBIDDEN_TOOLS |
| 客户端支持 | LangChain 生态 | Claude API | MCP 兼容客户端 |

**关键差异：** PaperAgent MCP 把「安全 + 审计」做进协议层，而不是留给业务方。

---

## 12. 可展示文件清单

- `apps/api/app/schemas_mcp.py` — MCPTool / MCPToolCallRequest / MCPToolCallResponse
- `apps/api/app/mcp/tools.py` — 4 个 tool 的 manifest
- `apps/api/app/mcp/permissions.py` — 白名单 / 黑名单 / Gate 检查
- `apps/api/app/mcp/server.py` — call_tool 主入口 + Trace 集成
- `apps/api/app/api/v1/mcp.py` — HTTP 路由
- `apps/api/tests/test_session36_mcp_tools.py` — 19 个后端测试
- `apps/web/e2e/test_one_topic_session36_mcp.py` — 6 个 Playwright 测试
- `docs/interview/MCP_FunctionCalling_Explainer.md` — 本文档

---

## 13. 未来扩展

- stdio / sse MCP transport
- Resource 暴露（不仅是 tool）
- Sampling（让 PaperAgent 反向调客户端 LLM）
- 工具调用计费 / 限流
- 跨 project 共享工具
- 工具调用统计面板

---

> **面试重点强调：** PaperAgent MCP 不是「把 API 包了一层」，而是「把安全边界、审计、权限 Gate 都做进协议层」。这是和 LangChain Tools / 简单 Function Calling 的核心区别。
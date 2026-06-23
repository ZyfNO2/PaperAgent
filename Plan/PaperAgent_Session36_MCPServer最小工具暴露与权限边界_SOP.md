# PaperAgent Session 36 SOP：MCP Server 最小工具暴露与权限边界

> 日期：2026-06-21  
> 前置：S23 已有 Tool Boundary，S34/S35 已有 RAG 与 Memory 解释。  
> 本轮目标：设计并最小实现 PaperAgent MCP Server，把核心能力暴露为 tools，同时保持 gate 和 Trace 边界。

---

## 1. 面试解释

### 面试官可能会问

```text
MCP 和 Function Calling 有什么区别？
你的工具调用怎么做权限控制？
工具失败怎么办？
外部 Agent 能不能复用你的能力？
```

### 为什么需要这么改

公司面经里 MCP / Function Calling 是高频追问，`modelcontextprotocol/servers` 也是近期高热仓库。PaperAgent 如果能暴露 MCP tools，就能从“Web 应用”升级为“可被 Agent 复用的科研证据服务”。

### PaperAgent 的回答

```text
Function Calling 是模型调用工具的格式；
MCP 是工具、资源、宿主之间的标准协议。
PaperAgent 将 search_topic_evidence、get_project_trace、check_export_readiness 暴露为 MCP tools，但所有工具都复用 isToolAllowed 和 Trace，不能绕过 Gate。
```

---

## 2. 最小工具

```text
search_topic_evidence
get_candidate_resources
get_project_trace
check_export_readiness
```

暂不暴露：

```text
promote_candidate_to_evidence
generate_proposal_draft
delete_project
write_file
```

原因：

```text
晋升证据和生成报告属于高风险动作，需要用户显式确认，不适合第一版 MCP 自动暴露。
```

---

## 3. 权限边界

```text
search_topic_evidence：必须 keyword_review approved；
get_candidate_resources：允许只读；
get_project_trace：允许只读，但隐藏敏感路径；
check_export_readiness：必须已有 FinalPackage；
所有工具调用都写 Trace。
```

---

## 4. 建议文件

```text
apps/api/app/mcp/server.py
apps/api/app/mcp/tools.py
apps/api/app/mcp/permissions.py
apps/api/tests/test_session36_mcp_tools.py
docs/interview/MCP_FunctionCalling_Explainer.md
```

如暂不引入完整 MCP runtime，可先写 tool manifest + mock server。

---

## 5. 测试

```text
1. tool manifest 可加载；
2. search_topic_evidence 未过 keyword gate 被拒；
3. get_candidate_resources 可只读返回；
4. check_export_readiness 无 FinalPackage 被拒；
5. 工具调用写 Trace；
6. 禁止 write_file/delete_project；
7. MCP 解释文档存在；
8. S23 isToolAllowed 不回退。
```

---

## 6. 验收标准

```text
1. 至少 4 个 MCP tool 有 manifest；
2. 至少 2 个 tool 可 mock 调用；
3. 权限边界可测；
4. Trace 可记录；
5. 面试解释文档可用；
6. 完工报告包含“面试解释”。
```

---

## 7. 完工报告

```text
Plan/reports/Session_36_MCP_Tools_PermissionBoundary_验收报告.md
```


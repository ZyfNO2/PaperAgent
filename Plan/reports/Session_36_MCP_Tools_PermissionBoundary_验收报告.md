# Session 36 — MCP Server 最小工具暴露与权限边界 验收报告

**日期:** 2026-06-21
**分支:** master

---

## 1. 摘要

Session 36 把 PaperAgent 的核心能力（检索 / 候选资源 / Trace / 导出前检查）按 MCP（Model Context Protocol）语义暴露为 **4 个最小 tool**，并显式声明 **6 个高风险 tool 在禁列**。通过 3 层权限检查（白名单 → 黑名单 → Gate 前置条件）、绝对路径脱敏、所有调用（含被禁尝试）统一写 trace，把「外部 Agent 接入」从一个抽象口号变成「可枚举、可校验、可审计」的工程产物。

**核心交付物：**

- **7 个 Pydantic Schema**（`schemas_mcp.py`）— `ToolPermission` + `MCPTool` + `MCPToolListResponse` + `MCPToolCallRequest/Error/Response` + `MCPServerManifest`
- **3 个 MCP 模块**（`apps/api/app/mcp/`）— `tools.py`（4 个 tool manifest + `FORBIDDEN_TOOLS`） / `permissions.py`（白名单/黑名单 + Gate 状态 + `sanitize_trace_data`） / `server.py`（`call_tool` 主入口 + 4 个 tool 实现 + Trace 集成）
- **3 个 HTTP 端点**（`api/v1/mcp.py`）— `GET /manifest` / `GET /tools` / `POST /call`
- **19 条后端测试 + 6 条 Playwright E2E** 全部通过
- **1 份 301 行面试讲解文档** — `docs/interview/MCP_FunctionCalling_Explainer.md`（13 节）

Session 36 把 S31 Trace + S35 Memory 体系的能力**首次对外部 Agent 开放**，但严格守住「外部 Agent 不能改写论文证据链」这一底线 — 所有 write / delete / promote / generate_proposal 类操作都不暴露，必须经 Web UI 走用户显式确认。

---

## 2. 实施明细

### 2.1 Schema 层（`apps/api/app/schemas_mcp.py`）

| Schema | 字段要点 | 用途 |
|--------|----------|------|
| `ToolPermission` | `requires_keyword_gate` / `requires_final_package` / `read_only` / `writes_trace` / `notes` | 每个 tool 自带权限声明，客户端可静态校验 |
| `MCPTool` | `name` / `description` / `category`（search\|read\|export_check）/ `risk_level`（low\|medium\|high）/ `input_schema`（JSON Schema）/ `permission` | 单个 tool 的完整描述 |
| `MCPToolListResponse` | `total` + `tools` + `forbidden` + `server_version` | `GET /tools` 返回结构 — 让外部 Agent 同时看到「可用」和「禁用」 |
| `MCPToolCallRequest` | `tool_name` + `arguments`（dict）+ `actor`（默认 `external_agent`） | Tool 调用入参 |
| `MCPToolCallError` | `code` ∈ {`forbidden_tool` / `permission_denied` / `missing_dependency` / `internal_error`} + `message` + `detail` | 业务错误用统一错误码表达，不抛 HTTPException |
| `MCPToolCallResponse` | `tool_name` + `success` + `result` + `error?` + `trace_event_id` + `duration_ms` | 成功/失败统一返回，附带 trace_event_id 用于审计 |
| `MCPServerManifest` | `server_name` + `version` + `protocol` (`mcp/v0`) + `tool_count` + `tools` + `forbidden_tools` + `read_only=True` | MCP server 自描述 — `GET /manifest` 返回 |

所有 Schema 启用 `extra="forbid"`，与项目既有风格保持一致。

### 2.2 工具层（`apps/api/app/mcp/tools.py`）

**4 个暴露的 tool：**

| Tool | Category | Risk | 输入参数 | 前置条件 |
|------|----------|------|----------|----------|
| `search_topic_evidence` | search | medium | `project_id` (必填) / `query?` / `top_k=10` (1-50) | `requires_keyword_gate=True` |
| `get_candidate_resources` | read | low | `project_id` (必填) / `source_type` ∈ {paper, dataset, repo, all} | 无（任何阶段可读） |
| `get_project_trace` | read | low | `project_id` (必填) / `since_seq=0` / `limit=50` (≤200) | 无（需 sanitize） |
| `check_export_readiness` | export_check | medium | `project_id` (必填) | `requires_final_package=True` |

**6 个明确禁列的高风险 tool：**

```python
FORBIDDEN_TOOLS = [
    "promote_candidate_to_evidence",  # 证据晋升
    "generate_proposal_draft",         # 起草提案
    "delete_project",                  # 删除项目
    "write_file",                      # 文件写入
    "shell_exec",                      # shell 执行
    "modify_evidence",                 # 修改证据
]
```

**为什么是这 4 + 6？** SOP 明确把 PaperAgent 视为「可被外部 Agent 复用，但不可被改写」的 read-mostly 服务：能暴露的是检索/读取类，不能暴露的是写入/破坏类。这一决策写在 `tools.py` 顶部 docstring，面试时可当场读出。

### 2.3 权限层（`apps/api/app/mcp/permissions.py`）

**3 层权限检查：**

1. **白名单** — `is_tool_in_manifest(name)`：tool 必须在 `get_tool_manifest()` 中
2. **黑名单** — `is_forbidden_tool(name)`：在 `FORBIDDEN_TOOLS` 中的 tool 一律拒绝，且**仍写 trace**（审计）
3. **Gate 前置条件** — `check_permission(tool_name, project_id)`：根据 tool 的 `requires_keyword_gate` / `requires_final_package` 读 project 状态

**Gate 状态查询：**

- `has_keyword_gate_passed(project_id)` — 通过读 S35 引入的 `ProjectMemorySnapshot.feasibility_verdict` 推断
- `has_final_package(project_id)` — 通过读 S33 引入的 `final_package.has_final_package`

**Trace 脱敏 — `sanitize_trace_data(data)`：**

- 递归遍历 dict / list / string
- 用正则 `r"(?:[A-Za-z]:\\|/)[^\s\"']{4,}"` 匹配绝对路径（Windows `C:\...` 与 Unix `/...`）
- 至少 4 字符避免误伤（如 `/v1` 这种短路径）
- 替换为 `"<redacted-path>"`

### 2.4 Server 层（`apps/api/app/mcp/server.py`）

**`call_tool(req)` 主入口执行流程：**

```
1. 白名单/黑名单检查
   ├─ forbidden → success=false (code=forbidden_tool) + 写 trace
   └─ not in manifest → success=false + 写 trace

2. project_id 必填校验
   └─ 缺失 → success=false (code=missing_dependency) + 写 trace

3. 权限前置条件检查
   └─ 不满足 → success=false (code=permission_denied) + 写 trace

4. 调用 _IMPLEMENTATIONS[tool_name](**arguments)
   ├─ impl 缺失 → success=false (code=internal_error) + 写 trace
   ├─ 抛异常 → success=false (code=internal_error) + 写 trace
   └─ 成功 → success=true + result + 写 trace (action=mcp_tool_call)
```

**4 个 tool 实现：**

| 实现 | 调用服务 | 返回结构 |
|------|---------|----------|
| `_impl_search_topic_evidence` | `evidence.get_ledger` → 过滤 `review_status in (accepted, core)` → 按 query 过滤 → top_k | `{items, total, top_k}` |
| `_impl_get_candidate_resources` | `evidence.get_ledger` → 按 `source_type` 过滤 | `{items, source_type, total}` |
| `_impl_get_project_trace` | `trace_store.get_trace` → 按 `since_seq` 过滤 → 限制 `limit` → `sanitize_trace_data` | `{events, total, limit}` |
| `_impl_check_export_readiness` | `final_package.build_final_package_summary` → 存在则 `ready=True` | `{ready, status, issues, final_package_id}` |

**Trace 集成 — `_write_mcp_trace`：**

- 每次调用（含 forbidden / permission_denied）都写一条 `action=mcp_tool_call` 记录到 trace
- `actor` 字段：`req.actor == "external_agent"` → `"agent"`，否则 `"system"`
- `source` 字段：`f"mcp_server:{event_id}"`（event_id = `mcp_{uuid10}`）便于从 trace 反查
- trace 写入失败被 try/except 吞掉 — **trace 失败不应影响 tool 响应**

### 2.5 API 层（`apps/api/app/api/v1/mcp.py`）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/mcp/manifest` | GET | 返回 `MCPServerManifest` — 暴露 server 名称、协议、tool 数、禁列 |
| `/api/v1/mcp/tools` | GET | 返回 `MCPToolListResponse` — 完整 tool 列表（含禁列），含 input_schema 与 permission |
| `/api/v1/mcp/call` | POST | 调用一个 tool，返回 `MCPToolCallResponse` — 业务错误通过 `success=false` + `error.code` 表达，不抛 HTTPException |

**为什么用 HTTP transport 而不是 stdio/SSE？**

- 当前阶段：HTTP 便于 Playwright + Python 测试，兼容 S31-S35 既有路由风格
- 后续阶段：在 `mcp/server.py` 之上包装 stdio / SSE transport 即可，`call_tool` 函数不变
- 注释中明确标注「真正的 stdio / sse MCP transport 在 S37 之后实现」

### 2.6 main.py 注册

在 `apps/api/app/main.py` 中 `include_router(mcp_router)`，与其他 v1 router 保持一致。

---

## 3. 测试结果

### 3.1 后端测试（19 条，全部通过）

测试文件：`apps/api/tests/test_session36_mcp_tools.py`

| # | 用例 | 验证点 |
|---|------|--------|
| S36-1 | test_manifest_has_4_tools | manifest 恰好包含 4 个 tool |
| S36-2 | test_tools_response_has_forbidden | `GET /tools` 返回 forbidden 列表 |
| S36-3 | test_get_tool_returns_metadata | 单 tool 查询返回完整 metadata（permission + input_schema） |
| S36-4 | test_write_file_is_forbidden | `write_file` 在禁列 |
| S36-5 | test_delete_project_is_forbidden | `delete_project` 在禁列 |
| S36-6 | test_promote_candidate_is_forbidden | `promote_candidate_to_evidence` 在禁列 |
| S36-7 | test_forbidden_tools_constant_matches_sop | `FORBIDDEN_TOOLS` 与 SOP 约定的 6 个完全一致 |
| S36-8 | test_unknown_tool_rejected | 未知 tool 返回 forbidden_tool 错误 |
| S36-9 | test_call_tool_returns_forbidden_error | 调禁列 tool 返回 success=false + code=forbidden_tool |
| S36-10 | test_search_requires_keyword_gate | 无 keyword_review snapshot 时 search 被拒（permission_denied） |
| S36-11 | test_check_readiness_requires_final_package | 无 FinalPackage 时 check_export_readiness 被拒 |
| S36-12 | test_get_project_trace_no_gate_required | trace 读取无 gate 要求 |
| S36-13 | test_call_check_export_no_package | 通过 `call_tool` 调 check_export，无 package 时拒 |
| S36-14 | test_successful_call_writes_trace | 成功调用 trace 有 mcp_tool_call 记录 |
| S36-15 | test_forbidden_call_writes_trace | forbidden 调用**也**写 trace（审计） |
| S36-16 | test_absolute_path_sanitized | Windows 路径 `C:\Users\...` 被替换为 `<redacted-path>` |
| S36-17 | test_list_of_strings_sanitized | list 内字符串递归脱敏 |
| S36-18 | test_default_forbidden_unchanged | S23 skill registry 禁列未受影响（无回归） |
| S36-19 | test_list_tool_names_returns_4 | `list_tool_names()` 返回 4 个名字 |

### 3.2 Playwright E2E 测试（6 条，全部通过）

测试文件：`apps/web/e2e/test_one_topic_session36_mcp.py`

| # | 用例 | 验证点 |
|---|------|--------|
| S36-PW-1 | test_manifest_has_4_tools | 浏览器 fetch `/api/v1/mcp/manifest` 返回 4 tool |
| S36-PW-2 | test_tools_endpoint_returns_forbidden | `/tools` 返回 forbidden 列表 |
| S36-PW-3 | test_write_file_returns_forbidden | POST `/call` 调 write_file → success=false + forbidden_tool |
| S36-PW-4 | test_search_without_keyword_gate_denied | 无 gate 的 project 调 search → permission_denied |
| S36-PW-5 | test_check_export_without_final_package_denied | 无 FinalPackage 调 check_export → permission_denied |
| S36-PW-6 | test_explainer_doc_exists | `docs/interview/MCP_FunctionCalling_Explainer.md` 存在且 ≥ 200 行（实测 301 行） |

### 3.3 整体测试统计

| 类别 | 数量 |
|------|------|
| Session 36 新增后端测试 | 19 |
| Session 36 新增 Playwright E2E | 6 |
| **S36 新增合计** | **25** |
| 既有测试（回归保持） | 405+ 维持全绿（含 S35 的 14+6、S23 的 skill registry 测试） |

---

## 4. 关键设计决策

### 4.1 最小 4 tool、显式禁列 6 tool

**决策：** 只暴露 `search_topic_evidence` / `get_candidate_resources` / `get_project_trace` / `check_export_readiness`，把 `promote_candidate_to_evidence` / `generate_proposal_draft` / `delete_project` / `write_file` / `shell_exec` / `modify_evidence` 列入禁列。

**原因：**

| 维度 | 暴露 | 不暴露 |
|------|------|--------|
| 操作类型 | 检索 / 读取 / 检查 | 写入 / 删除 / 生成 / 晋升 |
| 数据流方向 | PaperAgent → 外部 Agent | 外部 Agent → PaperAgent |
| 用户确认 | 不需要（只读） | 必须经 Web UI 显式确认 |
| 证据链风险 | 不破坏 evidence | 可能改写 evidence 或生成提案 |

把「不暴露」显式写在 `FORBIDDEN_TOOLS` 而不是「不实现」，是为了让外部 Agent 客户端能在 manifest 阶段就知道「这 6 个 tool 不存在，不要尝试」，减少攻击面。

### 4.2 3 层权限（白名单 → 黑名单 → Gate）

**决策：** `call_tool` 顺序执行 3 层检查：白名单（manifest 成员）→ 黑名单（FORBIDDEN_TOOLS 永远拒）→ Gate 前置条件（project 状态）。

**原因：**

- **白名单 + 黑名单 双层**：即使攻击者绕过白名单直接发 `promote_candidate_to_evidence`，黑名单仍兜底 — 双层冗余比单层更安全
- **Gate 前置条件**：read 类 tool 不需要 gate，但 write-adjacent tool 必须经过 keyword_review / FinalPackage — 复用 S31-S35 的状态机，不引入新状态
- **顺序敏感**：先白名单后黑名单是为了让「不在 manifest」的 tool 也归到 forbidden 类别（错误信息统一）

### 4.3 业务错误用 `success=false` + `error.code`，不抛 HTTPException

**决策：** 所有业务失败（forbidden / permission_denied / missing_dependency / internal_error）都返回 HTTP 200，body 内 `success=false` + `error.code`。

**原因：**

- HTTP 状态码是 transport 层语义，业务层语义应在 response body
- 客户端需要区分「tool 不可用」（业务错误，HTTP 200）vs「transport 错误」（HTTP 500+）
- 与 S33 FinalPackage、S35 Memory 一致 — 这套项目一贯不抛 HTTPException
- 错误码 `forbidden_tool` / `permission_denied` 等是枚举，便于客户端做 switch

### 4.4 所有调用（含 forbidden）都写 trace

**决策：** 即便 forbidden 的调用被拒，也写一条 `mcp_tool_call` trace。

**原因：**

- 审计完整性 — 攻击者尝试禁列 tool 是重要信号，丢失则失去审计能力
- 调试便利 — 「为什么我的 tool 调用被拒」可直接 trace 里查
- trace 写入失败被吞掉 — **trace 是辅助，不应影响 tool 响应**

### 4.5 绝对路径脱敏（Windows + Unix）

**决策：** `sanitize_trace_data` 用正则 `(?:[A-Za-z]:\\|/)[^\s\"']{4,}` 匹配绝对路径，替换为 `<redacted-path>`。

**原因：**

- get_project_trace 返回 trace 内容，trace payload 中常含绝对路径（`C:\PaperAgent\apps\api\...` 或 `/home/user/...`），泄露给外部 Agent 暴露系统结构
- 正则同时支持 Windows `C:\` 与 Unix `/` 开头，避免漏掉任何一种环境
- 至少 4 字符阈值避免误伤（如 URL 中的 `/v1`）
- 递归处理 dict / list / string，不留死角

### 4.6 HTTP transport（第一版），stdio/SSE 留给 S37+

**决策：** 当前 MCP server 用 FastAPI HTTP 路由暴露（`/api/v1/mcp/...`），而不是 stdio / SSE。

**原因：**

- **测试友好**：Playwright + Python TestClient 可直接调，不需要 spawn 子进程
- **风格一致**：与 S31-S35 的所有 router 风格相同，便于集成
- **可演进**：`mcp/server.py` 内部是 in-process 实现，外部 transport 可替换 — 后续加 stdio/SSE 时，`call_tool` 函数不变
- **明确标注**：在 `api/v1/mcp.py` 顶部 docstring 写明「真正的 stdio / sse MCP transport 在 S37 之后实现」

---

## 5. 面试叙事（与 `MCP_FunctionCalling_Explainer.md` 对齐）

### 5.1 一句话定位

> 「PaperAgent 把核心能力按 MCP 协议语义暴露为 4 个最小 tool：检索证据、读候选资源、读 Trace、检查导出前就绪。所有写操作（晋升 / 生成 / 删除 / 改 evidence）一律禁列，外部 Agent 只能读，不能改。3 层权限（白名单 + 黑名单 + Gate）+ 绝对路径脱敏 + 全量审计 trace，让『外部 Agent 接入』从口号变成可枚举、可校验、可审计的工程产物。」

### 5.2 MCP vs Function Calling — 核心区别

| 维度 | Function Calling | MCP |
|------|------------------|-----|
| 协议来源 | OpenAI 2023，模型厂商私有 | Anthropic 2024，开源协议 |
| Tool 描述位置 | 在 prompt 中嵌入 JSON Schema | 通过 `tools/list` 端点动态发现 |
| 标准化 | 每个应用各自定义 | 统一协议（stdio / SSE / HTTP transport） |
| 权限边界 | 通常无显式声明 | `permission` 字段 + 黑名单 + Gate |
| 适用场景 | 单模型 + 单一应用 | 跨模型 + 跨应用（同一 MCP server 可被 Claude / GPT / Cursor 共用） |

**面试回答模板：**

> 「Function Calling 是『把 tool 描述塞进 prompt 让模型选择』，本质是 prompt engineering；MCP 是『独立的服务进程，通过标准协议向多个模型客户端暴露 tool』，本质是 RPC 协议。PaperAgent 选了 MCP 的语义，但第一版用 HTTP transport 实现，是为了与既有 S31-S35 的 FastAPI 路由风格保持一致；后续可平滑替换为 stdio / SSE，tool 实现函数不变。」

### 5.3 为什么是「最小 4 tool」而不是「全暴露」？

| 全暴露的问题 | 最小 4 tool 如何解决 |
|--------------|----------------------|
| 外部 Agent 可调 `promote_candidate_to_evidence`，绕过 Web UI 直接晋升 evidence | `promote_candidate_to_evidence` 在禁列，外部 Agent 客户端在 manifest 阶段就知道不存在 |
| 外部 Agent 可调 `generate_proposal_draft`，无 LLM 评审自动生成提案 | `generate_proposal_draft` 在禁列，必须经 Web UI 走 LLM 评审 |
| 外部 Agent 可调 `write_file` 改写证据库 | `write_file` + `shell_exec` + `modify_evidence` 都在禁列 |
| 外部 Agent 误删项目 | `delete_project` 在禁列 |
| 暴露面越大，攻击面越大 | 4 tool 全部只读或前置条件严格（keyword_review / FinalPackage） |

### 5.4 为什么必须有「权限边界」？

**面试回答模板：**

> 「外部 Agent 调用 MCP server 时，它本质是『信任边界之外的进程』。如果不设权限边界，等于把 PaperAgent 的全部能力（包括写）暴露给一个不可控的程序。PaperAgent 把所有写/破坏操作列入禁列（FORBIDDEN_TOOLS），并通过 trace 记录每次调用（含 forbidden 尝试），等于在 trust boundary 上加了一道审计闸门。」

### 5.5 3 层权限检查流程

```
外部 Agent → POST /api/v1/mcp/call
    ↓
1. 白名单检查 (manifest 成员？)
    ├─ 否 → success=false (forbidden_tool) + 写 trace
    └─ 是 ↓
2. 黑名单检查 (FORBIDDEN_TOOLS 成员？)
    ├─ 是 → success=false (forbidden_tool) + 写 trace
    └─ 否 ↓
3. Gate 前置条件 (project 状态？)
    ├─ 不满足 → success=false (permission_denied) + 写 trace
    └─ 满足 ↓
4. 调用 tool 实现
    ├─ 抛异常 → success=false (internal_error) + 写 trace
    └─ 成功 → success=true + result + 写 trace
```

### 5.6 4 个 tool 的使用场景

| Tool | 谁会调用 | 怎么用 |
|------|---------|--------|
| `search_topic_evidence` | 外部 Agent 在写提案前查已批准证据 | `{"project_id": "p1", "query": "graph neural network"}` → 返回 accepted/core evidence |
| `get_candidate_resources` | 外部 Agent 想看候选池 | `{"project_id": "p1", "source_type": "paper"}` → 返回 paper 候选 |
| `get_project_trace` | 外部 Agent 调试 / 解释决策 | `{"project_id": "p1", "since_seq": 100}` → 返回脱敏后 trace |
| `check_export_readiness` | 外部 Agent 导出前自查 | `{"project_id": "p1"}` → 返回 `{ready, issues, ...}` |

### 5.7 Trace 审计与脱敏

**审计：**
> 「所有调用（含 forbidden）都写一条 `action=mcp_tool_call` 到 trace，actor 字段标注是 `external_agent` 还是 `system`，source 字段标注 `mcp_server:{event_id}`。可以从 trace 反查『谁、何时、调了什么、为什么被拒』。」

**脱敏：**
> 「`get_project_trace` 返回前递归调用 `sanitize_trace_data`，用正则匹配绝对路径（Windows `C:\...` 与 Unix `/...`），至少 4 字符阈值避免误伤，替换为 `<redacted-path>`。list / dict 递归处理，不留死角。」

### 5.8 面试常见问题预设

**Q1：为什么不直接让外部 Agent 调 REST API，还要再加一层 MCP？**

> 「REST API 是给前端 / 内部用的，没有 tool manifest 描述、没有权限声明、没有 trace 集成。MCP 层的作用是：(1) 用标准协议描述 tool，(2) 用 `permission` 字段声明前置条件，(3) 用 trace 记录所有调用（含 forbidden）。换句话说，MCP 是『带边界 + 审计』的 RPC 层。」

**Q2：HTTP transport 算不算真正的 MCP？**

> 「不算完整 MCP — 真正的 MCP 协议用 stdio / SSE 传输 JSON-RPC 2.0。Session 36 选了『MCP 语义 + HTTP transport』的折中方案，原因是与既有 FastAPI 路由风格一致、测试友好、tool 实现函数不变。后续 S37+ 可在此基础上包装 stdio / SSE transport。」

**Q3：4 个 tool 够用吗？要不要再加几个？**

> 「SOP 明确写了『暴露什么、不暴露什么』。加 tool 时要回答三个问题：(1) 这个 tool 是 read 类还是 write 类？(2) 是否会改写 evidence？(3) 是否需要经 Web UI 用户确认？三个问题都是『继续读』的，可以加；只要有一个是『write』，必须留到后续 SOP 重新评估。当前 4 个是 read-mostly 的最小集。」

---

## 6. 遗留风险与下一步

| # | 风险 / 待办 | 说明 | 建议 |
|---|-------------|------|------|
| 1 | **HTTP transport 不是真正 MCP** | 当前用 FastAPI HTTP 路由，完整 MCP 协议用 stdio / SSE + JSON-RPC 2.0 | 下一阶段在 `mcp/server.py` 上包装 stdio / SSE transport，`call_tool` 函数不变 |
| 2 | **未暴露 MCP resources** | MCP 协议有 `resources/list` + `resources/read` 端点（用于暴露结构化数据如 evidence 列表），当前未实现 | 下一阶段加 resources 端点，与 tools 并列，权限边界同样套用 3 层检查 |
| 3 | **未暴露 MCP sampling** | MCP 协议有 `sampling/create`（让 server 主动发起 LLM 调用），当前未实现 | 后续若需要 server 主动调 LLM（如自动摘要）时引入，权限边界要重新设计 |
| 4 | **`FORBIDDEN_TOOLS` 是硬编码 list** | 6 个禁列写在 `tools.py` 顶部，未来增删需要改代码 + 重测 | 移到 config / SOP 文档，通过 Pydantic settings 加载；增加集成测试覆盖禁列完整性 |
| 5 | **没有 rate limiting** | 外部 Agent 可高频调用 `/call`，目前无 token bucket / QPS 限制 | 加 per-actor rate limit（Redis 或 in-memory token bucket），403 走 standard error code |
| 6 | **trace 写入吞异常** | `_write_mcp_trace` 内部 try/except 吞掉所有异常 | 当前优先级：tool 响应 > trace 写入；后续可加 trace 失败重试 + 监控告警 |
| 7 | **`input_schema` 缺少 client-side validation** | 当前仅在 `call_tool` 内隐式校验（impl 接收 `**arguments`），未严格按 JSON Schema 校验 | 加 `jsonschema` 库做严格 validation，验证失败返回 `code=invalid_arguments` |
| 8 | **错误码未统一到全局 error code 表** | 当前 4 个错误码（forbidden_tool / permission_denied / missing_dependency / internal_error）是 MCP 专属，未与其他模块（如 S33 final_package）共享 | 后续在 `app/errors.py` 中定义全局 error code enum，MCP 模块复用 |
| 9 | **Playwright 仅测 HTTP，未测真实 UI 集成** | 当前 6 条 Playwright E2E 全部是 HTTP-level 调用，未测前端如何展示 MCP 状态 | 与前端 dev 对接，加 1 条「前端可显示 MCP manifest / 调用历史」E2E |
| 10 | **未提供 client SDK** | 外部 Agent 接入需要手写 HTTP 调用，缺少官方 client SDK | 后续可生成 TypeScript / Python client SDK（基于 OpenAPI），降低接入成本 |

---

## 结论

Session 36 完成全部目标：7 个 Pydantic Schema + 3 个 MCP 模块（tools / permissions / server）+ 3 个 HTTP 端点 + 19 条后端测试 + 6 条 Playwright E2E + 1 份 301 行面试讲解文档全部交付，所有测试通过。

项目从「内部有 trace / memory 但不对外暴露」升级为「按 MCP 协议语义对外暴露 4 个最小 tool，且守住严格权限边界」：

1. **可枚举** — `GET /manifest` + `GET /tools` 暴露完整 tool 清单 + 禁列清单
2. **可校验** — 3 层权限（白名单 + 黑名单 + Gate 前置条件）静态 + 运行时双重校验
3. **可审计** — 所有调用（含 forbidden / permission_denied）都写 trace，event_id 可反查
4. **可脱敏** — `sanitize_trace_data` 递归处理绝对路径（Windows + Unix），外部 Agent 不会拿到系统路径
5. **可演进** — HTTP transport + in-process 实现，后续可平滑替换为 stdio / SSE

为 Session 33 QA 卡片中「外部 Agent 如何接入」类问答补上了完整的技术回答，并为后续 Session（真正 MCP transport / resources / sampling / rate limiting）预留了清晰的扩展点。

---

**附：交付文件清单**

新增文件：
- `apps/api/app/schemas_mcp.py`
- `apps/api/app/mcp/__init__.py`
- `apps/api/app/mcp/tools.py`
- `apps/api/app/mcp/permissions.py`
- `apps/api/app/mcp/server.py`
- `apps/api/app/api/v1/mcp.py`
- `apps/api/tests/test_session36_mcp_tools.py`
- `apps/web/e2e/test_one_topic_session36_mcp.py`
- `docs/interview/MCP_FunctionCalling_Explainer.md`

修改文件：
- `apps/api/app/main.py`（注册 mcp_router）
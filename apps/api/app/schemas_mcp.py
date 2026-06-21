"""Session 36: MCP Server schemas — 工具清单 + 权限声明 + 调用响应.

设计目的：
- 把 PaperAgent 的能力按 MCP 协议语义描述为 tool manifest
- 提供 permissions 字段让 client 知道边界
- 与现有 Gate / Trace 体系保持一致
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ---- Tool 分类 ---- #

ToolCategory = Literal["search", "read", "export_check"]
RiskLevel = Literal["low", "medium", "high"]


class ToolPermission(BaseModel):
    """Tool 的权限声明."""

    model_config = ConfigDict(extra="forbid")

    requires_keyword_gate: bool = False
    requires_final_package: bool = False
    read_only: bool = True
    writes_trace: bool = True
    notes: str = ""


class MCPTool(BaseModel):
    """单个 MCP tool 描述."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    category: ToolCategory
    risk_level: RiskLevel
    input_schema: dict[str, Any] = Field(default_factory=dict)
    permission: ToolPermission = Field(default_factory=ToolPermission)


class MCPToolListResponse(BaseModel):
    """返回所有可用 tool."""

    model_config = ConfigDict(extra="forbid")

    total: int
    tools: list[MCPTool]
    forbidden: list[str] = Field(default_factory=list)
    server_version: str = "0.1.0"


# ---- Tool 调用 ---- #


class MCPToolCallRequest(BaseModel):
    """Tool 调用请求."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    actor: str = "external_agent"


class MCPToolCallError(BaseModel):
    """Tool 调用错误."""

    model_config = ConfigDict(extra="forbid")

    code: str  # "forbidden_tool" | "permission_denied" | "missing_dependency" | "internal_error"
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResponse(BaseModel):
    """Tool 调用响应."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    error: MCPToolCallError | None = None
    trace_event_id: str | None = None
    duration_ms: int = 0


# ---- Manifest 元数据 ---- #


class MCPServerManifest(BaseModel):
    """MCP server 自描述."""

    model_config = ConfigDict(extra="forbid")

    server_name: str = "paperagent-mcp"
    version: str = "0.1.0"
    protocol: str = "mcp/v0"
    description: str = (
        "PaperAgent MCP Server — 把 TopicPilot-CN 的检索、证据、可读性能力暴露为 tools。"
        "所有 tool 都走 Gate 与 Trace，外部 Agent 可安全复用。"
    )
    tool_count: int
    tools: list[str]
    forbidden_tools: list[str]
    read_only: bool = True

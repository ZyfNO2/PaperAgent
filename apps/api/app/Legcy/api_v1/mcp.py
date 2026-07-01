"""Session 36: MCP HTTP router — 把 manifest / call 暴露为 HTTP 端点.

虽然名字叫 MCP, 但本阶段使用 HTTP transport (便于 Playwright / 测试访问).
真正的 stdio / sse MCP transport 在 S37 之后实现.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.mcp import server as mcp_server
from app.schemas_mcp import (
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolListResponse,
    MCPServerManifest,
)


router = APIRouter(prefix="/api/v1/mcp", tags=["mcp"])


@router.get(
    "/manifest",
    response_model=MCPServerManifest,
    summary="Session 36: MCP server 自描述",
)
def get_manifest() -> MCPServerManifest:
    return mcp_server.get_manifest()


@router.get(
    "/tools",
    response_model=MCPToolListResponse,
    summary="Session 36: 列出可用 tools (含 forbidden)",
)
def list_tools() -> MCPToolListResponse:
    return mcp_server.list_tools_response()


@router.post(
    "/call",
    response_model=MCPToolCallResponse,
    summary="Session 36: 调用一个 MCP tool",
)
def call_tool(req: MCPToolCallRequest) -> MCPToolCallResponse:
    # 业务失败通过 success=false 表达, 不抛 HTTPException,
    # 让客户端能区分 "tool 不可用" 与 "transport 错误"
    return mcp_server.call_tool(req)
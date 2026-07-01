"""Session 36: MCP tools — 把 PaperAgent 能力暴露为 4 个最小 tool.

工具集合:
  - search_topic_evidence    (search, medium)  需 keyword gate
  - get_candidate_resources  (read, low)       只读
  - get_project_trace        (read, low)       只读 + 隐藏敏感路径
  - check_export_readiness   (export_check, medium) 需 FinalPackage

高风险动作（promote / generate_proposal / delete / write_file）一律不暴露，
外部 Agent 需通过 Web UI 走用户显式确认。
"""

from __future__ import annotations

from typing import Any

from app.schemas_mcp import MCPTool, ToolPermission


def _keyword_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "query": {"type": "string", "description": "可选的二次检索词"},
            "top_k": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
        },
        "required": ["project_id"],
    }


def _candidate_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "source_type": {
                "type": "string",
                "enum": ["paper", "dataset", "repo", "all"],
                "default": "all",
            },
        },
        "required": ["project_id"],
    }


def _trace_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "since_seq": {"type": "integer", "default": 0},
            "limit": {"type": "integer", "default": 50, "maximum": 200},
        },
        "required": ["project_id"],
    }


def _readiness_input_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
        },
        "required": ["project_id"],
    }


def get_tool_manifest() -> list[MCPTool]:
    """返回 4 个 tool 的 manifest."""
    return [
        MCPTool(
            name="search_topic_evidence",
            description=(
                "按 project_id 检索已批准的关键词，返回 EvidenceRef 列表。"
                "需要 keyword_review 已通过。"
            ),
            category="search",
            risk_level="medium",
            input_schema=_keyword_input_schema(),
            permission=ToolPermission(
                requires_keyword_gate=True,
                requires_final_package=False,
                read_only=True,
                writes_trace=True,
                notes="仅暴露 accepted/core 状态的 evidence，candidate 不暴露",
            ),
        ),
        MCPTool(
            name="get_candidate_resources",
            description=(
                "按 project_id 列出候选资源（paper / dataset / repo），"
                "只读，不修改任何状态。"
            ),
            category="read",
            risk_level="low",
            input_schema=_candidate_input_schema(),
            permission=ToolPermission(
                requires_keyword_gate=False,
                requires_final_package=False,
                read_only=True,
                writes_trace=True,
                notes="任何阶段都允许，候选态可读",
            ),
        ),
        MCPTool(
            name="get_project_trace",
            description=(
                "读取 project 的 Trace 事件流，外部 Agent 可观察 Step Deck 行为。"
                "敏感路径（如绝对路径、token）会被脱敏。"
            ),
            category="read",
            risk_level="low",
            input_schema=_trace_input_schema(),
            permission=ToolPermission(
                requires_keyword_gate=False,
                requires_final_package=False,
                read_only=True,
                writes_trace=True,
                notes="脱敏: 绝对路径、API key 字段全部替换",
            ),
        ),
        MCPTool(
            name="check_export_readiness",
            description=(
                "检查 project 是否可导出 FinalPackage，导出前必备检查。"
                "需要已有 FinalPackage。"
            ),
            category="export_check",
            risk_level="medium",
            input_schema=_readiness_input_schema(),
            permission=ToolPermission(
                requires_keyword_gate=False,
                requires_final_package=True,
                read_only=True,
                writes_trace=True,
                notes="无 FinalPackage 直接拒绝",
            ),
        ),
    ]


def get_tool(name: str) -> MCPTool | None:
    for t in get_tool_manifest():
        if t.name == name:
            return t
    return None


def list_tool_names() -> list[str]:
    return [t.name for t in get_tool_manifest()]


# 明确禁止暴露给 MCP 的高风险工具
FORBIDDEN_TOOLS = [
    "promote_candidate_to_evidence",
    "generate_proposal_draft",
    "delete_project",
    "write_file",
    "shell_exec",
    "modify_evidence",
]

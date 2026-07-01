"""Session 36: MCP 权限边界检查.

每个 tool 都有 permission 声明 (ToolPermission), 此模块负责:
  - check_tool_allowed  : 工具是否在白名单
  - check_permission     : 调用方是否满足前置条件
  - sanitize_trace_data  : 脱敏敏感路径
"""

from __future__ import annotations

import re
from typing import Any

from app.mcp.tools import FORBIDDEN_TOOLS, get_tool


# ---- 白名单 / 黑名单 ---- #


def is_tool_in_manifest(name: str) -> bool:
    return get_tool(name) is not None


def is_forbidden_tool(name: str) -> bool:
    return name in FORBIDDEN_TOOLS


# ---- 权限检查 ---- #


def check_tool_allowed(name: str) -> tuple[bool, str]:
    """检查 tool 是否允许被外部 Agent 调用.

    Returns:
        (allowed, reason)
    """
    if is_forbidden_tool(name):
        return False, f"tool '{name}' is in the forbidden list (high-risk action)"
    if not is_tool_in_manifest(name):
        return False, f"tool '{name}' is not in MCP tool manifest"
    return True, "ok"


# 绝对路径脱敏 (Windows / Unix)
_ABS_PATH_RE = re.compile(
    r"(?:[A-Za-z]:\\|/)[^\s\"']{4,}",  # 至少 4 字符避免误伤
)


def sanitize_trace_data(data: Any) -> Any:
    """递归脱敏 trace 数据中的绝对路径."""
    if isinstance(data, dict):
        return {k: sanitize_trace_data(v) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_trace_data(v) for v in data]
    if isinstance(data, str):
        return _ABS_PATH_RE.sub("<redacted-path>", data)
    return data


def has_keyword_gate_passed(project_id: str) -> bool:
    """检查 project 是否已过 keyword_review gate.

    通过读 project memory snapshot / trace 推断.
    没有 memory 时返回 False.
    """
    try:
        from app.services.project_memory import get_latest_snapshot

        snap = get_latest_snapshot(project_id)
        if snap is None:
            return False
        # snapshot.feasibility_verdict 在 keyword 通过后才会有
        return bool(snap.feasibility_verdict)
    except Exception:
        return False


def has_final_package(project_id: str) -> bool:
    """检查 project 是否已有 FinalPackage."""
    try:
        from app.services.final_package import has_final_package as _has

        return _has(project_id)
    except Exception:
        return False


def check_permission(tool_name: str, project_id: str) -> tuple[bool, str]:
    """检查调用 tool 的前置条件是否满足."""
    tool = get_tool(tool_name)
    if tool is None:
        return False, f"tool '{tool_name}' not found"
    perm = tool.permission
    if perm.requires_keyword_gate and not has_keyword_gate_passed(project_id):
        return False, (
            f"tool '{tool_name}' requires keyword_review gate, "
            f"project '{project_id}' has not passed"
        )
    if perm.requires_final_package and not has_final_package(project_id):
        return False, (
            f"tool '{tool_name}' requires FinalPackage, "
            f"project '{project_id}' has none"
        )
    return True, "ok"

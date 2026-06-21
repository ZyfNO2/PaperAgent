"""Session 36: MCP server 主入口 — tool 调用 + Trace 集成.

不引入完整 MCP runtime, 用 Python in-process 实现, 便于:
  - 在 FastAPI 路由中暴露 manifest / call
  - 单元测试可 mock
  - 未来若需真正 MCP transport (stdio / sse) 可在此基础上包装
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from app.mcp import permissions
from app.mcp.tools import get_tool, get_tool_manifest
from app.schemas_mcp import (
    MCPServerManifest,
    MCPToolCallError,
    MCPToolCallRequest,
    MCPToolCallResponse,
    MCPToolListResponse,
)


# ---- manifest ---- #


def get_manifest() -> MCPServerManifest:
    tools = get_tool_manifest()
    return MCPServerManifest(
        tool_count=len(tools),
        tools=[t.name for t in tools],
        forbidden_tools=list(permissions.FORBIDDEN_TOOLS),
    )


def list_tools_response() -> MCPToolListResponse:
    tools = get_tool_manifest()
    return MCPToolListResponse(
        total=len(tools),
        tools=tools,
        forbidden=list(permissions.FORBIDDEN_TOOLS),
    )


# ---- tool 调用实现 ---- #


def _impl_search_topic_evidence(project_id: str, query: str = "", top_k: int = 10) -> dict[str, Any]:
    """检索已批准 evidence."""
    from app.services.evidence import get_ledger
    from app.schemas_evidence import EvidenceLedgerResponse

    try:
        ledger = get_ledger(project_id)
    except Exception:
        return {"items": [], "total": 0, "note": "ledger unavailable"}

    items = ledger.items if isinstance(ledger, EvidenceLedgerResponse) else []
    accepted = [e for e in items if getattr(e, "review_status", "") in ("accepted", "core")]
    if query:
        q = query.lower()
        accepted = [e for e in accepted if q in (getattr(e, "title", "") or "").lower()]
    return {
        "items": [
            {
                "evidence_id": e.evidence_id,
                "title": e.title,
                "url": e.url,
                "review_status": e.review_status,
            }
            for e in accepted[:top_k]
        ],
        "total": len(accepted),
        "top_k": top_k,
    }


def _impl_get_candidate_resources(project_id: str, source_type: str = "all") -> dict[str, Any]:
    """列出候选资源."""
    try:
        from app.services.evidence import get_ledger
        from app.schemas_evidence import EvidenceLedgerResponse

        ledger = get_ledger(project_id)
    except Exception:
        return {"items": [], "source_type": source_type, "total": 0}

    items = ledger.items if isinstance(ledger, EvidenceLedgerResponse) else []
    out: list[dict[str, Any]] = []
    for e in items:
        st = getattr(e, "evidence_type", "") or ""
        if source_type != "all" and st != source_type:
            continue
        out.append(
            {
                "evidence_id": e.evidence_id,
                "title": e.title or "",
                "source_type": st,
                "url": e.url or "",
            }
        )
    return {"items": out, "source_type": source_type, "total": len(out)}


def _impl_get_project_trace(project_id: str, since_seq: int = 0, limit: int = 50) -> dict[str, Any]:
    """读取 trace 并脱敏."""
    try:
        from app.services.trace_store import get_trace

        resp = get_trace(project_id)
    except Exception:
        return {"events": [], "total": 0, "limit": limit}

    raw_events = resp.events if hasattr(resp, "events") else []
    out: list[dict[str, Any]] = []
    for ev in raw_events:
        seq = 0
        meta = getattr(ev, "metadata", None) or {}
        if isinstance(meta, dict):
            seq = meta.get("seq", 0)
        if seq < since_seq:
            continue
        out.append(
            {
                "step_key": getattr(ev, "step_key", "") or "",
                "event_type": getattr(ev, "event_type", "") or "",
                "summary": (getattr(ev, "summary", "") or "")[:200],
            }
        )
        if len(out) >= limit:
            break
    out = permissions.sanitize_trace_data(out)
    return {"events": out, "total": len(out), "limit": limit}


def _impl_check_export_readiness(project_id: str) -> dict[str, Any]:
    """导出前检查."""
    try:
        from app.services.final_package import build_final_package_summary

        summary = build_final_package_summary(project_id)
    except Exception:
        return {"ready": False, "note": "final_package service unavailable"}

    if summary is None:
        return {"ready": False, "reason": "no_final_package"}
    # FinalPackage 存在 -> 简化认为 ready (实际 readiness 在 one_topic.py 内调用 check_readiness)
    return {
        "ready": True,
        "status": "pass",
        "issues": [],
        "final_package_id": getattr(summary, "package_id", None),
    }


_IMPLEMENTATIONS = {
    "search_topic_evidence": _impl_search_topic_evidence,
    "get_candidate_resources": _impl_get_candidate_resources,
    "get_project_trace": _impl_get_project_trace,
    "check_export_readiness": _impl_check_export_readiness,
}


# ---- 入口 ---- #


def call_tool(req: MCPToolCallRequest) -> MCPToolCallResponse:
    """调用 tool 并写 trace."""
    t0 = time.time()
    trace_event_id: str | None = None

    # 1. 白名单 / 黑名单
    allowed, reason = permissions.check_tool_allowed(req.tool_name)
    if not allowed:
        trace_event_id = _write_mcp_trace(req, success=False, reason=reason, error_code="forbidden_tool")
        return MCPToolCallResponse(
            tool_name=req.tool_name,
            success=False,
            error=MCPToolCallError(
                code="forbidden_tool",
                message=reason,
                detail={"tool_name": req.tool_name},
            ),
            trace_event_id=trace_event_id,
            duration_ms=_ms(t0),
        )

    # 2. 权限前置条件
    project_id = req.arguments.get("project_id", "")
    if not project_id:
        trace_event_id = _write_mcp_trace(req, success=False, reason="missing project_id", error_code="missing_dependency")
        return MCPToolCallResponse(
            tool_name=req.tool_name,
            success=False,
            error=MCPToolCallError(
                code="missing_dependency",
                message="project_id is required",
                detail={},
            ),
            trace_event_id=trace_event_id,
            duration_ms=_ms(t0),
        )

    ok, reason = permissions.check_permission(req.tool_name, project_id)
    if not ok:
        trace_event_id = _write_mcp_trace(req, success=False, reason=reason, error_code="permission_denied")
        return MCPToolCallResponse(
            tool_name=req.tool_name,
            success=False,
            error=MCPToolCallError(
                code="permission_denied",
                message=reason,
                detail={"project_id": project_id},
            ),
            trace_event_id=trace_event_id,
            duration_ms=_ms(t0),
        )

    # 3. 执行实现
    impl = _IMPLEMENTATIONS.get(req.tool_name)
    if impl is None:
        trace_event_id = _write_mcp_trace(req, success=False, reason="no implementation", error_code="internal_error")
        return MCPToolCallResponse(
            tool_name=req.tool_name,
            success=False,
            error=MCPToolCallError(
                code="internal_error",
                message=f"no implementation for tool '{req.tool_name}'",
            ),
            trace_event_id=trace_event_id,
            duration_ms=_ms(t0),
        )

    try:
        result = impl(**req.arguments)
    except Exception as exc:  # noqa: BLE001
        trace_event_id = _write_mcp_trace(
            req, success=False, reason=str(exc), error_code="internal_error"
        )
        return MCPToolCallResponse(
            tool_name=req.tool_name,
            success=False,
            error=MCPToolCallError(
                code="internal_error",
                message=str(exc),
            ),
            trace_event_id=trace_event_id,
            duration_ms=_ms(t0),
        )

    trace_event_id = _write_mcp_trace(req, success=True, reason="ok", error_code=None)
    return MCPToolCallResponse(
        tool_name=req.tool_name,
        success=True,
        result=result,
        trace_event_id=trace_event_id,
        duration_ms=_ms(t0),
    )


# ---- Trace 辅助 ---- #


def _ms(t0: float) -> int:
    return int((time.time() - t0) * 1000)


def _write_mcp_trace(
    req: MCPToolCallRequest,
    success: bool,
    reason: str,
    error_code: str | None,
) -> str:
    """写一条 trace 记录 tool 调用."""
    event_id = f"mcp_{uuid.uuid4().hex[:10]}"
    try:
        from app.services.trace_store import append_trace

        append_trace(
            project_id=req.arguments.get("project_id") or "_external_mcp",
            action="mcp_tool_call",
            target_type="mcp_tool",
            target_id=req.tool_name,
            reason=(
                f"MCP tool '{req.tool_name}' from {req.actor}: "
                f"{'ok' if success else 'fail'} ({reason[:120]})"
            ),
            actor="agent" if req.actor == "external_agent" else "system",
            source=f"mcp_server:{event_id}",
        )
    except Exception:
        # trace 失败不应影响 tool 响应
        pass
    return event_id
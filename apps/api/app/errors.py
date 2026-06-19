"""统一错误结构 (Session 18 SOP §4).

业务可降级场景不要全部变成 500; 能 partial 就 partial + warning.
真实 500 只保留给未预期异常.

错误结构:
{
  "error_code": "RETRIEVAL_SOURCE_FAILED",
  "message": "OpenAlex 暂时不可用, 已保留其他来源结果.",
  "detail": {...},
  "next_action": "稍后重试, 或使用手动导入 / 资料卡片化.",
  "request_id": "req_...",
  "project_id": "ot_..."
}
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


# 错误码常量 (按 SOP §4 表格)
PROJECT_NOT_FOUND = "PROJECT_NOT_FOUND"
EVIDENCE_NOT_FOUND = "EVIDENCE_NOT_FOUND"
RETRIEVAL_SOURCE_FAILED = "RETRIEVAL_SOURCE_FAILED"
RETRIEVAL_ALL_FAILED = "RETRIEVAL_ALL_FAILED"
VERIFY_FAILED = "VERIFY_FAILED"
MATERIAL_TOO_LARGE = "MATERIAL_TOO_LARGE"
MATERIAL_TYPE_UNSUPPORTED = "MATERIAL_TYPE_UNSUPPORTED"
MATERIAL_PARSE_SKIPPED = "MATERIAL_PARSE_SKIPPED"
REPORT_QUALITY_LOW = "REPORT_QUALITY_LOW"
BASELINE_CONTRACT_FAILED = "BASELINE_CONTRACT_FAILED"
INTERNAL_ERROR = "INTERNAL_ERROR"

# HTTP 状态映射
_STATUS_MAP = {
    PROJECT_NOT_FOUND: 404,
    EVIDENCE_NOT_FOUND: 404,
    RETRIEVAL_ALL_FAILED: 502,
    MATERIAL_TOO_LARGE: 413,
    MATERIAL_TYPE_UNSUPPORTED: 415,
    # partial / skipped 用 200 (业务可降级)
    RETRIEVAL_SOURCE_FAILED: 200,
    VERIFY_FAILED: 200,
    MATERIAL_PARSE_SKIPPED: 200,
    REPORT_QUALITY_LOW: 200,
    BASELINE_CONTRACT_FAILED: 500,
    INTERNAL_ERROR: 500,
}


# 默认 next_action 文案
_NEXT_ACTIONS = {
    PROJECT_NOT_FOUND: "先跑一次分析 (POST /analyze) 或检查 project_id 是否正确.",
    EVIDENCE_NOT_FOUND: "刷新证据列表; 该 evidence 可能已被删除.",
    RETRIEVAL_SOURCE_FAILED: "稍后重试, 或切换 refresh=False 用上次结果.",
    RETRIEVAL_ALL_FAILED: "检查网络; 可改用手动添加 / 资料卡片化.",
    VERIFY_FAILED: "URL 不可访问, 这条证据不会进 supports; 可手动确认后改 status.",
    MATERIAL_TOO_LARGE: "压缩文件 (上限 20MB) 或拆分后再上传.",
    MATERIAL_TYPE_UNSUPPORTED: "确认扩展名与 MIME 在白名单 (PDF / PNG / JPG / WEBP / TXT / MD).",
    MATERIAL_PARSE_SKIPPED: "PDF 无文本层 / 图片未做 OCR, 请人工确认或换格式.",
    REPORT_QUALITY_LOW: "按 revision_checklist 补强后重新生成.",
    BASELINE_CONTRACT_FAILED: "检查 S17 baseline 是否被破坏, 修复代码或更新基线.",
    INTERNAL_ERROR: "看后端日志; 若是用户输入导致, 提供更详细复现.",
}


def make_error(
    error_code: str,
    message: str,
    *,
    detail: dict[str, Any] | None = None,
    next_action: str | None = None,
    project_id: str | None = None,
    request_id: str | None = None,
    status: int | None = None,
) -> dict[str, Any]:
    """构造一个统一错误 dict (给 fastapi.HTTPException(detail=...) 用)."""

    return {
        "error_code": error_code,
        "message": message,
        "detail": detail or {},
        "next_action": next_action or _NEXT_ACTIONS.get(error_code, ""),
        "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
    }


def status_for(error_code: str) -> int:
    return _STATUS_MAP.get(error_code, 500)


class AppError(Exception):
    """业务异常 (区别于未预期 500)."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
        next_action: str | None = None,
        project_id: str | None = None,
        status: int | None = None,
    ):
        self.error_code = error_code
        self.message = message
        self.detail = detail or {}
        self.next_action = next_action or _NEXT_ACTIONS.get(error_code, "")
        self.project_id = project_id
        self.status = status or _STATUS_MAP.get(error_code, 500)
        super().__init__(message)

    def to_dict(self, request_id: str | None = None) -> dict[str, Any]:
        return make_error(
            self.error_code,
            self.message,
            detail=self.detail,
            next_action=self.next_action,
            project_id=self.project_id,
            request_id=request_id,
        )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """FastAPI exception handler: 把 AppError 转成统一 JSON 响应."""

    body = exc.to_dict(request_id=f"req_{uuid.uuid4().hex[:12]}")
    return JSONResponse(status_code=exc.status, content=body)


async def http_exception_handler(request: Request, exc) -> JSONResponse:
    """FastAPI HTTPException handler (向后兼容优先).

    - detail 是含 error_code 的 dict → 透传 (新代码走 AppError 结构)
    - detail 是普通 dict → 补 error_code / next_action 等结构化字段, 同时保留 detail 原值
    - detail 是字符串 → 保持 FastAPI 默认 {"detail": str} (旧测试 / 前端读 r.json()['detail'])

    新代码应优先抛 AppError 获得完整结构化错误.
    """

    from fastapi import HTTPException
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "error_code" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        if isinstance(detail, dict):
            code = INTERNAL_ERROR if exc.status_code >= 500 else "HTTP_ERROR"
            body = make_error(code, detail.get("message", "HTTP error"))
            body["detail"] = detail
            return JSONResponse(status_code=exc.status_code, content=body)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})
    return JSONResponse(
        status_code=500,
        content=make_error(INTERNAL_ERROR, "unexpected error", detail={"raw": str(exc)}),
    )
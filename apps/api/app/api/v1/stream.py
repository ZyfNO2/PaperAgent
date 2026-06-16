"""SSE 端点: 8 个流式 wrapper.

每条事件格式: data: {"type": ..., "name": ..., "detail": ..., "meta": {...}}\\n\\n
前端 fetch + ReadableStream 消费.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session

router = APIRouter(prefix="/api/v1/projects", tags=["stream"])


def _sse_bytes(ev: dict[str, Any]) -> bytes:
    return f"data: {json.dumps(ev, ensure_ascii=False)}\n\n".encode("utf-8")


async def _stream_phase(
    phase_name: str, runner: Callable[[Callable[..., None]], Any]
) -> AsyncGenerator[bytes, None]:
    """通用 SSE 包装. runner 是 async fn, 接受 emit(name, detail, meta) callable,
    runner 内调 emit 上报 trace, 最后自己 emit 一个 result 事件.

    在 asyncio 同一 loop 内: queue + 后台 task 模式, 主循环 yield.
    """

    queue: asyncio.Queue = asyncio.Queue()

    def emit(name: str, detail: str, meta: dict[str, Any] | None = None) -> None:
        if name == "result" or name.startswith("result_"):
            ev_type = "result"
        elif name in ("llm", "llm_call", "llm_done"):
            ev_type = "llm"
        elif name == "start":
            ev_type = "start"
        elif name == "error":
            ev_type = "error"
        elif name == "warn":
            ev_type = "warn"
        else:
            ev_type = "step"
        queue.put_nowait({"type": ev_type, "name": name, "detail": detail, "meta": meta or {}})

    yield _sse_bytes({"type": "start", "phase": phase_name})

    async def _run() -> None:
        try:
            await runner(emit)
        except Exception as exc:  # noqa: BLE001
            await queue.put({"type": "error", "detail": f"{type(exc).__name__}: {exc}"})
        finally:
            await queue.put({"type": "__end__"})

    task = asyncio.create_task(_run())

    while True:
        ev = await queue.get()
        if ev.get("type") == "__end__":
            break
        yield _sse_bytes(ev)

    await task
    yield _sse_bytes({"type": "end"})


# ---------- 单 endpoint: 在这里 import async helpers (懒加载避免循环) ----------


def _decompose_runner(project_id: int, prefer: str, sink: Callable[..., None]) -> None:
    """Phase 02 拆解. 是 async 但 runner 接受 sink 函数, SSE wrapper 内部已用 queue.
    这里我们跑在 to_thread, 但 build_evidence_async 是 async 不能直接跑线程, 所以
    这个函数必须是 async — 见 _stream_phase_async."""
    raise NotImplementedError  # 由 _stream_phase_async 替代


# 实际方案: 直接 async SSE 端点 (不通过 _stream_phase 包装), 因为业务函数本身就是 async


@router.post("/{project_id}/topic/decompose/stream")
async def decompose_topic_stream(
    project_id: int,
    body: dict | None = None,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import decompose_async

    body = body or {}
    prefer = body.get("prefer", "auto")
    return StreamingResponse(
        _stream_phase("decompose", lambda emit: decompose_async(project_id, session, prefer, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/search/plan/stream")
async def build_search_plan_stream(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import search_plan_async

    return StreamingResponse(
        _stream_phase("search_plan", lambda emit: search_plan_async(project_id, session, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/evidence/build/stream")
async def build_evidence_stream(
    project_id: int,
    body: dict | None = None,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import evidence_async

    body = body or {}
    prefer = body.get("prefer", "auto")
    return StreamingResponse(
        _stream_phase("evidence", lambda emit: evidence_async(project_id, session, prefer, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/risk/evaluate/stream")
async def risk_evaluate_stream(
    project_id: int,
    body: dict | None = None,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import risk_async

    body = body or {}
    prefer = body.get("prefer", "auto")
    return StreamingResponse(
        _stream_phase("risk", lambda emit: risk_async(project_id, session, prefer, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/work_package/plan/stream")
async def work_package_stream(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import work_package_async

    return StreamingResponse(
        _stream_phase("work_package", lambda emit: work_package_async(project_id, session, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/proposal/draft/stream")
async def proposal_draft_stream(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import proposal_async

    return StreamingResponse(
        _stream_phase("proposal", lambda emit: proposal_async(project_id, session, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/committee/review/stream")
async def committee_review_stream(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import committee_async

    return StreamingResponse(
        _stream_phase("committee", lambda emit: committee_async(project_id, session, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{project_id}/final_package/build/stream")
async def final_package_stream(
    project_id: int,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    from app.api.v1.projects_async_helpers import final_package_async

    return StreamingResponse(
        _stream_phase("final_package", lambda emit: final_package_async(project_id, session, emit)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

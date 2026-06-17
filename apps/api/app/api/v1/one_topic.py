"""OneTopic router: POST /analyze + POST /analyze/stream (SSE).

对齐 Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md §12.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from ...schemas import OneTopicRequest, OneTopicResponse
from ...services import one_topic as ot_service

router = APIRouter(prefix="/api/v1/one-topic", tags=["one-topic"])


@router.post("/analyze", response_model=OneTopicResponse, summary="一题分析: 6 段产物一次返回")
def analyze(req: OneTopicRequest) -> OneTopicResponse:
    try:
        return ot_service.run_one_topic(req)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=json.loads(exc.json())) from exc


@router.post("/analyze/stream", summary="一题分析 SSE 流式: 边推 trace 边算")
async def analyze_stream(req: OneTopicRequest) -> StreamingResponse:
    """SSE 端点. 事件流:
    start / step (keyword_decompose / paper_search / dataset_search / engineering_search /
                  feasibility / proposal_recommendation / light_review / result) / warn / error / end.
    """

    async def _gen() -> AsyncGenerator[bytes, None]:
        queue: asyncio.Queue = asyncio.Queue()

        def emit(name: str, detail: str, meta: dict | None = None) -> None:
            payload = {
                "type": (
                    "result" if name == "result" else
                    "error" if name == "error" else
                    "warn" if name == "warn" else
                    "start" if name == "start" else
                    "step"
                ),
                "name": name,
                "detail": detail,
                "meta": meta or {},
            }
            queue.put_nowait(payload)

        yield "data: " + json.dumps({"type": "start", "phase": "one_topic"}, ensure_ascii=False) + "\n\n"

        async def _run() -> None:
            try:
                await asyncio.to_thread(ot_service.run_one_topic_stream, req, emit)
            except Exception as exc:  # noqa: BLE001
                emit("error", f"{type(exc).__name__}: {exc}")
            finally:
                await queue.put({"type": "__end__"})

        task = asyncio.create_task(_run())

        while True:
            ev = await queue.get()
            if ev.get("type") == "__end__":
                break
            yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"

        await task
        yield "data: " + json.dumps({"type": "end"}, ensure_ascii=False) + "\n\n"

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

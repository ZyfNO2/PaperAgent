"""Agent trace sink: 把 build_* 内部步骤 emit 到 SSE 流.

每个 build_* 节点函数接受可选 trace_sink 参数. 形如:

    def build_x(..., trace_sink=None):
        def emit(name, detail, **meta):
            if trace_sink:
                trace_sink(name, detail, meta)
        emit("start", "开始做 X")
        ...
        emit("step", "拼装 prompt", max_tokens=4000)
        raw = chat_json(...)
        emit("llm", "LLM 返回成功", duration_ms=12000)
        ...
        emit("result", "完成 X", paper_count=8)

trace_sink 由 SSE 端点传入, 把事件塞进 asyncio.Queue, 跨线程用 call_soon_threadsafe.
未传 trace_sink 时, emit 静默 (no-op).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger(__name__)


@dataclass
class TraceEvent:
    """SSE 事件载荷 (序列化为 JSON dict)."""

    type: Literal["start", "step", "llm", "warn", "result", "error"]
    name: str
    detail: str
    meta: dict[str, Any] = field(default_factory=dict)
    ts_ms: int = field(default_factory=lambda: int(time.time() * 1000))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "detail": self.detail,
            "meta": self.meta,
            "ts_ms": self.ts_ms,
        }


def noop_sink(name: str, detail: str, meta: dict[str, Any] | None = None) -> None:
    """默认 sink: 静默."""
    return None


def console_sink(name: str, detail: str, meta: dict[str, Any] | None = None) -> None:
    """开发用: print 一行, 不阻塞业务."""
    extras = " ".join(f"{k}={v}" for k, v in (meta or {}).items())
    line = f"[trace] {name}: {detail}"
    if extras:
        line += f"  ({extras})"
    logger.info(line)


class ListSink:
    """测试用: 把所有事件存 list 供断言."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def __call__(self, name: str, detail: str, meta: dict[str, Any] | None = None) -> None:
        # type 推断: "llm" / "result" 名字以 result_ 开头视为 result
        if name == "result" or name.startswith("result_"):
            ev_type: Literal["result"] = "result"
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
        self.events.append(TraceEvent(type=ev_type, name=name, detail=detail, meta=meta or {}))

    def of_type(self, t: str) -> list[TraceEvent]:
        return [e for e in self.events if e.type == t]

    def has_name(self, name: str) -> bool:
        return any(e.name == name for e in self.events)


def make_sink_func(
    sink: Callable[[str, str, dict[str, Any] | None], None] | ListSink | None
) -> Callable[[str, str, dict[str, Any] | None], None]:
    """统一 sink 入参: None 走 noop, ListSink 实例直接用, 函数原样."""
    if sink is None:
        return noop_sink
    if isinstance(sink, ListSink):
        return sink
    if callable(sink):
        return sink
    return noop_sink

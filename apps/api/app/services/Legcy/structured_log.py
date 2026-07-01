"""结构化日志 (Session 18 SOP §8).

MVP 只做本地 .runtime/logs/app.jsonl, 不引入日志平台.

字段:
  ts, level, request_id, project_id, action,
  target_type, target_id, status, duration_ms, message

边界:
  不记录用户上传全文;
  不记录敏感文件内容;
  只记录 id / 状态 / 摘要.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]


_LOCK = threading.Lock()


def _log_path() -> Path:
    base = Path(os.environ.get("PAPERAGENT_LOG_DIR", PROJECT_ROOT / ".runtime" / "logs"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "app.jsonl"


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    level: str,
    message: str,
    *,
    request_id: str | None = None,
    project_id: str | None = None,
    action: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    status: str | None = None,
    duration_ms: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写一条结构化日志到 .runtime/logs/app.jsonl. 返回这条事件 dict (不入盘校验失败也安全)."""

    event = {
        "ts": _utc_iso(),
        "level": level,
        "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
        "project_id": project_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "status": status,
        "duration_ms": duration_ms,
        "message": message,
        "extra": extra or {},
    }
    try:
        with _LOCK:
            with _log_path().open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        # 日志失败不阻塞业务
        pass
    return event


def info(message: str, **kw) -> dict[str, Any]:
    return log_event("info", message, **kw)


def warn(message: str, **kw) -> dict[str, Any]:
    return log_event("warn", message, **kw)


def error(message: str, **kw) -> dict[str, Any]:
    return log_event("error", message, **kw)


class timed:
    """上下文管理器: 测量耗时并自动写一条结构化日志."""

    def __init__(self, action: str, *, level: str = "info", **kw):
        self.action = action
        self.level = level
        self.kw = kw
        self.start = 0.0

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, exc_type, exc, tb):
        ms = int((time.time() - self.start) * 1000)
        status = "ok" if exc_type is None else "error"
        msg = self.kw.pop("message", f"{self.action} {status}")
        kw = dict(self.kw)
        kw.setdefault("status", status)
        kw.setdefault("duration_ms", ms)
        log_event(self.level if exc_type is None else "error", msg, action=self.action, **kw)
        return False  # 不吞异常
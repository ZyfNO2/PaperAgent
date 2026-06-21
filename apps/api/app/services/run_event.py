"""Session 27: RunEvent persistence service (SOP §6-7).

持久化策略：
- .runtime/runs/{project_id}/{run_id}/events.jsonl
- .runtime/runs/{project_id}/{run_id}/state.json
- .runtime/runs/{project_id}/{run_id}/user_patches.jsonl
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas_run_event import (
    RunCreateRequest,
    RunCreateResponse,
    RunEvent,
    RunEventAppendRequest,
    RunEventAppendResponse,
    RunEventListResponse,
    RunResumeRequest,
    RunState,
    RunStatus,
)

# ---- runtime root ---- #

RUNTIME_ROOT = Path(os.getenv("TOPICPILOT_RUNTIME_ROOT", ".runtime"))


def _run_dir(project_id: str, run_id: str) -> Path:
    return RUNTIME_ROOT / "runs" / project_id / run_id


def _events_path(project_id: str, run_id: str) -> Path:
    return _run_dir(project_id, run_id) / "events.jsonl"


def _state_path(project_id: str, run_id: str) -> Path:
    return _run_dir(project_id, run_id) / "state.json"


def _patches_path(project_id: str, run_id: str) -> Path:
    return _run_dir(project_id, run_id) / "user_patches.jsonl"


# ---- CRUD ---- #


def create_run(req: RunCreateRequest) -> RunCreateResponse:
    """创建 run，写入初始 state.json."""
    run_id = req.run_id or f"run_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    state = RunState(
        run_id=run_id,
        project_id=req.project_id,
        status="running",
        started_at=now,
    )
    d = _run_dir(req.project_id, run_id)
    d.mkdir(parents=True, exist_ok=True)
    _state_path(req.project_id, run_id).write_text(state.model_dump_json(indent=2), encoding="utf-8")
    # touch events file
    _events_path(req.project_id, run_id).touch()
    return RunCreateResponse(
        run_id=run_id,
        project_id=req.project_id,
        status="running",
        events_url=f"/api/v1/runs/{run_id}/events",
        stream_url=f"/api/v1/runs/{run_id}/stream",
    )


def append_event(
    project_id: str,
    run_id: str,
    req: RunEventAppendRequest,
) -> RunEventAppendResponse:
    """追加事件到 events.jsonl，更新 state.json."""
    ev_path = _events_path(project_id, run_id)
    st_path = _state_path(project_id, run_id)
    if not st_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found for project {project_id}")

    # 读取当前 seq
    state = RunState.model_validate_json(st_path.read_text(encoding="utf-8"))
    new_seq = state.last_seq + 1
    now = datetime.now(timezone.utc).isoformat()
    event_id = f"evt_{run_id}_{new_seq:04d}"

    event = RunEvent(
        event_id=event_id,
        seq=new_seq,
        run_id=run_id,
        project_id=project_id,
        step_key=req.step_key,
        event_type=req.event_type,
        status=req.status,
        payload=req.payload,
        ts=now,
        source=req.source,
    )

    # append JSONL
    with ev_path.open("a", encoding="utf-8") as f:
        f.write(event.model_dump_json() + "\n")

    # update state
    state.last_seq = new_seq
    state.last_step_key = req.step_key
    state.status = req.status
    st_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")

    return RunEventAppendResponse(
        event_id=event_id,
        seq=new_seq,
        run_id=run_id,
        status=req.status,
    )


def get_events(
    project_id: str,
    run_id: str,
    from_seq: int = 0,
) -> RunEventListResponse:
    """读取 events.jsonl，返回 from_seq 之后的事件."""
    ev_path = _events_path(project_id, run_id)
    st_path = _state_path(project_id, run_id)
    if not st_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found for project {project_id}")

    state = RunState.model_validate_json(st_path.read_text(encoding="utf-8"))
    events: list[RunEvent] = []
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            ev = RunEvent.model_validate_json(line)
            if ev.seq > from_seq:
                events.append(ev)

    return RunEventListResponse(
        run_id=run_id,
        project_id=project_id,
        total=len(events),
        last_seq=state.last_seq,
        status=state.status,
        events=events,
    )


def list_events(
    project_id: str,
    run_id: str,
    from_seq: int = 0,
) -> RunEventListResponse:
    """List events from events.jsonl (alias for get_events)."""
    return get_events(project_id, run_id, from_seq)


def append_user_patch(
    project_id: str,
    run_id: str,
    patch: dict[str, Any],
    from_seq: int,
    strategy: str,
) -> None:
    """追加 user_patch 到 user_patches.jsonl."""
    p_path = _patches_path(project_id, run_id)
    if not _state_path(project_id, run_id).exists():
        raise FileNotFoundError(f"Run {run_id} not found for project {project_id}")

    entry = {
        "patch": patch,
        "from_seq": from_seq,
        "strategy": strategy,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    with p_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # update state user_patches count
    st_path = _state_path(project_id, run_id)
    state = RunState.model_validate_json(st_path.read_text(encoding="utf-8"))
    state.user_patches += 1
    st_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")


def get_state(project_id: str, run_id: str) -> RunState:
    """读取 run state."""
    st_path = _state_path(project_id, run_id)
    if not st_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found for project {project_id}")
    return RunState.model_validate_json(st_path.read_text(encoding="utf-8"))


def update_run_status(project_id: str, run_id: str, status: RunStatus) -> RunState:
    """更新 run 状态."""
    st_path = _state_path(project_id, run_id)
    if not st_path.exists():
        raise FileNotFoundError(f"Run {run_id} not found for project {project_id}")
    state = RunState.model_validate_json(st_path.read_text(encoding="utf-8"))
    state.status = status
    if status in ("completed", "failed", "aborted"):
        state.completed_at = datetime.now(timezone.utc).isoformat()
    st_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    return state


def cleanup_run(project_id: str, run_id: str) -> bool:
    """删除 run 目录（测试清理用）."""
    import shutil

    d = _run_dir(project_id, run_id)
    if d.exists():
        shutil.rmtree(d)
        return True
    return False

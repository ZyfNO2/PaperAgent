"""Session 11: Trace 持久化与操作回放.

把 in-memory trace dict 升级为 .runtime/traces/{project_id}.jsonl
每行一个 JSON. in-memory 缓存保留 (速度), 但以 jsonl 为准.

调用:
  append_trace(...)                  # 单入口, evidence.append_trace 委托
  get_trace(project_id, ...)         # 读 + 过滤
  get_evidence_timeline(project_id, evidence_id)
  get_trace_summary(project_id)
  reset_traces()                     # 测试用
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from ..schemas_trace import TraceEvent, TraceListResponse, TraceSummaryResponse


# ---------- 路径配置 ---------- #


def _get_trace_dir() -> Path:
    """每次调用时读取 env, 支持测试时切换目录."""

    return Path(os.environ.get("PAPERAGENT_TRACE_DIR", ".runtime/traces"))


def _ensure_dir() -> None:
    _get_trace_dir().mkdir(parents=True, exist_ok=True)


def _jsonl_path(project_id: str) -> Path:
    safe = project_id.replace("/", "_").replace("\\", "_")
    return _get_trace_dir() / f"{safe}.jsonl"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- in-memory 缓存 (兼容 evidence.py 旧接口) ---------- #

_CACHE: dict[str, list[dict[str, Any]]] = {}
_CACHE_LOCK = threading.RLock()


# ---------- 写入 ---------- #


def append_trace(
    project_id: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    evidence_id: str | None = None,
    reason: str | None = None,
    actor: Literal["system", "user", "agent"] = "system",
    before: dict | None = None,
    after: dict | None = None,
    source: str | None = None,
    session: str | None = None,
) -> dict[str, Any]:
    """单入口写入. 同时写 jsonl 和 in-memory 缓存."""

    event: dict[str, Any] = {
        "trace_id": f"tr_{uuid.uuid4().hex[:10]}",
        "project_id": project_id,
        "ts": _utcnow_iso(),
        "actor": actor,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "evidence_id": evidence_id,
        "before": before or {},
        "after": after or {},
        "reason": reason,
        "source": source,
        "session": session,
    }
    # 1) in-memory 缓存
    with _CACHE_LOCK:
        _CACHE.setdefault(project_id, []).append(event)
    # 2) 持久化到 jsonl
    try:
        _ensure_dir()
        path = _jsonl_path(project_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        # 持久化失败时 in-memory 已有, 不抛 (单进程 MVP)
        pass
    return event


# ---------- 读取 ---------- #


def _read_jsonl(project_id: str) -> list[dict[str, Any]]:
    path = _jsonl_path(project_id)
    if not path.exists():
        # 降级到 in-memory
        with _CACHE_LOCK:
            return list(_CACHE.get(project_id, []))
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    # 用 in-memory cache 补回启动前 + 启动后未落盘的事件 (防顺序错乱)
    # 简化: 启动后写入同时进两边, 这里只用 jsonl 即可.
    return out


def get_trace(
    project_id: str,
    *,
    limit: int = 100,
    action: str | None = None,
    actor: str | None = None,
    since: str | None = None,
) -> TraceListResponse:
    events = _read_jsonl(project_id)
    # 过滤
    if action:
        events = [e for e in events if e.get("action") == action]
    if actor:
        events = [e for e in events if e.get("actor") == actor]
    if since:
        events = [e for e in events if (e.get("ts") or "") >= since]
    filtered = len(events)
    # 最新在前
    events.reverse()
    events = events[:limit]
    return TraceListResponse(
        project_id=project_id,
        events=[TraceEvent(**e) for e in events],
        total=filtered,
        filtered=filtered,
    )


def get_evidence_timeline(project_id: str, evidence_id: str) -> list[TraceEvent]:
    events = _read_jsonl(project_id)
    matched = [e for e in events if e.get("evidence_id") == evidence_id]
    return [TraceEvent(**e) for e in matched]


def get_trace_summary(project_id: str) -> TraceSummaryResponse:
    events = _read_jsonl(project_id)
    user_n = sum(1 for e in events if e.get("actor") == "user")
    system_n = sum(1 for e in events if e.get("actor") == "system")
    agent_n = sum(1 for e in events if e.get("actor") == "agent")
    last_ts = events[-1]["ts"] if events else None

    key_decisions: list[str] = []
    for e in events:
        action = e.get("action") or ""
        if action not in {
            "workspace_move", "workspace_patch", "review_status_changed",
            "manual_verification", "card_intake_created",
            "final_package_build", "pivot_selected", "verify_evidence",
            "verify_project", "ref_rebuild", "ref_review",
        }:
            continue
        eid = e.get("evidence_id") or e.get("target_id") or "?"
        reason = e.get("reason") or ""
        actor = e.get("actor") or "system"
        if action in ("workspace_move", "workspace_patch"):
            lane = (e.get("after") or {}).get("workspace_lane") or "?"
            key_decisions.append(f"{actor} 将 {eid} 移到 {lane} 栏: {reason}".strip())
        elif action == "review_status_changed":
            new_s = (e.get("after") or {}).get("review_status") or "?"
            key_decisions.append(f"{actor} 将 {eid} 状态改为 {new_s}: {reason}".strip())
        elif action == "manual_verification":
            v = (e.get("after") or {}).get("verification_status") or "?"
            key_decisions.append(f"{actor} 手动确认 {eid} 验证状态 = {v}".strip())
        elif action == "card_intake_created":
            key_decisions.append(f"系统生成 Agent 卡片 {eid}: {reason}".strip())
        elif action == "final_package_build":
            key_decisions.append("系统生成 FinalPackage Markdown 报告")
        elif action == "pivot_selected":
            key_decisions.append(f"{actor} 选了 pivot 路线 {eid}")
        elif action in ("verify_evidence", "verify_project"):
            v = (e.get("after") or {}).get("verification_status") or "?"
            key_decisions.append(f"系统对 {eid} 跑验证: {v}")
        elif action in ("ref_rebuild", "ref_review"):
            key_decisions.append(f"{actor} {action} {eid}: {reason}".strip())

    # 去重保持顺序
    seen = set()
    deduped: list[str] = []
    for line in key_decisions:
        if line in seen:
            continue
        seen.add(line)
        deduped.append(line)

    return TraceSummaryResponse(
        project_id=project_id,
        user_actions=user_n,
        system_actions=system_n,
        agent_actions=agent_n,
        total=len(events),
        key_decisions=deduped[-30:],  # 最多 30 条关键决策
        last_event_ts=last_ts,
    )


# ---------- 测试用 ---------- #


def reset_traces() -> None:
    """清空所有 trace 缓存 + 删除所有 jsonl 文件."""

    global _CACHE
    with _CACHE_LOCK:
        _CACHE = {}
    td = _get_trace_dir()
    if td.exists():
        for f in td.glob("*.jsonl"):
            try:
                f.unlink()
            except OSError:
                pass


def reset_project_traces(project_id: str) -> None:
    """只清一个 project 的 trace."""

    with _CACHE_LOCK:
        _CACHE.pop(project_id, None)
    path = _jsonl_path(project_id)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
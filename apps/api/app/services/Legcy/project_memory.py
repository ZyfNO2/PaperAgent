"""Session 35: Project Memory — 项目级摘要 & 压缩.

压缩策略：
- 保留 critical 事件 (gate / user_patch / evidence_promotion / url_verified / readiness_check / llm_call)
- token_delta 合并成摘要
- card_delta 保留最终状态
- 生成 ProjectMemorySnapshot
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from ..schemas_memory import (
    CompressionConfig,
    CompressionResult,
    EvidenceMemoryEntry,
    ProjectMemorySnapshot,
    TranscriptEvent,
)
from ..schemas_run_event import RunEvent
from . import run_event as re_service


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_LOCK = threading.RLock()
_SNAPSHOTS: dict[str, list[ProjectMemorySnapshot]] = {}
_EVIDENCE_MEMORY: dict[str, dict[str, EvidenceMemoryEntry]] = {}  # project_id -> {eid: entry}
_TRANSCRIPT_CACHE: dict[str, list[TranscriptEvent]] = {}  # project_id -> events


def reset_memory_state() -> None:
    """测试用 — 清空所有记忆."""
    global _SNAPSHOTS, _EVIDENCE_MEMORY, _TRANSCRIPT_CACHE
    with _LOCK:
        _SNAPSHOTS = {}
        _EVIDENCE_MEMORY = {}
        _TRANSCRIPT_CACHE = {}


# ---------------------------------------------------------------------------
# Critical event detection
# ---------------------------------------------------------------------------


DEFAULT_CRITICAL_TYPES = {
    "user_patch",
    "gate",
    "evidence_promotion",
    "url_verified",
    "readiness_check",
    "llm_call",
}


def is_critical_event(event: RunEvent | TranscriptEvent) -> bool:
    """判断是否关键事件（不被压缩）."""
    if event.event_type in DEFAULT_CRITICAL_TYPES:
        return True
    if event.event_type.startswith("gate_") or event.event_type.startswith("user_"):
        return True
    return False


# ---------------------------------------------------------------------------
# Project Memory Snapshot
# ---------------------------------------------------------------------------


def build_snapshot_from_run(
    project_id: str,
    run_id: str,
    *,
    extra: dict[str, Any] | None = None,
) -> ProjectMemorySnapshot:
    """从 RunEvent + 额外 context 构造 ProjectMemorySnapshot."""
    events = _load_transcript(project_id, run_id)
    events_count = len(events)

    # 提取关键字段
    raw_topic = ""
    keywords = {}
    search_plan = {}
    candidate_count = 0
    paper_cand = 0
    ds_cand = 0
    repo_cand = 0
    ev_accepted = 0
    ev_core = 0
    ev_rejected = 0
    feasibility_verdict = None
    proposal_md = None
    readiness_status = None
    last_compressed_seq = 0

    # 倒序遍历 — 找每个字段最后一次写入
    for ev in reversed(events):
        et = ev.event_type
        p = ev.payload or {}
        if not raw_topic and (p.get("raw_topic") or p.get("topic")):
            raw_topic = p.get("raw_topic") or p.get("topic")
        if not keywords and p.get("confirmed_keywords"):
            keywords = p["confirmed_keywords"]
        if not search_plan and p.get("confirmed_search_plan"):
            search_plan = p["confirmed_search_plan"]
        if candidate_count == 0 and p.get("total_candidates"):
            candidate_count = int(p["total_candidates"])
        if paper_cand == 0 and p.get("paper_candidates"):
            paper_cand = int(p["paper_candidates"])
        if ds_cand == 0 and p.get("dataset_candidates"):
            ds_cand = int(p["dataset_candidates"])
        if repo_cand == 0 and p.get("repo_candidates"):
            repo_cand = int(p["repo_candidates"])
        if ev_accepted == 0 and p.get("accepted_count"):
            ev_accepted = int(p["accepted_count"])
        if ev_core == 0 and p.get("core_count"):
            ev_core = int(p["core_count"])
        if ev_rejected == 0 and p.get("rejected_count"):
            ev_rejected = int(p["rejected_count"])
        if not feasibility_verdict and p.get("verdict"):
            feasibility_verdict = p["verdict"]
        if not proposal_md and p.get("proposal_markdown"):
            proposal_md = p["proposal_markdown"]
        if not readiness_status and p.get("readiness_status"):
            readiness_status = p["readiness_status"]
        if last_compressed_seq == 0 and p.get("last_compressed_seq"):
            last_compressed_seq = int(p["last_compressed_seq"])

    md_tokens = len(proposal_md) if proposal_md else 0

    snapshot = ProjectMemorySnapshot(
        project_id=project_id,
        snapshot_id=f"snap_{uuid.uuid4().hex[:10]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        raw_topic=raw_topic,
        goal_level=(extra or {}).get("goal_level"),
        confirmed_keywords=keywords,
        confirmed_search_plan=search_plan,
        candidate_count=candidate_count,
        paper_candidates=paper_cand,
        dataset_candidates=ds_cand,
        repo_candidates=repo_cand,
        evidence_count=ev_accepted + ev_core,
        accepted_evidence=ev_accepted,
        core_evidence=ev_core,
        rejected_evidence=ev_rejected,
        feasibility_verdict=feasibility_verdict,
        proposal_markdown=proposal_md,
        proposal_markdown_tokens=md_tokens,
        last_readiness_status=readiness_status,
        compressed_event_count=events_count,
        last_compressed_seq=last_compressed_seq or events_count,
    )

    with _LOCK:
        _SNAPSHOTS.setdefault(project_id, []).append(snapshot)

    return snapshot


def get_latest_snapshot(project_id: str) -> ProjectMemorySnapshot | None:
    with _LOCK:
        snaps = _SNAPSHOTS.get(project_id, [])
        return snaps[-1] if snaps else None


def list_snapshots(project_id: str) -> list[ProjectMemorySnapshot]:
    with _LOCK:
        return list(_SNAPSHOTS.get(project_id, []))


# ---------------------------------------------------------------------------
# Evidence Memory (immutable)
# ---------------------------------------------------------------------------


def add_evidence_memory(entry: EvidenceMemoryEntry) -> None:
    """EvidenceMemory 写入 — 永远不会被普通压缩覆盖."""
    with _LOCK:
        _EVIDENCE_MEMORY.setdefault(entry.project_id, {})[entry.evidence_id] = entry


def get_evidence_memory(project_id: str, evidence_id: str) -> EvidenceMemoryEntry | None:
    with _LOCK:
        return _EVIDENCE_MEMORY.get(project_id, {}).get(evidence_id)


def list_evidence_memory(project_id: str) -> list[EvidenceMemoryEntry]:
    with _LOCK:
        return list(_EVIDENCE_MEMORY.get(project_id, {}).values())


def evidence_memory_size(project_id: str) -> int:
    with _LOCK:
        return len(_EVIDENCE_MEMORY.get(project_id, {}))


# ---------------------------------------------------------------------------
# Transcript cache + compression
# ---------------------------------------------------------------------------


def _load_transcript(project_id: str, run_id: str) -> list[TranscriptEvent]:
    """从 run_event service 加载完整 transcript."""
    cache_key = f"{project_id}::{run_id}"
    if cache_key in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[cache_key]

    # 调 run_event 的 list 函数
    try:
        events_resp = re_service.list_events(project_id, run_id)
        events = [
            TranscriptEvent(
                event_id=ev.event_id,
                seq=ev.seq,
                run_id=ev.run_id,
                project_id=ev.project_id,
                step_key=ev.step_key,
                event_type=ev.event_type,
                status=ev.status,
                payload=ev.payload,
                ts=ev.ts,
                source=ev.source,
                is_critical=is_critical_event(ev),
            )
            for ev in events_resp.events
        ]
    except Exception:
        events = []

    _TRANSCRIPT_CACHE[cache_key] = events
    return events


def clear_transcript_cache(project_id: str | None = None, run_id: str | None = None) -> None:
    if project_id is None:
        with _LOCK:
            _TRANSCRIPT_CACHE.clear()
        return
    if run_id:
        _TRANSCRIPT_CACHE.pop(f"{project_id}::{run_id}", None)


def compress_transcript(
    project_id: str,
    run_id: str,
    config: CompressionConfig | None = None,
) -> CompressionResult:
    """压缩 transcript — 保留 critical + 最近 N 个事件.

    Returns: CompressionResult with snapshot_id reference.
    """
    cfg = config or CompressionConfig()

    events = _load_transcript(project_id, run_id)
    if len(events) <= cfg.max_events_before_compress:
        # 不用压缩
        return CompressionResult(
            project_id=project_id,
            run_id=run_id,
            compressed_count=0,
            kept_critical_count=0,
            kept_recent_count=len(events),
            snapshot_id="",
            compressed_at=datetime.now(timezone.utc).isoformat(),
        )

    # 1) 关键事件全保留
    critical = [e for e in events if e.is_critical]
    # 2) 最近 N 个全保留
    recent = events[-cfg.keep_last_n :]
    # 3) 合并去重 (按 event_id)
    keep_set: dict[str, TranscriptEvent] = {}
    for e in critical + recent:
        keep_set[e.event_id] = e

    kept = list(keep_set.values())
    kept.sort(key=lambda x: x.seq)
    compressed_count = len(events) - len(kept)

    # 4) 在 transcript 中标 is_compressed
    for e in events:
        if e.event_id not in keep_set:
            e.is_compressed = True

    # 5) 触发 snapshot 重建
    snapshot = build_snapshot_from_run(project_id, run_id, extra={
        "compressed_event_count": compressed_count,
        "last_compressed_seq": events[-1].seq if events else 0,
    })

    return CompressionResult(
        project_id=project_id,
        run_id=run_id,
        compressed_count=compressed_count,
        kept_critical_count=len(critical),
        kept_recent_count=len(recent),
        snapshot_id=snapshot.snapshot_id,
        compressed_at=datetime.now(timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def replay_project(
    project_id: str,
    run_id: str | None = None,
    *,
    from_seq: int = 0,
    strategy: str = "replay",
    skip_steps: list[str] | None = None,
) -> dict:
    """Replay 项目记忆 — 恢复 step deck 状态.

    流程：
    1. 加载 ProjectMemorySnapshot（如有）
    2. 加载 from_seq 之后的 events
    3. 构造 step_states 供前端恢复
    """
    skip_set = set(skip_steps or [])
    run_id = run_id or ""

    # 1) 加载 snapshot
    snapshot = get_latest_snapshot(project_id)

    # 2) 加载 events
    recent_events: list[TranscriptEvent] = []
    step_states: dict[str, dict[str, Any]] = {}
    last_seq = 0

    if run_id:
        events = _load_transcript(project_id, run_id)
        for ev in events:
            if ev.seq < from_seq:
                continue
            if ev.step_key in skip_set:
                continue
            recent_events.append(ev)
            last_seq = max(last_seq, ev.seq)
            # 把 events 状态合并到 step_states
            if ev.step_key not in step_states:
                step_states[ev.step_key] = {}
            step_states[ev.step_key].update(ev.payload)

    # 决定 replay_source
    if snapshot and recent_events:
        replay_source = "both"
    elif snapshot:
        replay_source = "snapshot"
    else:
        replay_source = "transcript"

    return {
        "project_id": project_id,
        "run_id": run_id,
        "strategy": strategy,
        "snapshot": snapshot,
        "recent_events": recent_events,
        "step_states": step_states,
        "last_seq": last_seq,
        "replay_source": replay_source,
    }
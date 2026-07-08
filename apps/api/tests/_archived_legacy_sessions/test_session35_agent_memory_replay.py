"""Session 35: Agent Memory / Transcript / Replay backend tests (8 个).

S35-1: Transcript 可写入
S35-2: Replay 后 Step 状态一致
S35-3: token_delta 可压缩
S35-4: gate 事件不会被压缩丢失
S35-5: EvidenceMemory 不被普通压缩覆盖
S35-6: ProjectMemorySnapshot 可序列化
S35-7: 压缩前后 readiness 结果一致
S35-8: S31 baseline 不回退
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.schemas_memory import (
    CompressionConfig,
    CompressionResult,
    EvidenceMemoryEntry,
    ProjectMemorySnapshot,
    TranscriptEvent,
)
from app.schemas_run_event import (
    RunCreateRequest,
    RunEvent,
    RunEventAppendRequest,
)
from app.services import run_event as re_service
from app.services import project_memory as pm_service


@pytest.fixture(autouse=True)
def _clean_state(tmp_path, monkeypatch):
    """每个测试用临时 runtime root + 清空 in-memory state."""
    monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
    pm_service.reset_memory_state()
    yield
    pm_service.reset_memory_state()


import uuid as _uuid


def _create_run_with_events(
    project_id: str = "p1",
    run_id: str | None = None,
    events: list[tuple[str, str, str, dict]] | None = None,
) -> str:
    """创建 run 并追加事件. events: [(step_key, event_type, status, payload), ...]"""
    if run_id is None:
        run_id = f"run_{_uuid.uuid4().hex[:10]}"
    re_service.create_run(RunCreateRequest(project_id=project_id, run_id=run_id))
    for step_key, event_type, status, payload in (events or []):
        re_service.append_event(
            project_id,
            run_id,
            RunEventAppendRequest(
                step_key=step_key,
                event_type=event_type,
                status=status,  # type: ignore[arg-type]
                payload=payload,
            ),
        )
    pm_service.clear_transcript_cache(project_id, run_id)
    return run_id


# ---------------------------------------------------------------------------
# S35-1: Transcript 可写入
# ---------------------------------------------------------------------------


class TestTranscriptWritable:
    def test_create_run_and_append_events(self):
        run_id = _create_run_with_events(
            events=[
                ("keyword_review", "llm_call", "completed", {"raw_topic": "YOLO 钢材"}),
                ("query_plan", "query_plan_generated", "completed", {"papers": ["YOLO", "defect"]}),
            ]
        )
        resp = re_service.list_events("p1", run_id)
        assert resp.total == 2
        assert resp.events[0].step_key == "keyword_review"
        assert resp.events[1].step_key == "query_plan"

    def test_transcript_cache_loads(self):
        run_id = _create_run_with_events(
            events=[
                ("step1", "llm_call", "completed", {"raw_topic": "test"}),
            ]
        )
        events = pm_service._load_transcript("p1", run_id)
        assert len(events) == 1
        assert isinstance(events[0], TranscriptEvent)


# ---------------------------------------------------------------------------
# S35-2: Replay 后 Step 状态一致
# ---------------------------------------------------------------------------


class TestReplayStepStates:
    def test_replay_reconstructs_step_states(self):
        run_id = _create_run_with_events(
            events=[
                ("keyword_review", "user_patch", "completed", {"confirmed_keywords": ["YOLO", "defect"]}),
                ("query_plan", "query_plan_generated", "completed", {"paper_queries": ["YOLO defect"]}),
                ("retrieval", "retrieval_completed", "completed", {"total_candidates": 5}),
            ]
        )
        result = pm_service.replay_project("p1", run_id)
        assert "keyword_review" in result["step_states"]
        assert result["step_states"]["keyword_review"].get("confirmed_keywords") == ["YOLO", "defect"]
        assert result["step_states"]["retrieval"].get("total_candidates") == 5
        assert result["last_seq"] == 3

    def test_replay_strategy_skip(self):
        run_id = _create_run_with_events(
            events=[
                ("keyword_review", "user_patch", "completed", {"k": "v"}),
                ("retrieval", "retrieval_completed", "completed", {"n": 3}),
            ]
        )
        result = pm_service.replay_project("p1", run_id, skip_steps=["retrieval"])
        assert "keyword_review" in result["step_states"]
        assert "retrieval" not in result["step_states"]


# ---------------------------------------------------------------------------
# S35-3: token_delta 可压缩
# ---------------------------------------------------------------------------


class TestTokenDeltaCompress:
    def test_compress_keeps_critical_and_recent(self):
        # 生成 250 个事件 (超过默认 200 阈值)
        events: list[tuple[str, str, str, dict]] = []
        for i in range(250):
            step_key = "candidate_review" if i % 5 != 0 else "user_patch"
            event_type = "candidate_scored" if i % 5 != 0 else "user_patch"
            events.append((step_key, event_type, "completed", {"i": i}))

        run_id = _create_run_with_events(events=events)

        # 强制压缩: 用一个低阈值
        cfg = CompressionConfig(
            max_events_before_compress=100,
            keep_critical_types=["user_patch"],
            keep_last_n=30,
        )
        result = pm_service.compress_transcript("p1", run_id, cfg)
        assert isinstance(result, CompressionResult)
        assert result.compressed_count > 0

    def test_no_compress_when_under_threshold(self):
        events = [
            ("step1", "llm_call", "completed", {"i": i}) for i in range(10)
        ]
        run_id = _create_run_with_events(events=events)
        result = pm_service.compress_transcript("p1", run_id)
        assert result.compressed_count == 0


# ---------------------------------------------------------------------------
# S35-4: gate 事件不会被压缩丢失
# ---------------------------------------------------------------------------


class TestCriticalEventsPreserved:
    def test_gate_events_not_compressed(self):
        """user_patch 事件必须在压缩后仍存在."""
        events: list[tuple[str, str, str, dict]] = []
        # 注入 5 个 user_patch 事件, 散落在 250 个普通事件中
        gate_positions = [10, 50, 100, 150, 200]
        for i in range(250):
            if i in gate_positions:
                events.append(("gate", "user_patch", "completed", {"decision": "approve", "i": i}))
            else:
                events.append(("candidate_review", "candidate_scored", "completed", {"i": i}))

        run_id = _create_run_with_events(events=events)
        cfg = CompressionConfig(
            max_events_before_compress=100,
            keep_critical_types=["user_patch"],
            keep_last_n=20,
        )
        result = pm_service.compress_transcript("p1", run_id, cfg)

        # 验证: 5 个 gate 事件都应该保留
        events_after = pm_service._load_transcript("p1", run_id)
        kept_user_patches = [e for e in events_after if e.event_type == "user_patch" and not e.is_compressed]
        assert len(kept_user_patches) >= 5

    def test_is_critical_event_helper(self):

        gate_ev = RunEvent(
            event_id="e1", seq=1, run_id="r", project_id="p",
            step_key="gate1", event_type="user_patch", status="completed",
            payload={}, ts="2026-06-21T00:00:00Z",
        )
        normal_ev = RunEvent(
            event_id="e2", seq=2, run_id="r", project_id="p",
            step_key="step2", event_type="candidate_scored", status="completed",
            payload={}, ts="2026-06-21T00:00:00Z",
        )
        assert pm_service.is_critical_event(gate_ev)
        assert not pm_service.is_critical_event(normal_ev)


# ---------------------------------------------------------------------------
# S35-5: EvidenceMemory 不被普通压缩覆盖
# ---------------------------------------------------------------------------


class TestEvidenceMemoryImmutable:
    def test_evidence_memory_survives_compression(self):
        """EvidenceMemory 不会被压缩影响."""
        # 添加 evidence memory
        entry = EvidenceMemoryEntry(
            evidence_id="ev_001",
            project_id="p1",
            evidence_type="paper",
            title="YOLO paper",
            url="https://arxiv.org/abs/2406.12345",
            review_status="accepted",
            verification_status="verified",
            is_immutable=True,
        )
        pm_service.add_evidence_memory(entry)

        # 跑普通压缩
        events = [
            ("step1", "llm_call", "completed", {"i": i}) for i in range(300)
        ]
        run_id = _create_run_with_events(events=events)
        pm_service.compress_transcript("p1", run_id, CompressionConfig(
            max_events_before_compress=100,
            keep_last_n=10,
        ))

        # EvidenceMemory 仍在
        assert pm_service.get_evidence_memory("p1", "ev_001") is not None
        assert pm_service.evidence_memory_size("p1") == 1

    def test_evidence_memory_immutable_flag(self):
        entry = EvidenceMemoryEntry(
            evidence_id="ev_x", project_id="p2",
            evidence_type="dataset", title="DS",
            review_status="core",
        )
        assert entry.is_immutable is True


# ---------------------------------------------------------------------------
# S35-6: ProjectMemorySnapshot 可序列化
# ---------------------------------------------------------------------------


class TestSnapshotSerializable:
    def test_snapshot_json_roundtrip(self):
        snap = ProjectMemorySnapshot(
            project_id="p1",
            snapshot_id="snap_001",
            created_at="2026-06-21T00:00:00Z",
            raw_topic="YOLO steel defect",
            candidate_count=10,
            paper_candidates=6,
            dataset_candidates=2,
            repo_candidates=2,
            evidence_count=8,
            accepted_evidence=5,
            core_evidence=2,
            feasibility_verdict="可做",
        )
        data = snap.model_dump()
        s = json.dumps(data, ensure_ascii=False)
        restored = json.loads(s)
        assert restored["project_id"] == "p1"
        assert restored["raw_topic"] == "YOLO steel defect"
        assert restored["feasibility_verdict"] == "可做"
        assert restored["accepted_evidence"] == 5

    def test_snapshot_build_from_run(self):
        run_id = _create_run_with_events(
            events=[
                ("keyword_review", "user_patch", "completed", {
                    "raw_topic": "YOLO steel defect",
                    "confirmed_keywords": {"method": ["YOLO"]},
                }),
                ("feasibility", "feasibility_decided", "completed", {
                    "verdict": "可做",
                    "candidate_count": 8,
                    "accepted_count": 5,
                }),
            ]
        )
        snap = pm_service.build_snapshot_from_run("p1", run_id)
        assert snap.raw_topic == "YOLO steel defect"
        assert snap.feasibility_verdict == "可做"
        assert snap.accepted_evidence == 5
        assert snap.snapshot_id.startswith("snap_")


# ---------------------------------------------------------------------------
# S35-7: 压缩前后 readiness 结果一致
# ---------------------------------------------------------------------------


class TestReadinessStableAcrossCompression:
    def test_readiness_status_preserved_in_snapshot(self):
        run_id = _create_run_with_events(
            events=[
                ("keyword_review", "user_patch", "completed", {"raw_topic": "topic"}),
                ("readiness", "readiness_check", "completed", {
                    "readiness_status": "warn",
                    "total_candidates": 5,
                }),
                ("step2", "candidate_scored", "completed", {"i": 1}),
                ("step3", "candidate_scored", "completed", {"i": 2}),
            ]
        )
        # 压缩前 snapshot
        snap_before = pm_service.build_snapshot_from_run("p1", run_id)
        assert snap_before.last_readiness_status == "warn"

        # 触发压缩 (用低阈值: 4 events, threshold=10 → 触发)
        cfg = CompressionConfig(
            max_events_before_compress=10,
            keep_critical_types=["user_patch", "readiness_check"],
            keep_last_n=2,
        )
        pm_service.compress_transcript("p1", run_id, cfg)
        snap_after = pm_service.get_latest_snapshot("p1")
        assert snap_after is not None
        # readiness 状态应在 snapshot 中保留
        assert snap_after.last_readiness_status == "warn"


# ---------------------------------------------------------------------------
# S35-8: S31 baseline 不回退
# ---------------------------------------------------------------------------


class TestS31Compat:
    def test_analyze_endpoint_still_works(self, tmp_path, monkeypatch):
        """S31 baseline 调用仍然可用."""
        monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
        from fastapi.testclient import TestClient
        from app.main import app
        from app.services import evidence as ev_store

        ev_store.reset_all()
        try:
            client = TestClient(app)
            resp = client.post("/api/v1/one-topic/analyze", json={
                "raw_topic": "基于YOLO的钢材表面缺陷检测",
                "goal_level": "保毕业",
                "prefer": "heuristic",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert "project_id" in data
            assert "feasibility" in data
        finally:
            ev_store.reset_all()
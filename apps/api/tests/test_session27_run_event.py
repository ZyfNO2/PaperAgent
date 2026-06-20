"""Session 27: RunEvent 持久化测试 (SOP §6, 10 tests).

覆盖：
1. POST /runs 创建 run
2. POST /runs/{id}/events 追加事件
3. GET /runs/{id}/events 读取事件
4. POST /runs/{id}/resume 用户 patch
5. POST /runs/{id}/complete 标记完成
6. seq 递增
7. 不存在 run 返回 404
8. 状态正确传播
9. 用户 patch 计数
10. 大批量事件（性能冒烟）
"""

from __future__ import annotations

import json
import sys
import shutil
from pathlib import Path

import pytest

# 确保 runtime 目录独立
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas_run_event import (
    RunCreateRequest,
    RunCreateResponse,
    RunEvent,
    RunEventAppendRequest,
    RunEventAppendResponse,
    RunEventListResponse,
    RunResumeRequest,
    RunState,
)
from app.services import run_event as re_service


# ---------- fixtures ---------- #


@pytest.fixture(autouse=True)
def _use_tmp_runtime(tmp_path, monkeypatch):
    """每个测试用独立临时目录."""
    monkeypatch.setattr(re_service, "RUNTIME_ROOT", tmp_path)
    yield


@pytest.fixture()
def create_req():
    return RunCreateRequest(project_id="proj_test", run_id="run_001")


# ---------- S27-B-1: POST /runs 创建 ---------- #


class TestCreateRun:
    def test_create_run_returns_response(self, create_req):
        resp = re_service.create_run(create_req)
        assert isinstance(resp, RunCreateResponse)
        assert resp.run_id == "run_001"
        assert resp.project_id == "proj_test"
        assert resp.status == "running"
        assert "/events" in resp.events_url
        assert "/stream" in resp.stream_url

    def test_state_file_created(self, create_req):
        re_service.create_run(create_req)
        state = re_service.get_state("proj_test", "run_001")
        assert state.run_id == "run_001"
        assert state.status == "running"

    def test_events_file_created(self, create_req):
        re_service.create_run(create_req)
        ev_path = re_service._events_path("proj_test", "run_001")
        assert ev_path.exists()


# ---------- S27-B-2: POST /runs/{id}/events ---------- #


class TestAppendEvent:
    def test_append_event_returns_response(self, create_req):
        re_service.create_run(create_req)
        ev_req = RunEventAppendRequest(
            step_key="keyword_review",
            event_type="step_started",
            status="running",
            payload={"keywords": ["steel", "defect"]},
        )
        resp = re_service.append_event("proj_test", "run_001", ev_req)
        assert isinstance(resp, RunEventAppendResponse)
        assert resp.seq == 1
        assert resp.run_id == "run_001"
        assert resp.event_id.startswith("evt_")

    def test_event_persisted_in_jsonl(self, create_req):
        re_service.create_run(create_req)
        ev_req = RunEventAppendRequest(
            step_key="query_plan",
            event_type="step_completed",
            status="completed",
            payload={"queries": ["q1"]},
        )
        re_service.append_event("proj_test", "run_001", ev_req)

        ev_path = re_service._events_path("proj_test", "run_001")
        lines = [l for l in ev_path.read_text().strip().splitlines() if l.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["step_key"] == "query_plan"
        assert data["event_type"] == "step_completed"
        assert data["status"] == "completed"


# ---------- S27-B-3: GET /runs/{id}/events ---------- #


class TestGetEvents:
    def test_get_all_events(self, create_req):
        re_service.create_run(create_req)
        for i in range(3):
            re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
                step_key=f"step_{i}", event_type="test", status="running"
            ))

        result = re_service.get_events("proj_test", "run_001")
        assert result.total == 3
        assert result.last_seq == 3
        assert len(result.events) == 3
        assert result.events[0].seq == 1

    def test_get_events_from_seq(self, create_req):
        re_service.create_run(create_req)
        for i in range(5):
            re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
                step_key=f"step_{i}", event_type="test", status="running"
            ))

        result = re_service.get_events("proj_test", "run_001", from_seq=3)
        assert result.total == 2
        assert all(ev.seq > 3 for ev in result.events)


# ---------- S27-B-4: POST /runs/{id}/resume ---------- #


class TestResumeRun:
    def test_resume_appends_user_patch(self, create_req):
        re_service.create_run(create_req)
        re_service.append_user_patch(
            "proj_test", "run_001",
            {"keywords": ["updated_kw"]},
            from_seq=0,
            strategy="continue",
        )
        state = re_service.get_state("proj_test", "run_001")
        assert state.user_patches == 1

    def test_resume_strategy_recorded(self, create_req):
        re_service.create_run(create_req)
        re_service.append_user_patch(
            "proj_test", "run_001",
            {"patch": "data"},
            from_seq=5,
            strategy="replay",
        )
        patches_path = re_service._patches_path("proj_test", "run_001")
        lines = [l for l in patches_path.read_text().strip().splitlines() if l.strip()]
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["strategy"] == "replay"
        assert data["from_seq"] == 5


# ---------- S27-B-5: POST /runs/{id}/complete ---------- #


class TestCompleteRun:
    def test_complete_updates_status(self, create_req):
        re_service.create_run(create_req)
        state = re_service.update_run_status("proj_test", "run_001", "completed")
        assert state.status == "completed"
        assert state.completed_at is not None

    def test_failed_sets_completed_at(self, create_req):
        re_service.create_run(create_req)
        state = re_service.update_run_status("proj_test", "run_001", "failed")
        assert state.status == "failed"
        assert state.completed_at is not None


# ---------- S27-B-6: seq 递增 ---------- #


class TestSeqIncrement:
    def test_seq_auto_increments(self, create_req):
        re_service.create_run(create_req)
        for i in range(5):
            resp = re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
                step_key="test", event_type="test", status="running"
            ))
            assert resp.seq == i + 1

        state = re_service.get_state("proj_test", "run_001")
        assert state.last_seq == 5


# ---------- S27-B-7: 不存在 run 404 ---------- #


class TestRunNotFound:
    def test_get_events_not_found(self):
        with pytest.raises(FileNotFoundError):
            re_service.get_events("proj_test", "nonexistent")

    def test_append_event_not_found(self):
        with pytest.raises(FileNotFoundError):
            re_service.append_event("proj_test", "nonexistent", RunEventAppendRequest(
                step_key="test", event_type="test", status="running"
            ))


# ---------- S27-B-8: 状态传播 ---------- #


class TestStatusPropagation:
    def test_status_reflects_latest_event(self, create_req):
        re_service.create_run(create_req)
        re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
            step_key="test", event_type="started", status="running"
        ))
        re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
            step_key="test", event_type="completed", status="completed"
        ))
        state = re_service.get_state("proj_test", "run_001")
        assert state.status == "completed"
        assert state.last_step_key == "test"


# ---------- S27-B-9: 用户 patch 计数 ---------- #


class TestUserPatchCount:
    def test_multiple_patches_counted(self, create_req):
        re_service.create_run(create_req)
        for i in range(3):
            re_service.append_user_patch(
                "proj_test", "run_001",
                {"update": i},
                from_seq=i,
                strategy="continue",
            )
        state = re_service.get_state("proj_test", "run_001")
        assert state.user_patches == 3


# ---------- S27-B-10: 大批量事件冒烟 ---------- #


class TestBulkEvents:
    def test_100_events_persisted(self, create_req):
        re_service.create_run(create_req)
        for i in range(100):
            re_service.append_event("proj_test", "run_001", RunEventAppendRequest(
                step_key=f"step_{i % 10}",
                event_type="test",
                status="running",
                payload={"index": i},
            ))

        result = re_service.get_events("proj_test", "run_001")
        assert result.total == 100
        assert result.last_seq == 100
        # 重放 from 95
        partial = re_service.get_events("proj_test", "run_001", from_seq=95)
        assert partial.total == 5

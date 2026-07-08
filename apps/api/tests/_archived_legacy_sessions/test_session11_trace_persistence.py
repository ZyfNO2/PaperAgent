"""Session 11: Trace 持久化与操作回放 后端测试 (SOP §9.1).

覆盖:
1. append_trace 写 jsonl
2. get_trace 按 project_id 读取
3. 重启/reset 后仍可读取 (用 in-memory cache 重启模拟)
4. workspace_move 写 trace
5. card_intake_created 写 trace
6. verification_run 写 trace
7. final_package_build 写 trace
8. evidence timeline 按 evidence_id 过滤
9. trace summary 生成 key_decisions
10. trace 不改变 review_status
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import trace_store as ts


@pytest.fixture(autouse=True)
def _isolate_traces(monkeypatch):
    """每个测试用临时目录, 避免污染."""

    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_trace_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    ts.reset_traces()
    ev_store.reset_all()
    yield
    ts.reset_traces()
    # cleanup
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "YOLO 钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- 1: append_trace 写 jsonl ---------- #


def test_01_append_trace_writes_jsonl(_isolate_traces):
    """append_trace 同步写 .runtime/traces/{pid}.jsonl."""

    ev = ts.append_trace(
        project_id="ot_test_001",
        action="workspace_move",
        target_type="evidence_item",
        target_id="paper_001",
        evidence_id="paper_001",
        reason="用户移到左侧",
        actor="user",
    )
    assert ev["trace_id"].startswith("tr_")
    assert ev["project_id"] == "ot_test_001"

    # 检查 jsonl 文件存在
    jsonl = Path(os.environ["PAPERAGENT_TRACE_DIR"]) / "ot_test_001.jsonl"
    assert jsonl.exists()
    lines = jsonl.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["action"] == "workspace_move"
    assert parsed["evidence_id"] == "paper_001"


# ---------- 2: get_trace 按 project 读 ---------- #


def test_02_get_trace_filters_by_project(_isolate_traces):
    """get_trace 只返回指定 project 的事件."""

    ts.append_trace("ot_A", action="workspace_move", actor="user", evidence_id="e1")
    ts.append_trace("ot_B", action="workspace_move", actor="user", evidence_id="e2")
    ts.append_trace("ot_A", action="verification_run", actor="system", evidence_id="e1")

    resp = ts.get_trace("ot_A", limit=50)
    assert resp.total == 2
    assert all(e.project_id == "ot_A" for e in resp.events)

    resp_b = ts.get_trace("ot_B")
    assert resp_b.total == 1
    assert resp_b.events[0].evidence_id == "e2"


# ---------- 3: reset 后仍可读 (持久化) ---------- #


def test_03_persistence_after_reset(_isolate_traces):
    """清空 in-memory 缓存后, jsonl 仍可读."""

    ts.append_trace("ot_persist", action="manual_verification", actor="user", evidence_id="e1", reason="x")
    ts.append_trace("ot_persist", action="workspace_move", actor="user", evidence_id="e2", reason="y")
    # 清缓存 (不删 jsonl)
    ts._CACHE.clear()
    # 再次读
    resp = ts.get_trace("ot_persist")
    assert resp.total == 2
    # 旧 in-memory 缓存不影响 jsonl 读取
    actions = [e.action for e in resp.events]
    assert "manual_verification" in actions
    assert "workspace_move" in actions


# ---------- 4: workspace_move 写 trace ---------- #


def test_04_workspace_patch_writes_trace(client):
    """PATCH /workspace/item 触发 workspace_patch trace."""

    pid = _analyze(client)

    # 加一个 paper evidence
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "p1", "url": "https://arxiv.org/abs/2106.09685", "arxiv_id": "2106.09685",
    })
    assert r.status_code == 200
    eid = r.json()["evidence_id"]

    # 移动到 selected (mark_core)
    r = client.patch(
        f"/api/v1/one-topic/{pid}/workspace/item",
        json={"evidence_id": eid, "workspace_lane": "selected", "review_status": "core",
              "reason": "用户标核心"},
    )
    assert r.status_code == 200

    # 查 trace
    resp = ts.get_trace(pid)
    actions = [e.action for e in resp.events]
    assert "workspace_patch" in actions, f"应有 workspace_patch, 实际 actions: {actions}"


# ---------- 5: card_intake_created 写 trace ---------- #


def test_05_card_intake_writes_trace(client):
    """POST /cards/intake 写 card_intake_created trace."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/cards/intake", json={
        "input_type": "url",
        "content": "https://github.com/test/repo",
        "hint": None,
        "target_lane": "user_preferred",
    })
    assert r.status_code == 200

    resp = ts.get_trace(pid)
    actions = [e.action for e in resp.events]
    assert "card_intake_created" in actions, f"应有 card_intake_created, 实际 actions: {actions}"


# ---------- 6: verification_run 写 trace ---------- #


def test_06_verification_writes_trace(client):
    """POST /evidence/{id}/verify 写 verify_evidence trace."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json={
        "name": "o/r", "repository_url": "https://github.com/o/r",
    })
    eid = r.json()["evidence_id"]
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    assert r.status_code == 200

    resp = ts.get_trace(pid)
    actions = [e.action for e in resp.events]
    assert "verify_evidence" in actions, f"应有 verify_evidence, 实际 actions: {actions}"


# ---------- 7: final_package_build 写 trace ---------- #


def test_07_final_package_build_writes_trace(client):
    """POST /final-package/build 写 final_package_build trace."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r.status_code == 200

    resp = ts.get_trace(pid)
    actions = [e.action for e in resp.events]
    assert "final_package_build" in actions, f"应有 final_package_build, 实际 actions: {actions}"


# ---------- 8: timeline 按 evidence_id 过滤 ---------- #


def test_08_timeline_by_evidence_id(_isolate_traces):
    """timeline 只返回该 evidence_id 的事件."""

    ts.append_trace("ot_t", action="workspace_move", evidence_id="paper_A", reason="r1", actor="user")
    ts.append_trace("ot_t", action="verification_run", evidence_id="paper_A", reason="r2", actor="system")
    ts.append_trace("ot_t", action="workspace_move", evidence_id="paper_B", reason="r3", actor="user")

    tl = ts.get_evidence_timeline("ot_t", "paper_A")
    assert len(tl) == 2
    assert all(e.evidence_id == "paper_A" for e in tl)

    tl_b = ts.get_evidence_timeline("ot_t", "paper_B")
    assert len(tl_b) == 1
    assert tl_b[0].reason == "r3"


# ---------- 9: summary 生成 key_decisions ---------- #


def test_09_summary_key_decisions(_isolate_traces):
    """trace summary 应生成 user_actions / system_actions / key_decisions."""

    # user: 移 + 标核心 + 手动验证
    ts.append_trace("ot_s", action="workspace_patch", actor="user", evidence_id="e1",
                    reason="加入左侧", before={"workspace_lane": "system_found"}, after={"workspace_lane": "user_preferred"})
    ts.append_trace("ot_s", action="manual_verification", actor="user", evidence_id="e3",
                    after={"verification_status": "verified"})
    # system: 验证 + FinalPackage
    ts.append_trace("ot_s", action="verify_evidence", actor="system", evidence_id="e1",
                    after={"verification_status": "partial"})
    ts.append_trace("ot_s", action="final_package_build", actor="system")

    summary = ts.get_trace_summary("ot_s")
    assert summary.user_actions == 2
    assert summary.system_actions == 2
    assert summary.total == 4
    assert len(summary.key_decisions) >= 3
    text = " ".join(summary.key_decisions)
    assert "e1" in text or "e3" in text


# ---------- 10: trace 不改 review_status ---------- #


def test_10_trace_does_not_change_review_status(client):
    """trace 只记录, 不修改 evidence 的 review_status."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "p", "url": "https://arxiv.org/abs/2106.09685", "review_status": "accepted",
    })
    eid = r.json()["evidence_id"]

    # 跑几次 trace 触发动作
    client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    client.patch(f"/api/v1/one-topic/{pid}/workspace/item",
                 json={"evidence_id": eid, "workspace_lane": "selected", "review_status": "core"})

    # review_status 应保持 core
    item = ev_store.get_item(eid)
    assert item.review_status == "core"


# ---------- 额外: GET API 端点 ---------- #


def test_11_get_trace_api(client):
    """GET /api/v1/one-topic/{pid}/trace 返回 TraceListResponse."""

    pid = _analyze(client)
    r = client.get(f"/api/v1/one-topic/{pid}/trace?limit=10")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == pid
    assert "events" in body
    assert "total" in body


def test_12_get_timeline_api(client):
    """GET /api/v1/one-topic/{pid}/evidence/{eid}/timeline 返回 TraceTimelineResponse."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "p", "url": "https://arxiv.org/abs/2106.09685",
    })
    eid = r.json()["evidence_id"]
    client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/{eid}/timeline")
    assert r.status_code == 200
    body = r.json()
    assert body["evidence_id"] == eid
    assert len(body["events"]) >= 1


def test_13_get_trace_summary_api(client):
    """GET /api/v1/one-topic/{pid}/trace/summary 返回 TraceSummaryResponse."""

    pid = _analyze(client)
    r = client.get(f"/api/v1/one-topic/{pid}/trace/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert "user_actions" in body
    assert "system_actions" in body
    assert "key_decisions" in body
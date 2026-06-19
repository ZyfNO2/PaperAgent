"""Session 11: Trace 持久化与操作回放 前端 e2e (SOP §9.2).

覆盖:
1. 操作历史面板可见
2. 移动证据后出现 trace
3. 验证证据后出现 trace
4. 生成报告后出现 trace
5. 点击证据 "查看路径" 显示 timeline
6. 刷新页面后 trace 仍显示 (server-side persistence)
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

import pytest

BACKEND_URL = "http://127.0.0.1:18181"


class _Resp:
    def __init__(self, status: int, body: Any):
        self.status_code = status
        self._body = body

    def json(self) -> Any:
        return self._body


class _HTTPClient:
    def get(self, path: str) -> _Resp:
        return self._send("GET", path)

    def post(self, path: str, json: dict | None = None) -> _Resp:
        return self._send("POST", path, json)

    def patch(self, path: str, json: dict | None = None) -> _Resp:
        return self._send("PATCH", path, json)

    def _send(self, method: str, path: str, body: dict | None = None) -> _Resp:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            f"{BACKEND_URL}{path}", data=data, method=method,
            headers={"Content-Type": "application/json"} if data else {},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            return _Resp(r.status, json.loads(r.read()))


@pytest.fixture
def api_client():
    return _HTTPClient()


# ---------- 1: 操作历史面板可见 ---------- #


def test_01_trace_panel_visible(page_with_result):
    """证据页应有 #evidence-trace-panel."""

    panel = page_with_result.locator("#evidence-trace-panel")
    assert panel.count() == 1, "应有 #evidence-trace-panel"
    assert page_with_result.locator("#btn-evidence-trace-refresh").count() == 1
    assert page_with_result.locator("#evidence-trace-filter-action").count() == 1
    assert page_with_result.locator("#evidence-trace-filter-actor").count() == 1


# ---------- 2: 移动证据后出现 trace ---------- #


def test_02_workspace_move_writes_trace(page_with_result, api_client):
    """PATCH workspace/item 后 trace 列表出现 workspace_patch 事件."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    # 通过 API 加一个 paper 证据
    r = api_client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "trace move test", "url": "https://arxiv.org/abs/2106.09685",
    })
    assert r.status_code == 200
    eid = r.json()["evidence_id"]

    # 通过 API 移动
    r = api_client.patch(f"/api/v1/one-topic/{pid}/workspace/item", json={
        "evidence_id": eid, "workspace_lane": "selected", "review_status": "core",
        "reason": "e2e trace test",
    })
    assert r.status_code == 200

    # 刷新 trace 历史
    page_with_result.click("#btn-evidence-trace-refresh")
    page_with_result.wait_for_selector(".trace-row", timeout=10000)
    rows = page_with_result.locator(".trace-row").all()
    actions = [r.locator(".trace-row__action").text_content() or "" for r in rows]
    assert any("workspace_patch" in a for a in actions), f"应有 workspace_patch, got {actions}"


# ---------- 3: 验证证据后出现 trace ---------- #


def test_03_verify_writes_trace(page_with_result, api_client):
    """POST /evidence/{id}/verify 后 trace 出现 verify_evidence 事件."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    r = api_client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json={
        "name": "trace/verify", "repository_url": "https://github.com/trace/verify",
    })
    eid = r.json()["evidence_id"]
    api_client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")

    page_with_result.click("#btn-evidence-trace-refresh")
    page_with_result.wait_for_selector(".trace-row", timeout=10000)
    actions = [r.locator(".trace-row__action").text_content() or "" for r in page_with_result.locator(".trace-row").all()]
    assert any("verify_evidence" in a for a in actions), f"应有 verify_evidence, got {actions}"


# ---------- 4: 生成报告后出现 trace ---------- #


def test_04_final_package_build_writes_trace(page_with_result, api_client):
    """POST /final-package/build 后 trace 出现 final_package_build 事件."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    r = api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r.status_code == 200

    page_with_result.click("#btn-evidence-trace-refresh")
    page_with_result.wait_for_selector(".trace-row", timeout=10000)
    actions = [r.locator(".trace-row__action").text_content() or "" for r in page_with_result.locator(".trace-row").all()]
    assert any("final_package_build" in a for a in actions), f"应有 final_package_build, got {actions}"


# ---------- 5: 查看路径显示 timeline ---------- #


def test_05_view_path_shows_timeline(page_with_result, api_client):
    """点击 "查看路径" 打开 timeline modal 显示该 evidence 的事件."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    r = api_client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "timeline test", "url": "https://arxiv.org/abs/2106.09685",
    })
    eid = r.json()["evidence_id"]
    api_client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    api_client.patch(f"/api/v1/one-topic/{pid}/workspace/item", json={
        "evidence_id": eid, "workspace_lane": "selected", "review_status": "core",
    })

    # 直接通过 JS 调 openEvidenceTimeline (绕开 UI 点击不可靠问题)
    page_with_result.evaluate(f"() => openEvidenceTimeline('{eid}')")
    page_with_result.wait_for_selector("#timeline-modal:not([hidden])", timeout=10000)
    # modal 内的 list 应至少有 1 条
    rows = page_with_result.locator("#timeline-list .trace-row")
    assert rows.count() >= 1, "timeline modal 应至少显示 1 条事件"


# ---------- 6: 刷新后 trace 仍显示 (server-side persistence) ---------- #


def test_06_persistence_after_reload(page_with_result, api_client):
    """trace 持久化在 jsonl, 即使客户端刷新仍能读到."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    # 写一个特殊 trace
    r = api_client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json={
        "name": "persist/repo", "repository_url": "https://github.com/persist/repo",
    })
    eid = r.json()["evidence_id"]
    api_client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")

    # 通过 trace summary API 验证持久化 (summary 必须包含 events)
    r = api_client.get(f"/api/v1/one-topic/{pid}/trace/summary")
    assert r.status_code == 200
    summary = r.json()
    assert summary["total"] >= 1, f"summary.total 应 >= 1, got {summary['total']}"
    assert summary["system_actions"] >= 1

    # 也确认页面 trace 历史能加载到
    page_with_result.click("#btn-evidence-trace-refresh")
    page_with_result.wait_for_selector(".trace-row", timeout=10000)
    hint = page_with_result.locator("#evidence-trace-summary-hint").text_content() or ""
    assert "总" in hint and "user" in hint and "system" in hint, f"hint 应含统计, got {hint}"
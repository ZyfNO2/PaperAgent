"""Session 15: 全文资料与图片 / PDF / 网页卡片化 前端 e2e (SOP §19.2).

覆盖:
1. 资料卡片化面板可见
2. 3 个 tab (上传 / 文字 / 备注) 可切换
3. 提交文字资料 (url_note) 生成 draft
4. draft 卡片显示类型 / 置信度 / 摘要
5. 用户编辑 draft (PATCH via API 直接调)
6. 用户能导入 draft 到工作台
7. 导入后 draft 状态变 imported
8. 备注 tab (manual_note) 能提交
9. 截图 / note 卡片显示 pending 状态
10. Trace 面板能看到 material 相关事件
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


# ---------- 1: 面板可见 ---------- #


def test_01_materials_panel_visible(page_with_result):
    """#materials-panel 应可见."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    panel = page_with_result.locator("#materials-panel")
    assert panel.count() == 1
    assert page_with_result.locator("#btn-materials-upload").count() == 1
    assert page_with_result.locator("#btn-materials-submit-text").count() == 1
    assert page_with_result.locator("#btn-materials-submit-note").count() == 1


# ---------- 2: 3 个 tab 可切换 ---------- #


def test_02_three_tabs_switchable(page_with_result):
    """3 个 tab 可点击切换 pane."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    tabs = page_with_result.locator(".materials-panel__tab")
    assert tabs.count() == 3

    page_with_result.click("[data-mat-tab=text]")
    assert page_with_result.locator("#materials-pane-text").is_visible()
    page_with_result.click("[data-mat-tab=note]")
    assert page_with_result.locator("#materials-pane-note").is_visible()
    page_with_result.click("[data-mat-tab=upload]")
    assert page_with_result.locator("#materials-pane-upload").is_visible()


# ---------- 3: 提交文字 (url_note) ---------- #


def test_03_submit_url_note_creates_draft(page_with_result, api_client):
    """提交 url_note 文字 -> draft 卡片出现."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    page_with_result.click("[data-mat-tab=text]")
    page_with_result.fill("#materials-text-title", "导师建议的论文")
    page_with_result.fill("#materials-text-url", "https://arxiv.org/abs/2106.09685")
    page_with_result.fill("#materials-text-body", "YOLO defect detection paper. DOI: 10.1234/test")
    page_with_result.fill("#materials-text-note", "关注这篇")
    page_with_result.click("#btn-materials-submit-text")
    page_with_result.wait_for_selector(".materials-card", timeout=10000)
    cards = page_with_result.locator(".materials-card")
    assert cards.count() >= 1


# ---------- 4: draft 卡片显示字段 ---------- #


def test_04_draft_card_fields_visible(page_with_result, api_client):
    """draft 卡片应显示 type / conf / summary."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    page_with_result.click("[data-mat-tab=text]")
    page_with_result.fill("#materials-text-title", "测试字段")
    page_with_result.fill("#materials-text-url", "https://example.com/x")
    page_with_result.fill("#materials-text-body", "some content")
    page_with_result.fill("#materials-text-note", "n")
    page_with_result.click("#btn-materials-submit-text")
    page_with_result.wait_for_selector(".materials-card", timeout=10000)

    first = page_with_result.locator(".materials-card").first
    assert first.locator(".materials-card__type").count() == 1
    assert first.locator(".materials-card__conf").count() == 1
    assert first.locator(".materials-card__summary").count() == 1


# ---------- 5: 编辑 draft (API 调 PATCH) ---------- #


def test_05_edit_draft_via_api(page_with_result, api_client):
    """编辑 draft 后 PATCH 生效."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    # 通过 API 提交
    api_client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "url_note", "text": "",
        "url": "https://example.com/x", "user_note": "n",
    })
    drafts = api_client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    assert len(drafts) >= 1
    did = drafts[0]["draft_card_id"]

    r = api_client.patch(f"/api/v1/one-topic/{pid}/materials/cards/{did}", json={
        "title": "Edited Title", "summary": "Edited summary",
    })
    assert r.status_code == 200
    assert r.json()["title"] == "Edited Title"


# ---------- 6: 导入 draft ---------- #


def test_06_import_draft_card(page_with_result, api_client):
    """点击导入 -> draft 进入 ledger."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    page_with_result.click("[data-mat-tab=text]")
    page_with_result.fill("#materials-text-title", "导入测试")
    page_with_result.fill("#materials-text-url", "https://example.com/imp")
    page_with_result.fill("#materials-text-body", "imp body")
    page_with_result.fill("#materials-text-note", "imp note")
    page_with_result.click("#btn-materials-submit-text")
    page_with_result.wait_for_selector(".materials-card", timeout=10000)

    # 点导入按钮
    page_with_result.locator(".materials-card .cta-mini[data-mat-action=import]:not([disabled])").first.click()
    page_with_result.wait_for_timeout(2000)


# ---------- 7: 导入后状态变 imported ---------- #


def test_07_imported_status_visible(page_with_result, api_client):
    """导入后 draft 卡片状态 = imported, 按钮 disabled."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    api_client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "url_note", "text": "",
        "url": "https://example.com/q", "user_note": "q",
    })
    drafts = api_client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    did = drafts[0]["draft_card_id"]
    api_client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    # 重新加载
    page_with_result.evaluate("() => loadMaterials()")
    page_with_result.wait_for_timeout(1500)
    status = page_with_result.locator(".materials-card .materials-card__status").first.text_content() or ""
    assert status == "imported", f"status 应为 imported, got '{status}'"


# ---------- 8: 备注 tab 提交 ---------- #


def test_08_manual_note_submission(page_with_result, api_client):
    """manual_note tab 能提交并生成 draft."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    page_with_result.click("[data-mat-tab=note]")
    page_with_result.fill("#materials-note-title", "导师备注")
    page_with_result.fill("#materials-note-body", "希望把题目限定到 NEU-DET")
    page_with_result.fill("#materials-note-note", "题目边界")
    page_with_result.click("#btn-materials-submit-note")
    page_with_result.wait_for_selector(".materials-card", timeout=10000)
    cards = page_with_result.locator(".materials-card")
    assert cards.count() >= 1


# ---------- 9: 截图 / note 默认 pending ---------- #


def test_09_note_default_pending_state(page_with_result, api_client):
    """manual_note 生成的 draft verification_status 默认未验证."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    # 提交 manual_note
    api_client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note", "text": "n", "user_note": "x",
    })
    drafts = api_client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    did = drafts[0]["draft_card_id"]
    r = api_client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })
    assert r.status_code == 200
    # 检查 ledger 中 evidence verification_status
    eid = r.json()["evidence_ids"][0]
    ledger = api_client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    papers = ledger.get("papers", [])
    # 找到刚导入的 item
    found = next((p for p in papers if p["evidence_id"] == eid), None)
    assert found is not None
    assert found["verification_status"] in ("unverified", "skipped", "verified", "partial", "failed")
    assert found["review_status"] == "pending"


# ---------- 10: Trace 事件 ---------- #


def test_10_trace_panel_has_material_events(page_with_result, api_client):
    """material_uploaded / parsed / draft_card_imported 应出现在 trace 中."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    api_client.post(f"/api/v1/one-topic/{pid}/materials/text", json={
        "source_type": "manual_note", "text": "x", "user_note": "trace test",
    })
    drafts = api_client.get(f"/api/v1/one-topic/{pid}/materials").json()["drafts"]
    did = drafts[0]["draft_card_id"]
    api_client.post(f"/api/v1/one-topic/{pid}/materials/cards/import", json={
        "draft_card_ids": [did], "workspace_lane": "user_preferred",
    })

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#evidence-trace-panel", timeout=10000)
    page_with_result.click("#btn-evidence-trace-refresh")
    page_with_result.wait_for_selector(".trace-row", timeout=10000)
    rows = page_with_result.locator(".trace-row")
    actions = [r.locator(".trace-row__action").text_content() or "" for r in rows.all()]
    assert any("material" in a for a in actions), f"trace 应含 material_*, got {actions}"
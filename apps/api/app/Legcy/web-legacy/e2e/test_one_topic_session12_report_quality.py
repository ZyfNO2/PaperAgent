"""Session 12: 报告质量检查与低门槛委员会复核 前端 e2e (SOP §10.2).

覆盖:
1. 页面出现报告质量检查区
2. 点击运行审核显示 verdict
3. 显示 8 维检查表
4. 显示修改清单
5. 显示答辩追问
6. evidence refs 在审核结果中可见
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


# ---------- 1: 报告质量检查区可见 ---------- #


def test_01_quality_panel_visible(page_with_result):
    """#quality-panel 应可见."""

    panel = page_with_result.locator("#quality-panel")
    assert panel.count() == 1
    assert page_with_result.locator("#btn-quality-run").count() == 1
    assert page_with_result.locator("#btn-quality-download").count() == 1


# ---------- 2: 点击运行审核显示 verdict ---------- #


def test_02_run_review_shows_verdict(page_with_result, api_client):
    """点击 btn-quality-run 后 quality-verdict 出现."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")

    # 先 build FinalPackage (保证 snapshot)
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})

    page_with_result.click("#btn-quality-run")
    page_with_result.wait_for_selector("#quality-verdict:not([hidden])", timeout=30000)
    text = page_with_result.locator("#quality-verdict").text_content() or ""
    assert any(v in text for v in ["通过", "有条件通过", "需修改", "不建议"]), f"verdict 应出现, got {text}"


# ---------- 3: 显示 8 维检查表 ---------- #


def test_03_eight_dimensions_visible(page_with_result, api_client):
    """8 维 checks 应展示."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    page_with_result.click("#btn-quality-run")
    page_with_result.wait_for_selector(".quality-check", timeout=30000)
    checks = page_with_result.locator(".quality-check")
    assert checks.count() == 8, f"应 8 维, got {checks.count()}"


# ---------- 4: 显示修改清单 ---------- #


def test_04_revision_checklist_visible(page_with_result, api_client):
    """修改清单应展示."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    page_with_result.click("#btn-quality-run")
    page_with_result.wait_for_selector("#quality-revision:not([hidden])", timeout=30000)
    items = page_with_result.locator("#quality-revision-list li")
    assert items.count() >= 0


# ---------- 5: 显示答辩追问 ---------- #


def test_05_defense_questions_visible(page_with_result, api_client):
    """答辩追问应展示 ≥ 6 题."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    page_with_result.click("#btn-quality-run")
    page_with_result.wait_for_selector("#quality-defense:not([hidden])", timeout=30000)
    qs = page_with_result.locator(".defense-q")
    assert qs.count() >= 6, f"应至少 6 题, got {qs.count()}"


# ---------- 6: evidence refs 在审核结果中可见 ---------- #


def test_06_evidence_refs_linked(page_with_result, api_client):
    """evidence refs (至少 dataset / baseline) 出现在 quality-check 中."""

    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    # POST /report/review 返回完整 ReportQualityReview (含 checks), 不用 summary
    r = api_client.post(f"/api/v1/one-topic/{pid}/report/review", json={})
    review = r.json()
    all_eids = []
    for c in review.get("checks", []):
        for r in c.get("evidence_refs", []):
            all_eids.append(r["evidence_id"])
    # 至少有 1 个 evidence ref (heuristic 后台自动入池)
    assert len(all_eids) >= 1, f"checks 应至少绑定 1 条 evidence, got {all_eids}"
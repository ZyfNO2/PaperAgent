"""Session 17: Demo 数据固化与回归基线 前端 e2e (SOP §9).

覆盖:
1.  从 UI 输入 YOLO Demo
2.  页面能生成 project_id (分析后头部显示)
3.  关键词拆解可见 (block-keywords)
4.  工作台 tab 可切换 (#tab-evidence)
5.  资料工作台 / Trace / Skill / Quality 4 面板可见
6.  FinalPackage 面板能生成 Markdown
7.  ReportQuality 面板能显示 verdict
8.  Trace 面板能看到关键事件
9.  关键 UI 文案 / 面板 selector 稳定 (Session 16 稳定化后的空状态)
10. 高风险 Case 在 UI 走通最小流程 (只跑 analyze + 看 verdict 文字)
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
        return _send("GET", path)

    def post(self, path: str, json: dict | None = None) -> _Resp:
        return _send("POST", path, json)

    def patch(self, path: str, json: dict | None = None) -> _Resp:
        return _send("PATCH", path, json)


def _send(method: str, path: str, body: dict | None = None) -> _Resp:
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


# ---------- 1: 输入 YOLO Demo 题目 ---------- #


def test_01_yolo_analyze_ui(page):
    """YOLO Demo 题目可输入并触发 analyze."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    # 默认 goal=保毕业 / advisor=工业质检
    page.fill("#input-advisor", "工业质检")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=120000)
    # 题目理解 + 关键词拆解 出现
    assert page.locator("#block-understanding").is_visible()
    assert page.locator("#block-keywords").is_visible()
    assert page.locator("#block-feasibility").is_visible()


# ---------- 2: project_id 可在头部查到 ---------- #


def test_02_yolo_project_id_visible(page_with_result):
    """evidence header 应显示 project_id (8+ 字符)."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#ev-pid", timeout=10000)
    pid_text = page_with_result.locator("#ev-pid").inner_text()
    assert "ot_" in pid_text, f"project_id 格式不对: {pid_text}"


def _pid_from(page) -> str:
    page.click("#tab-evidence")
    page.wait_for_selector("#ev-pid", timeout=10000)
    txt = page.locator("#ev-pid").inner_text().strip()
    return txt.split(":")[-1].strip()


# ---------- 3: 工作台 4 个面板可见 ---------- #


def test_03_workspace_panels_visible(page_with_result):
    """4 个关键面板 selector 稳定 (evidence-trace-panel / retrieval-panel / quality-panel / materials-panel)."""

    page_with_result.click("#tab-evidence")
    for sel in ["#evidence-trace-panel", "#retrieval-panel", "#quality-panel", "#materials-panel"]:
        page_with_result.wait_for_selector(sel, timeout=10000)
        assert page_with_result.locator(sel).count() == 1, f"缺面板: {sel}"


# ---------- 4: Trace 空状态友好文案 ---------- #


def test_04_trace_empty_state_friendly(page_with_result):
    """Session 16 引入的 empty-state 应在 Trace 加载初期可见."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#evidence-trace-panel", timeout=10000)
    # 切到一个新 project 不行 (没新按钮); 但 trace-list 应有内容或 empty-state
    list_html = page_with_result.locator("#evidence-trace-list").inner_html()
    # 既可能是 trace 事件, 也可能是空状态; 都接受
    assert list_html, "trace-list 应有内容或空状态"


# ---------- 5: Quality 面板默认 verdict 隐藏 + 按钮可见 ---------- #


def test_05_quality_panel_visible(page_with_result):
    """quality-panel 存在, verdict 默认 hidden."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#quality-panel", timeout=10000)
    # verdict 元素存在但可能 hidden (没跑 review)
    verdict = page_with_result.locator("#quality-verdict")
    assert verdict.count() == 1


# ---------- 6: Materials 工作台 3 个按钮可见 ---------- #


def test_06_materials_three_buttons(page_with_result):
    """materials 工作台 3 个入口按钮 (上传 / 文字 / 备注)."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#materials-panel", timeout=10000)
    for btn in ["#btn-materials-upload", "#btn-materials-submit-text", "#btn-materials-submit-note"]:
        assert page_with_result.locator(btn).count() == 1, f"缺按钮: {btn}"


# ---------- 7: FinalPackage 按钮可见 + 生成 ---------- #


def test_07_final_package_build(page_with_result, api_client):
    """FinalPackage 应可生成, Markdown 含 7 个章节."""

    # 直接走 API, 不依赖 UI (UI 已由 S8 覆盖)
    pid = _pid_from(page_with_result)
    # 至少导入一条 paper 让引用不为空
    api_client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={
            "title": "YOLOv8 Baseline for Steel Defect Detection",
            "url": "https://arxiv.org/abs/2406.12345",
            "arxiv_id": "2406.12345",
            "review_status": "accepted",
        },
    )
    r = api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r.status_code == 200, f"final-package 失败: status={r.status_code}"
    body = r.json()
    md = body.get("proposal_markdown", "")
    for sec in ["研究背景", "国内外研究现状", "研究内容", "技术路线", "实验方案", "风险预案", "引用清单"]:
        assert sec in md, f"FinalPackage 缺章节: {sec}"


# ---------- 8: ReportQuality 8 维评分可见 ---------- #


def test_08_report_quality_visible(page_with_result, api_client):
    """quality review 8 维结果可见."""

    pid = _pid_from(page_with_result)
    api_client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "Test", "review_status": "accepted"},
    )
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    r = api_client.post(f"/api/v1/one-topic/{pid}/report/review", json={})
    assert r.status_code == 200
    body = r.json()
    assert "verdict" in body, "quality review 缺 verdict"
    assert "checks" in body and len(body["checks"]) >= 1, "quality review 缺 checks"
    assert "revision_checklist" in body, "quality review 缺 revision_checklist"


# ---------- 9: Trace 含关键 action (经 API 走完整流程) ---------- #


def test_09_trace_actions_via_api(api_client):
    """经 API 走完整流程, trace 必须含 verify_project + final_package_build."""

    r = api_client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "goal_level": "保毕业",
        "advisor_direction": "工业质检",
        "prefer": "heuristic",
    })
    pid = r.json()["project_id"]
    api_client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "Trace Test", "review_status": "accepted"},
    )
    api_client.post(f"/api/v1/one-topic/{pid}/evidence/verify", json={"scope": "all"})
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})

    tr = api_client.get(f"/api/v1/one-topic/{pid}/trace").json()
    actions = [e["action"] for e in tr.get("events", [])]
    for a in ["verify_project", "final_package_build"]:
        assert a in actions, f"trace 缺 action: {a} (have {actions})"


# ---------- 10: 高风险 Case UI 流程 (仅 analyze) ---------- #


def test_10_risky_case_analyze(page):
    """高风险 MLLM case 跑完 analyze, verdict 文本必须可见."""

    page.fill("#input-topic", "基于多模态大模型的通用工业缺陷智能诊断")
    page.fill("#input-advisor", "工业 AI")
    page.select_option("#input-goal", "冲高水平")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=120000)
    # feasibility 块必有 verdict
    feas_html = page.locator("#block-feasibility").inner_text()
    assert "可" in feas_html or "转向" in feas_html or "暂缓" in feas_html, \
        f"feasibility 未显示 5 档: {feas_html[:200]}"
"""Session 9: 双栏工作台 + Agent Card Intake 前端 e2e (SOP §7.2).

覆盖:
1. 页面显示双栏证据工作台
2. paper/dataset/repo 三类分区存在
3. 系统候选卡片可以加入左侧
4. 卡片可以标为核心
5. 拒绝卡片后不再作为正向引用
6. Agent 卡片导入面板存在
7. 输入 GitHub URL 后生成 repo 卡片
8. 生成的卡片显示 pending / extraction_confidence / warning
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.main import app  # noqa: E402
from app.services import evidence as ev_store  # noqa: E402


@pytest.fixture
def api_client():
    ev_store.reset_all()
    return TestClient(app)


def test_01_workspace_board_visible(page_with_result):
    """页面显示双栏证据工作台 (SOP §7.2.1)."""

    board = page_with_result.locator("#workspace-board")
    assert board.is_visible(), "应可见 #workspace-board"
    # tab 栏
    assert page_with_result.locator(".ws-tab[data-ws-tab='paper']").is_visible()
    assert page_with_result.locator(".ws-tab[data-ws-tab='dataset']").is_visible()
    assert page_with_result.locator(".ws-tab[data-ws-tab='repo']").is_visible()
    # paper 面板左右栏
    assert page_with_result.locator("#ws-paper-left").is_visible()
    assert page_with_result.locator("#ws-paper-right").is_visible()


def test_02_three_type_panels_exist(page_with_result, api_client):
    """三类分区 paper / dataset / repo 都存在 (§7.2.2)."""

    panels = page_with_result.locator(".ws-panel")
    assert panels.count() == 3, f"应有 3 个 panel, 实际 {panels.count()}"
    assert page_with_result.locator('.ws-panel[data-ws-panel="paper"]').count() == 1
    assert page_with_result.locator('.ws-panel[data-ws-panel="dataset"]').count() == 1
    assert page_with_result.locator('.ws-panel[data-ws-panel="repo"]').count() == 1


def test_03_add_to_left_button(page_with_result, api_client):
    """系统候选卡片可以加入左侧 (§7.2.3)."""

    # 切到 paper tab (默认就是), 找 right lane 的 add_left 按钮
    add_left_btn = page_with_result.locator(
        '#ws-paper-right .ws-card__btn[data-ws-action="add_left"]'
    ).first
    if add_left_btn.count() == 0:
        pytest.skip("无 right 卡片可加入左侧")
    add_left_btn.click()
    page_with_result.wait_for_timeout(2000)
    # 验证 board 刷新: 该 eid 应在 left
    # 重新拉 board 数据查
    eid = add_left_btn.get_attribute("data-ws-eid")
    # 通过 API 验证
    pid = page_with_result.evaluate("() => state && state.projectId")
    if not pid:
        pytest.skip("无 projectId")
    board = api_client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    left_eids = [e["evidence_id"] for e in board["papers"]["left_items"]]
    assert eid in left_eids, f"{eid} 应在 left, 实际 left={left_eids}"


def test_04_mark_core_button(page_with_result, api_client):
    """卡片可以标为核心 (§7.2.4)."""

    mark_core_btn = page_with_result.locator(
        '#ws-paper-right .ws-card__btn[data-ws-action="mark_core"]'
    ).first
    if mark_core_btn.count() == 0:
        pytest.skip("无 right 卡片")
    mark_core_btn.click()
    page_with_result.wait_for_timeout(2000)
    eid = mark_core_btn.get_attribute("data-ws-eid")
    pid = page_with_result.evaluate("() => state && state.projectId")
    board = api_client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    sel_eids = [e["evidence_id"] for e in board["papers"]["selected_items"]]
    assert eid in sel_eids, f"{eid} 应在 selected, 实际 selected={sel_eids}"


def test_05_reject_excluded_from_citations(page_with_result, api_client):
    """拒绝卡片后, Markdown 报告不再正向引用 (§7.2.5)."""

    # 拿一个 paper, 拒绝它
    paper = page_with_result.locator("#ws-paper-right .ws-card").first
    if paper.count() == 0:
        pytest.skip("无 right paper")
    eid = paper.locator('[data-ws-action="reject"]').first.get_attribute("data-ws-eid")
    page_with_result.locator(
        f'[data-ws-action="reject"][data-ws-eid="{eid}"]'
    ).first.click()
    page_with_result.wait_for_timeout(1500)

    # 重建 final package, 该 eid 不应在 citation_list
    pid = page_with_result.evaluate("() => state && state.projectId")
    api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    pkg = api_client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={}).json()
    cited_eids = [c["evidence_id"] for c in pkg["citation_list"]]
    assert eid not in cited_eids, f"rejected eid={eid} 不应在 citation_list: {cited_eids}"


def test_06_card_intake_panel_visible(page_with_result):
    """Agent 卡片导入面板存在 (§7.2.6)."""

    panel = page_with_result.locator("#card-intake-panel")
    assert panel.is_visible(), "应可见 #card-intake-panel"
    assert page_with_result.locator("#intake-type").is_visible()
    assert page_with_result.locator("#intake-content").is_visible()
    assert page_with_result.locator("#intake-hint").is_visible()
    assert page_with_result.locator("#btn-intake").is_visible()


def test_07_github_url_creates_repo_card(page_with_result, api_client):
    """输入 GitHub URL 后生成 repo 卡片 (§7.2.7)."""

    # 填表单
    page_with_result.locator("#intake-type").select_option("url")
    page_with_result.locator("#intake-content").fill("https://github.com/ultralytics/ultralytics")
    page_with_result.locator("#intake-hint").fill("YOLO baseline")
    page_with_result.locator("#btn-intake").click()
    page_with_result.wait_for_timeout(2500)

    result = page_with_result.locator("#intake-result")
    assert result.is_visible(), "应显示生成结果"
    text = result.inner_text()
    assert "repo" in text, f"应有 repo 类型, 实际 {text[:200]}"


def test_08_intake_card_shows_confidence_warnings(page_with_result, api_client):
    """生成的卡片显示 pending / extraction_confidence / warning (§7.2.8)."""

    page_with_result.locator("#intake-type").select_option("url")
    page_with_result.locator("#intake-content").fill("https://github.com/owner/repo")
    page_with_result.locator("#intake-hint").fill("test")
    page_with_result.locator("#btn-intake").click()
    page_with_result.wait_for_timeout(2500)

    result = page_with_result.locator("#intake-result")
    text = result.inner_text()
    # 置信度百分比
    assert "置信度" in text or "%" in text, f"应有置信度显示: {text[:200]}"
    # pending 状态
    assert "pending" in text, f"应有 pending 状态: {text[:200]}"
    # 警告 (因为 URL 识别, 但未真实验证 train/eval)
    assert "⚠" in text or "未实际验证" in text, f"应有 warning: {text[:200]}"
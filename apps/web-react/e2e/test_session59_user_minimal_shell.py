"""Session 59 用户主线极简化与开发者模式隔离 — 真实点击 + 截图.

覆盖:
- T3: UserWorkbenchPage 4 区合一 (zone-a 题目 / zone-b AI / zone-c 证据 / zone-d 文献库)
- T4: 开发者抽屉 (Ctrl+` 触发 + 收纳 RAG/ThesisEval/Interview/Protocols/Health/旧前端)
- T5: ThoughtPanel 默认隐藏, 开发者窗口内才显示

前置: 后端 18181 + React dev 18183 都已起来.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session59"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def _shoot(page: Page, name: str) -> None:
    page.wait_for_timeout(200)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(150)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


@pytest.fixture(autouse=True)
def _reset_dev_mode(page: Page, react_url: str) -> None:
    """每个 case 开始前关闭 dev mode, 避免上一个 case 留下的状态干扰."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.evaluate("window.localStorage.removeItem('paperagent:dev-mode')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(200)


# ===========================================================================
# T3: UserWorkbenchPage — 4 区合一
# ===========================================================================


def test_s59_home_shows_user_workbench(page: Page, react_url: str) -> None:
    """#/ 首屏直接是 UserWorkbenchPage, 不再需要点 '进入工作台'."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("user-shell")).to_be_visible()
    expect(page.get_by_test_id("user-workbench")).to_be_visible()
    expect(page.get_by_test_id("uw-zone-a")).to_be_visible()
    expect(page.get_by_test_id("uw-zone-b")).to_be_visible()
    expect(page.get_by_test_id("uw-evidence")).to_be_visible()
    expect(page.get_by_test_id("uw-library")).to_be_visible()
    _shoot(page, "s59_user_minimal_home.png")


def test_s59_sidenav_hidden_in_user_mode(page: Page, react_url: str) -> None:
    """普通模式 SideNav 不渲染 (UserShell 不含 sidenav slot)."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    sidenav = page.get_by_test_id("sidenav")
    expect(sidenav).to_have_count(0)


def test_s59_thought_panel_hidden_in_user_mode(page: Page, react_url: str) -> None:
    """T5: ThoughtPanel 在普通模式下不存在于 DOM."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    # 普通模式 dev-mode 关闭, 没有 developer-panel; 也没有 thought-panel
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)
    # TUI console 的 test-id 也不应该出现
    expect(page.locator(".pa-thought-panel")).to_have_count(0)


def test_s59_zone_a_topic_intake_runs(page: Page, react_url: str) -> None:
    """Zone A: 题目输入 + 开始分析 → 状态变为等待确认."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topic-intake-input").fill("基于YOLO的钢材表面缺陷检测")
    expect(page.get_by_test_id("topic-intake-start")).to_be_enabled()
    page.get_by_test_id("topic-intake-start").click()
    page.wait_for_function(
        """() => {
            const status = document.querySelector('[data-testid="uw-topic-status"]');
            const analysis = document.querySelector('[data-testid="uw-analysis-results"]');
            return Boolean(
                status &&
                status.textContent &&
                status.textContent.includes('等待确认') &&
                analysis
            );
        }""",
        timeout=20000,
    )
    # 题目当前展示
    expect(page.get_by_test_id("topic-intake-current")).to_contain_text("YOLO")
    # 状态徽章更新
    status = page.get_by_test_id("uw-topic-status")
    expect(status).to_contain_text("等待确认")


def test_s59_zone_b_quick_action_fills_draft(page: Page, react_url: str) -> None:
    """Zone B: 4 个 quick action 真实填入 chat draft."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    for key, fragment in [
        ("modify", "请把题目改为"),
        ("constraint", "补充约束"),
        ("retrieve", "请帮我查证"),
        ("next", "请给我下一步建议"),
    ]:
        page.get_by_test_id(f"uw-quick-{key}").click()
        page.wait_for_timeout(80)
        value = page.get_by_test_id("chat-input").input_value()
        assert fragment in value, f"expected '{fragment}' in '{value}'"
        page.get_by_test_id("chat-input").fill("")


def test_s59_zone_b_chat_submit_modify_topic(page: Page, react_url: str) -> None:
    """Zone B: 提交 '修改...' → 预览卡片出现 → 接受后题目更新."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topic-intake-input").fill("原题")
    page.get_by_test_id("topic-intake-start").click()
    page.wait_for_timeout(200)
    page.get_by_test_id("chat-input").fill("修改 新题: 红外小目标检测")
    page.get_by_test_id("chat-submit").click()
    page.wait_for_timeout(300)
    expect(page.get_by_test_id("chat-preview")).to_be_visible()
    page.get_by_test_id("chat-accept").click()
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("topic-intake-current")).to_contain_text("红外小目标检测")


def test_s59_zone_c_evidence_submit_and_status(page: Page, react_url: str) -> None:
    """Zone C: 提交证据 → 出现条目 → 状态可改 → 可删除."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("evidence-link").fill("https://arxiv.org/abs/2106.12345")
    page.get_by_test_id("evidence-note").fill("用于方法对比")
    page.get_by_test_id("evidence-submit").click()
    page.wait_for_timeout(200)
    items = page.get_by_test_id("evidence-list").locator(".pa-uw-evidence-item")
    expect(items).to_have_count(1)
    expect(items.first).to_contain_text("arxiv.org")
    # 修改状态
    status_select = items.first.locator(".pa-uw-evidence-item__status")
    status_select.select_option("可用")
    expect(status_select).to_have_value("可用")
    # 删除
    items.first.locator(".pa-uw-evidence-item__remove").click()
    page.wait_for_timeout(150)
    expect(page.get_by_test_id("evidence-list").locator(".pa-uw-evidence-item")).to_have_count(0)
    _shoot(page, "s59_evidence_submit.png")


def test_s59_zone_d_library_submit_tag_status_remove(page: Page, react_url: str) -> None:
    """Zone D: S60 起改后端闭环 — 入库 → tag 切换 → 真实 paper_id 可见.

    S59 旧版测的是 useState 本地闭环 (改 status / 标记重新索引 / 删除).
    S60 后端接管后, 提交变成 POST /manual, 真实 paper_id 来自后端, 删除/状态字段
    暂未对接 (M6 边界). 这里保留对 tag 切换和真实入库的最小验证.
    """
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    # 隔离项目目录避免污染其他 test
    import shutil
    from pathlib import Path
    pd = Path("G:/PaperAgent/apps/api/.runtime/paper_library/demo_local_rag")
    if pd.exists():
        shutil.rmtree(pd, ignore_errors=True)
    page.reload(wait_until="domcontentloaded")
    page.get_by_test_id("library-title").fill("YOLOv5 钢材表面缺陷检测")
    page.get_by_test_id("library-link").fill("https://arxiv.org/abs/2106.12345")
    # S60 要求 text ≥ 10 字
    page.get_by_test_id("library-text").fill(
        "Abstract: YOLOv5 applied to steel surface defect detection on NEU-DET dataset."
    )
    page.get_by_test_id("library-submit").click()
    # 等后端入库 (S60 flash 出现)
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)
    items = page.get_by_test_id("library-list").locator(".pa-uw-library-item")
    expect(items).to_have_count(1)
    # 真实 paper_id 来自后端 (paper_mn_ 前缀)
    pid_text = items.first.locator("[data-testid^='library-meta-paper_mn_']").text_content() or ""
    assert "paper_mn_" in pid_text, f"期望后端 paper_id, got {pid_text}"
    # tag 切换仍然可用 (本地 UI 状态)
    items.first.locator(".pa-uw-tag").nth(0).click()
    items.first.locator(".pa-uw-tag").nth(2).click()
    page.wait_for_timeout(100)
    on_tags = items.first.locator(".pa-uw-tag--on")
    expect(on_tags).to_have_count(2)
    _shoot(page, "s59_rag_library_edit.png")


# ===========================================================================
# T4: DeveloperPanel 抽屉
# ===========================================================================


def test_s59_dev_panel_hidden_by_default(page: Page, react_url: str) -> None:
    """普通用户进入首屏, dev 抽屉不可见."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)


def test_s59_dev_panel_opens_via_toggle(page: Page, react_url: str) -> None:
    """TopBar 开发者按钮可打开 dev 抽屉, 含 RAG Eval / ThesisEval / Interview / Protocol 入口."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topbar-dev-toggle").click()
    page.wait_for_timeout(300)
    expect(page.get_by_test_id("developer-panel")).to_be_visible()
    for tid in [
        "dev-nav-rag-eval",
        "dev-nav-thesis-eval",
        "dev-nav-interview",
        "dev-nav-protocols",
        "dev-nav-health",
        "dev-nav-legacy",
    ]:
        expect(page.get_by_test_id(tid)).to_be_visible()
    # 抽屉里包含 ThoughtPanel (T5: dev 模式才显示 TUI console)
    expect(page.get_by_test_id("dev-thought-panel")).to_be_attached()
    _shoot(page, "s59_developer_panel.png")


def test_s59_dev_panel_closes_via_scrim_and_toggle(page: Page, react_url: str) -> None:
    """scrim 和 toggle 都能关闭 dev 抽屉."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    # 打开
    page.get_by_test_id("topbar-dev-toggle").click()
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_be_visible()
    # 关闭按钮
    page.get_by_test_id("dev-close").click()
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)
    # 再开 -> scrim 关闭
    page.get_by_test_id("topbar-dev-toggle").click()
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_be_visible()
    page.get_by_test_id("dev-scrim").click()
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)


def test_s59_dev_panel_keyboard_shortcut(page: Page, react_url: str) -> None:
    """Ctrl + ` 切换 dev 抽屉."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)
    page.keyboard.press("Control+`")
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_be_visible()
    page.keyboard.press("Control+`")
    page.wait_for_timeout(200)
    expect(page.get_by_test_id("developer-panel")).to_have_count(0)


def test_s59_dev_panel_nav_links_route(page: Page, react_url: str) -> None:
    """dev 抽屉点 RAG Eval → 跳到 RAG page."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    page.get_by_test_id("topbar-dev-toggle").click()
    page.wait_for_timeout(200)
    page.get_by_test_id("dev-nav-rag-eval").click()
    page.wait_for_timeout(400)
    expect(page.get_by_test_id("rag-eval-page")).to_be_visible()
    # dev 抽屉依然在
    expect(page.get_by_test_id("developer-panel")).to_be_visible()

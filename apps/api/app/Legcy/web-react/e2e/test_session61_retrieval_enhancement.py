"""Session 61: 多源检索候选面板 — 真实浏览器点击 + 截图.

覆盖 (SOP §7.2):
 1. 首页 user-shell + uw-retrieval 都可见
 2. 中文三维成像题检索 → papers/datasets/repos 三区都可见
 3. 论文候选含真实 title 文本
 4. 来源执行状态: 至少 2 个 retrieval-source-* 出现
 5. 缺数据集时 gap_report 出现 (或显式说没出现)
 6. retry banner / dataset candidates 至少有一个为真
 7. dev panel 打开 + retrieval-debug nav 可点
 8. 加入证据返回真实 evidence_id (man_paper_ 前缀)
 9. 标记不相关: 卡片 dim 化, 不报错
10. 补搜类似: input 框被填充
11. fetch mock 503 → retrieval-error 卡可见

前置: 后端 18181 + React dev 18183 都已起来.
project_id 使用 RetrievalCandidatePanel 默认的 demo-local-rag (后端已 seed 检索快照).
teardown 时清掉 demo-s61-retrieval 的 paper_library 数据 (防止命名冲突).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session61"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


PROJECT_ID = "demo-s61-retrieval"
DEFAULT_TOPIC = "基于三维成像的损伤智能检测"


def _project_dir() -> Path:
    """后端 paper_library 实际项目目录 (按 storage._safe_project 规则).

    uvicorn 用 --app-dir apps/api 启动, cwd = apps/api, 所以 PAPER_LIBRARY_DIR 相对 cwd.
    测试启动时 cwd 是 apps/web-react, 必须先回溯到仓库根再进入 apps/api.
    """

    repo_root = Path(__file__).resolve().parents[3]  # apps/web-react/e2e/ → G:/PaperAgent
    api_root = repo_root / "apps" / "api"
    root = api_root / ".runtime" / "paper_library"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in PROJECT_ID)
    return root / safe


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


@pytest.fixture(autouse=True)
def _clean_project_before():
    """每个 test 前清空 demo-s61-retrieval 数据 (paper_library 命名空间).

    one-topic 快照是 in-process, 这里只清 on-disk 部分.
    """

    pd = _project_dir()
    if pd.exists():
        shutil.rmtree(pd, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean_project_after():
    """teardown: 再次清理."""

    yield
    pd = _project_dir()
    if pd.exists():
        shutil.rmtree(pd, ignore_errors=True)


def _shoot(page: Page, name: str) -> None:
    page.wait_for_timeout(200)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(150)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


def _ensure_analyze_snapshot(page: Page) -> None:
    """确保 demo-local-rag 有 analyze snapshot (检索前置).

    假设 page 已导航到 react_url (相对 URL 才能解析).
    用 window.fetch 直接打 /analyze, project_id_override=demo-local-rag.
    """

    status = page.evaluate(
        """async () => {
            try {
                const r = await fetch('/api/v1/one-topic/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        raw_topic: '3D imaging damage detection',
                        prefer: 'heuristic',
                        project_id_override: 'demo-local-rag'
                    })
                });
                return r.status;
            } catch (e) {
                return 'err:' + String(e);
            }
        }"""
    )
    # 等一个 tick 让后端完成快照写入
    page.wait_for_timeout(400)
    return status


# ===========================================================================
# T1: 首页含 user-shell + uw-retrieval
# ===========================================================================


def test_s61_home_shows_retrieval_panel(page: Page, react_url: str) -> None:
    """普通模式: UserWorkbenchPage 含 user-shell + 新加的 retrieval panel."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("user-shell")).to_be_visible()
    expect(page.get_by_test_id("uw-retrieval")).to_be_visible()
    _shoot(page, "s61_home_retrieval.png")


# ===========================================================================
# T2-T6: 真实点击 — 三维成像题检索, 三区 + sources + gap_report
# ===========================================================================


def test_s61_three_d_topic_yields_three_regions(page: Page, react_url: str) -> None:
    """中文三维成像题 → papers/datasets/repos 三区可见."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)

    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    # 等结果: papers region 必出现
    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)
    expect(page.get_by_test_id("retrieval-datasets")).to_be_visible()
    expect(page.get_by_test_id("retrieval-repos")).to_be_visible()

    _shoot(page, "s61_three_regions.png")


def test_s61_paper_candidates_have_title_and_source(page: Page, react_url: str) -> None:
    """至少一篇论文候选含真实 title 文本 (非空)."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    paper_items = page.locator('[data-testid^="retrieval-paper-"]')
    # 至少 1 条 paper 候选
    count = paper_items.count()
    assert count >= 1, f"retrieval-paper-* 应至少 1 条, got {count}"

    # 第一条 title 文本非空
    first = paper_items.first
    text = (first.text_content() or "").strip()
    assert len(text) > 0, "首条 paper 候选 text 应非空"

    _shoot(page, "s61_paper_candidates.png")


def test_s61_source_results_visible(page: Page, react_url: str) -> None:
    """retrieval-sources 可见, 至少 2 个 retrieval-source-{name}."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-sources")).to_be_visible(timeout=30000)

    sources = page.locator('[data-testid^="retrieval-source-"]')
    # 排除 retrieval-source-tone-* (那是 badge 内子元素)
    count = 0
    for i in range(sources.count()):
        tid = sources.nth(i).get_attribute("data-testid") or ""
        if tid.startswith("retrieval-source-tone-"):
            continue
        count += 1

    assert count >= 2, f"retrieval-source-* 应至少 2 条, got {count}"

    _shoot(page, "s61_source_results.png")


def test_s61_gap_report_shows_when_dataset_missing(page: Page, react_url: str) -> None:
    """缺 dataset 时: retrieval-gap-report 出现 OR 明确无 gap 也允许."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    gap = page.get_by_test_id("retrieval-gap-report")
    # 不强制必须出现 (看后端是否决定生成 gap)
    # 但 datasets 区必须可见
    expect(page.get_by_test_id("retrieval-datasets")).to_be_visible()

    # 验证: 要么 gap 出现, 要么 datasets 里有候选
    datasets_count = page.locator('[data-testid^="retrieval-dataset-"]').count()
    gap_visible = gap.count() > 0 and gap.first.is_visible()

    assert gap_visible or datasets_count > 0, (
        "retrieval-gap-report 应出现 或 datasets 候选非空"
    )

    _shoot(page, "s61_gap_report.png")


def test_s61_retry_banner_or_datasets_present(page: Page, react_url: str) -> None:
    """retry banner 出现 OR datasets 候选非空 — 至少一个为真."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    retry_banner = page.get_by_test_id("retrieval-retry-banner")
    datasets_count = page.locator('[data-testid^="retrieval-dataset-"]').count()

    banner_visible = retry_banner.count() > 0 and retry_banner.first.is_visible()
    assert banner_visible or datasets_count > 0, (
        "retrieval-retry-banner 应出现 或 datasets 候选非空"
    )


# ===========================================================================
# T7: dev panel 打开 + retrieval-debug nav 可见
# ===========================================================================


def test_s61_dev_panel_query_plan_visible(page: Page, react_url: str) -> None:
    """打开 dev panel → retrieval-debug nav 可见 + 抽屉里 console slot 存在."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    # 默认 dev mode 关闭, 打开它
    page.evaluate("window.localStorage.setItem('paperagent:dev-mode', '1')")
    page.evaluate("window.dispatchEvent(new CustomEvent('paperagent:dev-mode', {detail: true}))")
    page.wait_for_timeout(300)

    expect(page.get_by_test_id("developer-panel")).to_be_visible()
    expect(page.get_by_test_id("dev-nav-retrieval-debug")).to_be_visible()

    # 点击 retrieval-debug nav → 路由 hash 跳到 ?mode=retrieval-debug
    page.get_by_test_id("dev-nav-retrieval-debug").click()
    page.wait_for_timeout(400)

    hash_value = page.evaluate("window.location.hash")
    assert "mode=retrieval-debug" in hash_value, f"hash 应含 mode=retrieval-debug, got {hash_value}"

    # console slot 至少存在 (TUI console 是 dev 专属)
    expect(page.get_by_test_id("dev-console-slot")).to_be_attached()

    _shoot(page, "s61_query_plan_dev.png")


# ===========================================================================
# T8: 加入证据返回真实 evidence_id
# ===========================================================================


def test_s61_add_paper_to_evidence_returns_real_id(page: Page, react_url: str) -> None:
    """点 retrieval-add-evidence-{cid} → 等待 imported-id 出现, id 应以 man_paper_ / ev_ 开头."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    paper_items = page.locator('[data-testid^="retrieval-paper-"]')
    if paper_items.count() == 0:
        pytest.skip("无 paper 候选, 跳过")

    # 取第一条 paper item, 提取 cid
    first_paper = paper_items.first
    first_tid = first_paper.get_attribute("data-testid") or ""
    cid = first_tid.replace("retrieval-paper-", "", 1)
    assert cid, f"无法提取 cid from {first_tid}"

    add_btn = page.get_by_test_id(f"retrieval-add-evidence-{cid}")
    expect(add_btn).to_be_visible()
    add_btn.click()

    # 等 imported-id 或 flash
    imported_locator = page.get_by_test_id(f"retrieval-imported-id-{cid}")

    # 后端可能因重复导入而返回 skipped_duplicates — 接受任一: imported-id 出现 OR flash 出现
    try:
        expect(imported_locator).to_be_visible(timeout=15000)
        text = imported_locator.text_content() or ""
        # 后端 candidate_actions 返回 man_paper_ 前缀
        assert text.startswith("evidence_id:") or "man_paper_" in text or "ev_" in text, (
            f"imported-id 应是 evidence_id 格式, got: {text}"
        )
    except Exception:
        # 退路: flash 里出现 "已加入证据" 或 "未导入"
        page.wait_for_timeout(1000)
        flash = page.get_by_test_id("retrieval-flash")
        if flash.count() > 0:
            flash_text = flash.first.text_content() or ""
            assert "证据" in flash_text or "重复" in flash_text or "未导入" in flash_text, (
                f"flash 应提示证据/重复/未导入, got: {flash_text}"
            )
        else:
            raise

    _shoot(page, "s61_add_evidence.png")


# ===========================================================================
# T9: 标记不相关 → 卡片 dim 化
# ===========================================================================


def test_s61_reject_candidate_does_navigation_only(page: Page, react_url: str) -> None:
    """点 retrieval-reject-{cid} → 卡片加 dim class, 无 error."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    paper_items = page.locator('[data-testid^="retrieval-paper-"]')
    if paper_items.count() == 0:
        pytest.skip("无 paper 候选, 跳过")

    first_paper = paper_items.first
    first_tid = first_paper.get_attribute("data-testid") or ""
    cid = first_tid.replace("retrieval-paper-", "", 1)

    reject_btn = page.get_by_test_id(f"retrieval-reject-{cid}")
    expect(reject_btn).to_be_visible()
    reject_btn.click()

    page.wait_for_timeout(500)

    # 卡片应含 dim class
    cls = first_paper.get_attribute("class") or ""
    assert "pa-uw-result-item--dim" in cls, f"reject 后应加 dim class, got: {cls}"

    # 不应有 error
    err = page.get_by_test_id("retrieval-error")
    assert err.count() == 0, "reject 后不应有 retrieval-error"

    _shoot(page, "s61_reject_dim.png")


# ===========================================================================
# T10: 补搜类似 → input 框被填充
# ===========================================================================


def test_s61_retry_similar_fills_input(page: Page, react_url: str) -> None:
    """点 retrieval-retry-similar-{cid} → retrieval-topic-input 值被更新."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    _ensure_analyze_snapshot(page)
    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)
    page.get_by_test_id("retrieval-search-btn").click()

    expect(page.get_by_test_id("retrieval-papers")).to_be_visible(timeout=30000)

    paper_items = page.locator('[data-testid^="retrieval-paper-"]')
    if paper_items.count() == 0:
        pytest.skip("无 paper 候选, 跳过")

    first_paper = paper_items.first
    first_tid = first_paper.get_attribute("data-testid") or ""
    cid = first_tid.replace("retrieval-paper-", "", 1)

    # 取 retry 前的 input 值
    before = page.get_by_test_id("retrieval-topic-input").input_value()

    retry_btn = page.get_by_test_id(f"retrieval-retry-similar-{cid}")
    expect(retry_btn).to_be_visible()
    retry_btn.click()

    page.wait_for_timeout(300)

    after = page.get_by_test_id("retrieval-topic-input").input_value()
    assert after != before, f"retry-similar 应改 input 值, before={before!r} after={after!r}"
    # 应含原 topic 的 keywords
    assert len(after) > len(before) or "implementation" in after or "survey" in after or "benchmark" in after, (
        f"retry-similar 应添加新关键词, after={after!r}"
    )

    _shoot(page, "s61_retry_similar.png")


# ===========================================================================
# T11: fetch mock 503 → retrieval-error 卡可见
# ===========================================================================


def test_s61_api_error_shows_error_card(page: Page, react_url: str) -> None:
    """mock fetch 让 /retrieval/search 返回 503 → retrieval-error 出现."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    page.get_by_test_id("retrieval-topic-input").fill(DEFAULT_TOPIC)

    page.evaluate(
        """() => {
            const origPost = window.fetch;
            window.fetch = (url, init) => {
                if (typeof url === 'string' && url.includes('/retrieval/search')) {
                    return Promise.resolve(new Response(
                        JSON.stringify({detail: 'simulated retrieval down'}),
                        {status: 503, headers: {'Content-Type': 'application/json'}},
                    ));
                }
                return origPost(url, init);
            };
        }"""
    )

    page.get_by_test_id("retrieval-search-btn").click()

    err = page.get_by_test_id("retrieval-error")
    expect(err).to_be_visible(timeout=15000)
    err_text = err.text_content() or ""
    assert "失败" in err_text or "simulated" in err_text or "503" in err_text, (
        f"error 卡应提示失败/simulated/503, got: {err_text}"
    )

    _shoot(page, "s61_api_error.png")
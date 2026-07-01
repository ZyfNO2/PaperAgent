"""Session 60: 本地 RAG 最小闭环 — 真实浏览器点击 + 截图.

覆盖 (SOP §6.2):
1. 普通首页仍只显示用户主线 + 新增 local-rag panel
2. 添加文献调用后端成功 (POST /manual)
3. 添加后列表出现真实后端返回的文献 (paper_id 来自后端)
4. 点击索引后显示 已索引 / chunk 数
5. 本地 RAG 提问后出现答案 (含 NEU-DET)
6. 答案下方显示引用 chunk
7. 刷新页面后文献仍存在
8. 后端 API 失败时显示错误卡, 不假装成功
9. 重复入库: flash 显示 duplicate
10. 待索引状态: item 标"待索引"

前置: 后端 18181 + React dev 18183 都已起来.
使用固定 project_id="demo-local-rag" (PaperLibraryEditor 默认),
teardown 时清掉该 project 的 .runtime/paper_library 数据.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect


pytestmark = pytest.mark.react_web


SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots" / "session60"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


SAMPLE_TITLE = "YOLO Steel Surface Defect Detection Note"
SAMPLE_TEXT = (
    "This paper studies steel surface defect detection using YOLO. "
    "The experiment uses the NEU-DET dataset and reports that lightweight "
    "YOLO variants can detect scratches, patches and crazing defects. "
    "The method section describes data augmentation and evaluation with precision and recall."
)
SAMPLE_QUESTION = "What dataset does this paper use?"

PROJECT_ID = "demo-local-rag"


def _project_dir() -> Path:
    """后端 paper_library 实际项目目录 (按 storage._safe_project 规则).

    uvicorn 用 --app-dir apps/api 启动, cwd = apps/api, 所以 PAPER_LIBRARY_DIR 相对 cwd.
    测试启动时 cwd 是 apps/web-react, 必须先回溯到仓库根再进入 apps/api.
    """

    # 测试进程 cwd = apps/web-react; 找仓库根 = 上一级
    repo_root = Path(__file__).resolve().parents[3]  # apps/web-react/e2e/ → G:/PaperAgent
    api_root = repo_root / "apps" / "api"
    # backend storage._library_root 用的是 .runtime/paper_library (相对 uvicorn 启动 cwd)
    # uvicorn cwd 解析: 调用方 cwd 即 G:/PaperAgent/apps/api, 故绝对路径是
    # G:/PaperAgent/apps/api/.runtime/paper_library
    root = api_root / ".runtime" / "paper_library"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in PROJECT_ID)
    return root / safe


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def _shoot(page: Page, name: str) -> None:
    page.wait_for_timeout(200)
    page.set_viewport_size({"width": 1440, "height": 900})
    page.wait_for_timeout(150)
    page.screenshot(path=str(SCREENSHOT_DIR / name), full_page=True)


@pytest.fixture(autouse=True)
def _clean_project_before():
    """每个 test 前清空 demo-local-rag 数据, 保证 test 间隔离."""

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


# ===========================================================================
# T1: 普通首页含 zone a-d + 新增 local-rag panel
# ===========================================================================


def test_s60_home_shows_local_rag_panel(page: Page, react_url: str) -> None:
    """普通模式: UserWorkbenchPage 含 zone-a/b/evidence/library + 新加的 local-rag panel."""
    page.goto(react_url + "/#/", wait_until="domcontentloaded")
    expect(page.get_by_test_id("user-shell")).to_be_visible()
    expect(page.get_by_test_id("uw-evidence")).to_be_visible()
    expect(page.get_by_test_id("uw-library")).to_be_visible()
    expect(page.get_by_test_id("uw-local-rag")).to_be_visible()
    _shoot(page, "s60_home_with_local_rag.png")


# ===========================================================================
# T2-T4: 真实点击 — 入库 + 索引 + 刷新持久化
# ===========================================================================


def test_s60_add_paper_index_and_persist(page: Page, react_url: str) -> None:
    """完整流程: 入库 → 列表显示真实 paper_id → 重建索引 → 状态变化 → 刷新后仍在."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    # 1) 入库
    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill(SAMPLE_TEXT)
    page.get_by_test_id("library-submit").click()

    # 等待 flash 出现
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)
    flash_text = page.get_by_test_id("library-flash").text_content() or ""
    assert "已入库" in flash_text, f"expected 已入库 in flash, got {flash_text}"

    # 2) 列表出现真实 paper_id
    page.wait_for_selector('[data-testid^="library-item-paper_mn_"]', timeout=10000)
    items = page.locator('[data-testid^="library-item-paper_mn_"]')
    assert items.count() >= 1

    # 取出 paper_id (从 meta 里)
    meta_text = page.locator('[data-testid^="library-meta-paper_mn_"]').first.text_content() or ""
    assert "paper_mn_" in meta_text
    assert "chunks" in meta_text

    _shoot(page, "s60_add_paper.png")

    # 3) 重建索引
    page.get_by_test_id("library-reindex-all").click()
    page.wait_for_function(
        """() => {
            const flash = document.querySelector('[data-testid="library-flash"]');
            return flash && flash.textContent && flash.textContent.includes('索引完成');
        }""",
        timeout=15000,
    )

    # index status provider 出现
    page.wait_for_function(
        """() => {
            const el = document.querySelector('[data-testid="library-meta-provider"]');
            return el && el.textContent && el.textContent.includes('provider:');
        }""",
        timeout=5000,
    )
    provider_text = page.get_by_test_id("library-meta-provider").text_content() or ""
    assert "provider:" in provider_text

    # 该 paper 的索引状态应为"已索引"
    indexed_status = page.locator('[data-testid^="library-index-status-paper_mn_"]').first
    expect(indexed_status).to_contain_text("已索引")

    _shoot(page, "s60_index_status.png")

    # 4) 刷新页面 → 文献仍在
    page.reload(wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid^="library-item-paper_mn_"]', timeout=10000)
    items_after = page.locator('[data-testid^="library-item-paper_mn_"]')
    assert items_after.count() >= 1

    _shoot(page, "s60_after_refresh_persisted.png")


# ===========================================================================
# T5-T6: 本地 RAG 问答 — 答案 + 引用 chunk
# ===========================================================================


def test_s60_local_rag_ask_returns_answer_with_citation(page: Page, react_url: str) -> None:
    """入库 → 索引 → 提问 → 答案 + 引用片段可见 (cite 来自用户原文)."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    # 入库 + 索引
    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill(SAMPLE_TEXT)
    page.get_by_test_id("library-submit").click()
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)
    page.get_by_test_id("library-reindex-all").click()
    page.wait_for_function(
        """() => {
            const flash = document.querySelector('[data-testid="library-flash"]');
            return flash && flash.textContent && flash.textContent.includes('索引完成');
        }""",
        timeout=15000,
    )

    # 提问
    page.get_by_test_id("local-rag-question").fill(SAMPLE_QUESTION)
    page.get_by_test_id("local-rag-submit").click()

    page.wait_for_selector('[data-testid="local-rag-result"]', timeout=15000)

    mode = page.get_by_test_id("local-rag-mode").text_content() or ""
    assert "local_embedding" in mode, f"expected local_embedding mode, got {mode}"

    answer = page.get_by_test_id("local-rag-answer").text_content() or ""
    # answer 应提到 NEU-DET (extractive answer 摘抄原文)
    assert "NEU-DET" in answer or "neu" in answer.lower(), (
        f"answer 应提到 NEU-DET, got: {answer[:200]}"
    )

    # 至少 1 条引用
    refs = page.locator('[data-testid^="local-rag-ref-chunk_"]')
    assert refs.count() >= 1

    # 引用 quote 应包含 NEU-DET
    first_quote = page.locator('[data-testid^="local-rag-ref-quote-chunk_"]').first.text_content() or ""
    assert "NEU-DET" in first_quote or "neu" in first_quote.lower()

    _shoot(page, "s60_local_rag_answer.png")


# ===========================================================================
# T7: 提问无关内容 → no_hit, 不假装有答案
# ===========================================================================


def test_s60_local_rag_no_hit_displays_unfilled(page: Page, react_url: str) -> None:
    """无命中时: 显示 未命中 徽章 + 明确文案, 不展示伪答案."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    # 先入库 + 索引 (库非空)
    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill(SAMPLE_TEXT)
    page.get_by_test_id("library-submit").click()
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)
    page.get_by_test_id("library-reindex-all").click()
    page.wait_for_function(
        """() => {
            const flash = document.querySelector('[data-testid="library-flash"]');
            return flash && flash.textContent && flash.textContent.includes('索引完成');
        }""",
        timeout=15000,
    )

    # 提问无关内容
    page.get_by_test_id("local-rag-question").fill("completely unrelated quantum entanglement telescope")
    page.get_by_test_id("local-rag-submit").click()

    page.wait_for_selector('[data-testid="local-rag-result"]', timeout=15000)

    no_hit = page.get_by_test_id("local-rag-no-hit")
    expect(no_hit).to_be_visible()
    mode = page.get_by_test_id("local-rag-mode").text_content() or ""
    assert "no_hit" in mode
    refs = page.locator('[data-testid^="local-rag-ref-chunk_"]')
    assert refs.count() == 0

    _shoot(page, "s60_local_rag_no_hit.png")


# ===========================================================================
# T8: API 失败时显示错误卡, 不假装成功
# ===========================================================================


def test_s60_local_rag_api_error_shows_error_card(page: Page, react_url: str) -> None:
    """mock fetch 503 → 错误卡可见."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    page.get_by_test_id("local-rag-question").fill("anything")
    page.evaluate(
        """() => {
            const origPost = window.fetch;
            window.fetch = (url, init) => {
                if (typeof url === 'string' && url.includes('/local-ask')) {
                    return Promise.resolve(new Response(
                        JSON.stringify({detail: 'simulated backend down'}),
                        {status: 503, headers: {'Content-Type': 'application/json'}},
                    ));
                }
                return origPost(url, init);
            };
        }"""
    )
    page.get_by_test_id("local-rag-submit").click()

    err = page.get_by_test_id("local-rag-error")
    expect(err).to_be_visible(timeout=10000)
    err_text = err.text_content() or ""
    assert "失败" in err_text or "simulated" in err_text

    _shoot(page, "s60_local_rag_api_error.png")


# ===========================================================================
# T9: 重复入库 → flash 显示 duplicate, 列表不增长
# ===========================================================================


def test_s60_duplicate_paper_shows_duplicate_flash(page: Page, react_url: str) -> None:
    """重复标题入库: flash 标 '重复文献', 列表不重复添加."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    # 第一次入库
    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill(SAMPLE_TEXT)
    page.get_by_test_id("library-submit").click()
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)
    first_count = page.locator('[data-testid^="library-item-paper_mn_"]').count()

    # 第二次入库同标题
    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill("Different text but same title should be detected as duplicate.")
    page.get_by_test_id("library-submit").click()
    page.wait_for_function(
        """() => {
            const flash = document.querySelector('[data-testid="library-flash"]');
            return flash && flash.textContent && flash.textContent.includes('重复');
        }""",
        timeout=10000,
    )

    second_count = page.locator('[data-testid^="library-item-paper_mn_"]').count()
    assert second_count == first_count, (
        f"重复入库不应增加文献数, 之前 {first_count} → 现在 {second_count}"
    )

    _shoot(page, "s60_duplicate_flash.png")


# ===========================================================================
# T10: 入库后未索引 → "待索引", 问答 no_hit (向量空)
# ===========================================================================


def test_s60_paper_pending_index_shows_pending_status(page: Page, react_url: str) -> None:
    """入库后未索引: item 状态是 待索引."""

    page.goto(react_url + "/#/", wait_until="domcontentloaded")

    page.get_by_test_id("library-title").fill(SAMPLE_TITLE)
    page.get_by_test_id("library-text").fill(SAMPLE_TEXT)
    page.get_by_test_id("library-submit").click()
    page.wait_for_selector('[data-testid="library-flash"]', timeout=10000)

    pending = page.locator('[data-testid^="library-index-status-paper_mn_"]').first
    expect(pending).to_contain_text("待索引")

    _shoot(page, "s60_pending_status.png")
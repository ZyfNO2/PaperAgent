"""Session 19: 轻量学校模板与开题报告适配 — 前端 e2e.

覆盖:
1. 模板选择器加载 3 个模板 (default / engineering / cv_ai)
2. 默认选中 default
3. 选择 cv_ai 模板 build 后, 模板信息显示 cv_ai
4. 生成 Markdown 包含模板 key 标注
5. 重新选择 default 模板 build 后, 模板信息同步回 default
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


def _select_template(page, template_key: str) -> None:
    """在 report-template select 中选择一个模板."""

    select = page.locator("#report-template")
    # 显式 dispatch change 事件, 确保前端 onChange handler 同步触发
    page.evaluate(
        """(key) => {
            const sel = document.getElementById('report-template');
            if (!sel) return;
            sel.value = key;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
        }""",
        template_key,
    )


def _wait_for_template_loaded(page) -> None:
    """等待模板选择器加载出 3 个选项 (option 元素本身不可见, 用 attached 检查存在)."""

    page.wait_for_selector("#report-template option[value='default']", state="attached", timeout=10000)
    page.wait_for_selector("#report-template option[value='engineering']", state="attached", timeout=10000)
    page.wait_for_selector("#report-template option[value='cv_ai']", state="attached", timeout=10000)
    # 确认 select 本身可见且含有 3 个 option
    page.wait_for_selector("#report-template", state="visible", timeout=10000)
    assert page.locator("#report-template option").count() == 3


def _build_and_wait(page, expected_template: str = None) -> None:
    """点击生成报告并等待 build 真正完成 (preview 重新渲染, 模板信息刷新).

    第一次 build 用 btn-build-report; 之后 build 用 btn-rebuild-report.
    等待策略: 抓取当前 preview 文本, 触发 build, 等到 preview 文本变化 (带超时).

    如果指定 expected_template, 还会等待 #report-template-info 包含该 key.
    """

    # 抓取当前 preview 文本作为变化锚
    preview_loc = page.locator("#report-preview")
    has_preview = preview_loc.count() > 0 and preview_loc.is_visible()
    before_text = preview_loc.inner_text() if has_preview else ""

    # 选 build / rebuild 按钮
    build_btn = page.locator("#btn-build-report")
    rebuild_btn = page.locator("#btn-rebuild-report")
    if rebuild_btn.count() > 0 and rebuild_btn.is_visible():
        rebuild_btn.click()
    else:
        build_btn.click()

    # 等 preview 出现 (若还未出现)
    try:
        if not has_preview:
            page.wait_for_selector("#report-preview", state="visible", timeout=10000)
    except Exception:
        if page.locator("#btn-preview-report").is_visible():
            page.locator("#btn-preview-report").click()
        page.wait_for_selector("#report-preview", state="visible", timeout=8000)

    # 等 build 完成: preview 文本变化 / 模板信息刷新 / 模板 key 符合预期 (最迟 15s)
    try:
        page.wait_for_function(
            """([before, expected]) => {
                const p = document.getElementById('report-preview');
                const t = document.getElementById('report-template-info');
                const nowPreview = p ? (p.innerText || '') : '';
                const nowTpl = t ? (t.innerText || '') : '';
                if (nowPreview !== before) return true;
                if (expected && nowTpl.indexOf(expected) >= 0) return true;
                if (!expected && /模板[:：]/.test(nowTpl)) return true;
                return false;
            }""",
            arg=[before_text, expected_template],
            timeout=15000,
        )
    except Exception:
        # 兜底: sleep 1s, 让 build 至少跑一次
        page.wait_for_timeout(1500)


def test_01_template_selector_loaded(page_with_result):
    """报告区出现模板选择器, 且包含 3 个模板."""

    _wait_for_template_loaded(page_with_result)
    select = page_with_result.locator("#report-template")
    options = select.locator("option").all()
    values = [opt.get_attribute("value") for opt in options]
    assert "default" in values
    assert "engineering" in values
    assert "cv_ai" in values
    # 默认选中 default
    assert select.input_value() == "default"


def test_02_default_template_build(page_with_result, api_client):
    """默认模板 build 后, 模板信息区显示 default."""

    _wait_for_template_loaded(page_with_result)
    _build_and_wait(page_with_result)

    info = page_with_result.locator("#report-template-info")
    assert info.is_visible(), "应显示模板信息区"
    text = info.inner_text()
    assert "default" in text, f"模板信息应包含 default, 实际: {text}"


def test_03_cv_ai_template_build(page_with_result, api_client):
    """选择 cv_ai 模板 build 后, 模板信息区显示 cv_ai."""

    _wait_for_template_loaded(page_with_result)
    _select_template(page_with_result, "cv_ai")
    _build_and_wait(page_with_result)

    info = page_with_result.locator("#report-template-info")
    assert info.is_visible()
    text = info.inner_text()
    assert "cv_ai" in text, f"模板信息应包含 cv_ai, 实际: {text}"

    # Markdown 预览中应包含模板 key 标注
    pre = page_with_result.locator("#report-preview")
    md = pre.inner_text()
    assert "cv_ai" in md, f"Markdown 应包含 cv_ai 模板标注, 实际前 200 字: {md[:200]}"


def test_04_engineering_template_build(page_with_result, api_client):
    """选择 engineering 模板 build 后, 模板信息区显示 engineering."""

    _wait_for_template_loaded(page_with_result)
    _select_template(page_with_result, "engineering")
    _build_and_wait(page_with_result)

    info = page_with_result.locator("#report-template-info")
    assert info.is_visible()
    text = info.inner_text()
    assert "engineering" in text, f"模板信息应包含 engineering, 实际: {text}"


def test_05_switch_back_to_default(page_with_result, api_client):
    """先选 cv_ai 再切回 default 重新 build, 模板信息同步回 default."""

    _wait_for_template_loaded(page_with_result)
    _select_template(page_with_result, "cv_ai")
    _build_and_wait(page_with_result, expected_template="cv_ai")
    _select_template(page_with_result, "default")
    _build_and_wait(page_with_result, expected_template="default")

    info = page_with_result.locator("#report-template-info")
    text = info.inner_text()
    assert "default" in text, f"切回 default 后模板信息应显示 default, 实际: {text}"

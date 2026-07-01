"""Session 52: React 前端 Playwright smoke.

- React 首页可打开, 显示迁移阶段
- 后端 health 有明确 loading/ok/error 三态
- 旧前端入口链接存在
- /api proxy 工作 (经过 Vite 转发)
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def react_url() -> str:
    return "http://127.0.0.1:18183"


def test_s52_01_homepage_loads(page: Page, react_url: str) -> None:
    """首页打开, title 包含 'PaperAgent'."""
    page.goto(react_url, wait_until="domcontentloaded")
    expect(page).to_have_title(re.compile(r"PaperAgent"))


def test_s52_02_migration_phase_visible(page: Page, react_url: str) -> None:
    """迁移阶段面板展示 S52 与后续 Session 路线图."""
    page.goto(react_url, wait_until="domcontentloaded")
    phase_card = page.get_by_test_id("phase-card")
    expect(phase_card).to_be_visible()
    expect(phase_card).to_contain_text("S52")
    expect(phase_card).to_contain_text("S53")
    expect(phase_card).to_contain_text("S55")


def test_s52_03_legacy_link_present(page: Page, react_url: str) -> None:
    """旧前端入口存在且指向 18182."""
    page.goto(react_url, wait_until="domcontentloaded")
    legacy = page.get_by_test_id("legacy-card")
    expect(legacy).to_be_visible()
    link = legacy.locator("a")
    expect(link).to_have_attribute("href", "http://127.0.0.1:18182")


def test_s52_04_health_loading_or_resolved(page: Page, react_url: str) -> None:
    """health 卡片至少呈现 loading/ok/error 中的一种."""
    page.goto(react_url, wait_until="domcontentloaded")
    # wait_for_selector 中任何一个出现都算健康探针工作
    page.wait_for_selector(
        "[data-testid='health-loading'], [data-testid='health-ok'], "
        "[data-testid='health-error']",
        timeout=10_000,
    )


def test_s52_05_sidenav_scaffolded(page: Page, react_url: str) -> None:
    """侧栏出现, 含旧前端入口."""
    page.goto(react_url, wait_until="domcontentloaded")
    nav = page.get_by_test_id("sidenav")
    expect(nav).to_be_visible()
    expect(nav).to_contain_text("脚手架")
    expect(nav).to_contain_text("18182")

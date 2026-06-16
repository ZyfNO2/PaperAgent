"""Playwright E2E smoke 模板（apps/web 出现时直接 cp 到 apps/web/e2e/）。

MVP 阶段：当前没有 apps/web，本文件作为参考模板 + hook 的预期位置。
一旦 apps/web 落地（Next.js / Vite / 任何前端），把本文件复制过去，
按需改 import 与 URL 即可。

设计：
- happy path: 走完 Phase 01-04 页面
- blocked path: 验证 D 评级项目不被允许进入 Phase 02
- refresh persistence: 刷新后阶段产物仍可见
"""

from __future__ import annotations

import re

import pytest


# 这个 conftest 是 Placeholder，等 apps/web 真实存在时改 import。
# 当前 conftest 路径示例:
#   apps/web/e2e/conftest.py
#   apps/web/e2e/test_smoke.py


# 跳过条件：当前无 apps/web
pytestmark = pytest.mark.skip(
    reason="apps/web 暂未实现。落地前端后: cp this file to apps/web/e2e/, install playwright."
)


@pytest.fixture
def page():
    raise NotImplementedError("待前端落地")


def test_happy_path_phase_01_to_04(page) -> None:
    """§5.1 MVP Happy Path."""
    page.goto("http://localhost:3000/")
    page.get_by_role("button", name=re.compile("创建项目")).click()
    # ... 实际交互依赖前端实现
    assert False, "占位"


def test_blocked_path_d_rating(page) -> None:
    """§5.2 Blocked Path."""
    page.goto("http://localhost:3000/")
    # 创建 D 级项目 → 验证"题目拆解"按钮 disabled
    raise NotImplementedError


def test_refresh_persistence(page) -> None:
    """§5.3 刷新后阶段产物仍可见."""
    raise NotImplementedError

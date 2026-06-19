"""Session 13: 内部 Skill Registry 前端 e2e (SOP §10.2).

覆盖:
1. 页面能看到内部 Skill 区块
2. 显示 4 个 skill
3. 显示 enabled / risk_level
4. 点击 skill 可展开用途
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


# ---------- 1: Skill 区块可见 ---------- #


def test_01_skill_panel_visible(page_with_result):
    """#skill-panel 应可见."""

    panel = page_with_result.locator("#skill-panel")
    assert panel.count() == 1
    assert page_with_result.locator("#btn-skill-refresh").count() == 1
    assert page_with_result.locator("#btn-skill-health").count() == 1


# ---------- 2: 显示 4 个 skill ---------- #


def test_02_shows_4_skills(page_with_result, api_client):
    """4 个内部 skill 应显示 (需切到 evidence tab)."""

    # 切到 evidence tab 触发 loadSkillRegistry
    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#skill-panel", timeout=10000)
    # 等 skill 卡片渲染
    page_with_result.wait_for_selector(".skill-card", timeout=10000)
    cards = page_with_result.locator(".skill-card")
    assert cards.count() >= 4, f"应至少 4 个 skill, got {cards.count()}"
    names = [c.locator(".skill-card__name").text_content() or "" for c in cards.all()]
    expected = {"paper-card", "dataset-validation", "github-baseline", "evidence-ledger"}
    actual = set(names)
    assert expected.issubset(actual), f"缺少 skill: {expected - actual}, got {actual}"


# ---------- 3: 显示 enabled / risk_level ---------- #


def test_03_shows_enabled_and_risk_level(page_with_result, api_client):
    """每个 skill 应显示 enabled pill 和 risk_level pill."""

    page_with_result.click("#tab-evidence")
    page_with_result.wait_for_selector("#skill-panel", timeout=10000)
    page_with_result.wait_for_selector(".skill-card", timeout=10000)
    cards = page_with_result.locator(".skill-card")
    for card in cards.all():
        text = card.text_content() or ""
        assert "enabled" in text or "disabled" in text, f"缺 status pill: {text[:100]}"
        assert "risk" in text, f"缺 risk_level pill: {text[:100]}"


# ---------- 4: 点击 health 显示 issues ---------- #


def test_04_health_check_button_works(page_with_result, api_client):
    """点击 健康检查 按钮后 hint 显示 issues 统计."""

    # 通过 API 验证 health 端点
    r = api_client.get("/api/v1/skills/health")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "ok" in body
    assert "issues" in body
    assert "default_forbidden_actions" in body

    # UI 检查
    page_with_result.click("#btn-skill-health")
    page_with_result.wait_for_selector(".skill-card", timeout=10000)
    hint = page_with_result.locator("#skill-summary-hint").text_content() or ""
    assert "health" in hint, f"hint 应含 health 统计, got {hint}"
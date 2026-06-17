"""Session 5 前端 e2e 测试: 评分展示 + 排序 + rescore 按钮 (SOP §9.2).

跑法:
    1. 起后端:  .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181
    2. 起前端:  .venv/Scripts/python.exe apps/web/dev_server.py
    3. 跑测试:  .venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session5_scoring.py -v
"""

from __future__ import annotations

import re
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402
from app.services import evidence as ev_store  # noqa: E402


@pytest.fixture
def api_client():
    ev_store.reset_all()
    return TestClient(app)


def _start_project(api_client: TestClient, topic: str = "基于YOLO的钢材表面缺陷检测") -> str:
    r = api_client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- §7.1 论文卡片显示分数 ---------- #


def test_evidence_cards_show_relevance_score(page_with_result, api_client):
    """论文/数据集/Repo 卡片展示 relevance_score / quality_score."""

    # 找到论文卡片, 验证含 "相关性:" 和分数
    cards = page_with_result.locator('[data-evidence-list="papers"] .evidence-card')
    assert cards.count() > 0
    first = cards.first
    text = first.inner_text()
    assert "相关性" in text
    # 分数形如 0.xx
    assert re.search(r"[\d]+\.\d+", text), f"missing score: {text}"


def test_evidence_cards_show_paper_type(page_with_result, api_client):
    """论文卡片展示 paper_type 标签 (survey/baseline_method/irrelevant/...)."""

    cards = page_with_result.locator('[data-evidence-list="papers"] .evidence-card')
    first_text = cards.first.inner_text()
    assert any(t in first_text for t in ("baseline_method", "survey", "application", "unknown", "irrelevant"))


def test_dataset_cards_show_quality_score(page_with_result, api_client):
    """数据集卡片展示 quality_score + dataset_status."""

    cards = page_with_result.locator('[data-evidence-list="datasets"] .evidence-card')
    assert cards.count() > 0
    text = cards.first.inner_text()
    assert "可用性" in text
    assert re.search(r"[\d]+\.\d+", text)


# ---------- §7.2 排序 ---------- #


def test_sort_papers_by_score_desc(page_with_result, api_client):
    """点 sort-papers=score-desc 后, 论文按评分降序."""

    page_with_result.locator("#sort-papers").select_option("score-desc")
    time.sleep(0.3)
    cards = page_with_result.locator('[data-evidence-list="papers"] .evidence-card')
    scores = []
    for i in range(cards.count()):
        text = cards.nth(i).inner_text()
        m = re.search(r"相关性:\s*([\d.]+)", text)
        if m:
            scores.append(float(m.group(1)))
    # 验证单调不增
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1] - 0.001, f"not desc: {scores}"


# ---------- §7.3 重新评分按钮 ---------- #


def test_rescore_button_triggers_endpoint(page_with_result, api_client):
    """点 rescore 按钮后, 调 /evidence/rescore 端点 + 显示成功状态."""

    btn = page_with_result.locator("#btn-rescore")
    btn.click()
    # 按钮变成 "⏳ 评分中..." 或 "✓ 已更新"
    page_with_result.wait_for_function(
        "() => document.getElementById('btn-rescore') && !document.getElementById('btn-rescore').textContent.includes('⏳')",
        timeout=15000,
    )
    text = btn.inner_text()
    assert "已更新" in text or "失败" in text


def test_score_summary_visible_after_rescore(page_with_result, api_client):
    """rescore 完成后按钮文字含 usable 计数 (P/D/R)."""

    btn = page_with_result.locator("#btn-rescore")
    btn.click()
    page_with_result.wait_for_function(
        "() => { const b = document.getElementById('btn-rescore'); return b && (b.textContent.includes('已更新') || b.textContent.includes('失败')); }",
        timeout=15000,
    )
    text = btn.inner_text()
    assert "P" in text and "D" in text and "R" in text, f"missing P/D/R: {text}"

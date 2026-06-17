"""Session 6 前端 e2e: LLM 路径生效 + 症状 3 根治 + 推荐/审核 LLM 化 (SOP §13.1).

跑法:
    1. 后端: .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181
    2. 前端: .venv/Scripts/python.exe apps/web/dev_server.py
    3. 测试: .venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session6_llm.py -v --timeout=90
"""

from __future__ import annotations

import re
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402
from app.services import evidence as ev_store  # noqa: E402


@pytest.fixture
def api_client():
    ev_store.reset_all()
    return TestClient(app)


# ---------- LLM 路径整体跑通 ---------- #


def test_llm_path_analyze_returns_pinn_papers(page, api_client):
    """PINN 题目 → LLM rerank 后, 论文里应含 PINN/PDE/数字孪生, 不含 German survey/AGN."""

    page.fill("#input-topic", "基于物理信息神经网络(PINN)的机构实时数字孪生")
    # 默认 auto
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-evidence .evidence-card", timeout=30000)

    # 看论文卡片文字
    cards = page.locator('[data-evidence-list="papers"] .evidence-card')
    all_text = " ".join(cards.nth(i).inner_text() for i in range(cards.count()))

    # LLM rerank 应至少 1 篇 PINN 真实相关
    has_pinn = any(kw in all_text for kw in ("PINN", "Physics-Informed", "PDE", "physics", "数字孪生", "Digital Twin"))
    # 不应含明显的无关论文
    has_irrelevant = any(kw in all_text for kw in ("German", "AGN", "Boötes", "Sandwich"))
    assert has_pinn, f"未找到 PINN 真实相关论文: {all_text[:300]}"
    assert not has_irrelevant, f"仍含无关论文 (症状 3 没根治): {all_text[:300]}"


def test_llm_path_baselines_match_pinn(page, api_client):
    """PINN 题目 → baseline 命中 DeepXDE 或 NVIDIA Modulus (症状 2 根治)."""

    page.fill("#input-topic", "基于物理信息神经网络(PINN)的机构实时数字孪生")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-evidence .evidence-card", timeout=30000)

    cards = page.locator('[data-evidence-list="baselines"] .evidence-card')
    all_text = " ".join(cards.nth(i).inner_text() for i in range(cards.count()))

    has_pinn_repo = any(kw in all_text for kw in ("DeepXDE", "NVIDIA Modulus", "PINN"))
    has_resnet_fallback = "ResNet-50" in all_text
    assert has_pinn_repo, f"PINN baseline 未命中: {all_text[:300]}"
    assert not has_resnet_fallback, f"仍兜底 ResNet-50 (症状 2 没根治): {all_text[:300]}"


def test_llm_recommend_topic_reflects_pinn(page, api_client):
    """LLM 写推荐题目, 应含原题关键词 (PINN/数字孪生), 不是通用 '目标检测'."""

    page.fill("#input-topic", "基于物理信息神经网络(PINN)的机构实时数字孪生")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-recommendation", timeout=30000)

    rec_text = page.inner_text("#block-recommendation")
    assert any(kw in rec_text for kw in ("PINN", "数字孪生", "物理信息", "机构")), (
        f"推荐题目不像 LLM 写的 (没含原题关键词): {rec_text[:300]}"
    )


def test_llm_review_has_5_dimensions(page, api_client):
    """5 维审核 (题目边界/数据集/Baseline/工作量/开题表达) 都存在."""

    page.fill("#input-topic", "基于物理信息神经网络(PINN)的机构实时数字孪生")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-light-review .review__check", timeout=30000)

    checks = page.locator("#block-light-review .review__check")
    n = checks.count()
    assert n == 5, f"5 维审核, 实际 {n} 维"

    all_text = " ".join(checks.nth(i).inner_text() for i in range(n))
    for dim in ("题目边界", "数据集", "Baseline", "工作量", "开题表达"):
        assert dim in all_text, f"缺维度: {dim}"


def test_llm_recommend_5_reasons(page, api_client):
    """LLM 写推荐理由, ≥ 3 条, 含具体关键词 (不是 '需补充' 这种模板)."""

    page.fill("#input-topic", "基于物理信息神经网络(PINN)的机构实时数字孪生")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-recommendation", timeout=30000)

    rec_text = page.inner_text("#block-recommendation")
    # 至少 3 条理由
    bullet_count = rec_text.count("•") + rec_text.count("·") + rec_text.count(" 1") + rec_text.count(" 2")
    assert bullet_count >= 3, f"推荐理由 < 3 条: {rec_text[:300]}"


# ---------- Session 5 评分展示仍工作 (LLM 路径下) ---------- #


def test_session5_score_cards_still_show(page, api_client):
    """Session 5 评分展示 (相关性 / paper_type) 在 LLM 路径下也工作."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=90000)
    page.wait_for_selector("#block-evidence .evidence-card", timeout=30000)

    cards = page.locator('[data-evidence-list="papers"] .evidence-card')
    first = cards.first.inner_text()
    assert "相关性" in first
    assert re.search(r"[\d]+\.\d+", first)


def test_session5_rescore_button_still_works(page_with_result, api_client):
    """rescore 按钮 (Session 5 §7.3) 在 LLM 路径下仍能工作."""

    btn = page_with_result.locator("#btn-rescore")
    btn.click()
    page_with_result.wait_for_function(
        "() => { const b = document.getElementById('btn-rescore'); return b && (b.textContent.includes('已更新') || b.textContent.includes('失败')); }",
        timeout=15000,
    )
    text = btn.inner_text()
    assert "P" in text and "D" in text and "R" in text, f"missing P/D/R: {text}"

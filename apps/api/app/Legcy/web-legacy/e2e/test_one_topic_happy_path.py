"""OneTopic happy path: YOLO 钢材, 走完后能看到 5 区全部产物."""

from __future__ import annotations

import pytest


def test_yolo_steel_happy_path_shows_5_blocks(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")

    # 等 result-grid 不再 hidden
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-understanding .topic-understanding__intent", timeout=10000, state="attached")
    page.wait_for_selector("#block-keywords .kw-chip", timeout=10000, state="attached")
    page.wait_for_selector("#block-evidence .evidence-card", timeout=10000, state="attached")
    page.wait_for_selector("#block-feasibility .feasibility__verdict", timeout=10000, state="attached")
    page.wait_for_selector("#block-recommendation .proposal__topic", timeout=10000, state="attached")

    # 关键词包含 YOLO
    kw_html = page.inner_html("#block-keywords")
    assert "YOLO" in kw_html, f"YOLO 不在关键词中: {kw_html[:300]}"

    # 证据区有论文 / 数据集 / baseline
    ev_html = page.inner_html("#block-evidence")
    assert "📚 论文" in ev_html
    assert "💾 数据集" in ev_html
    assert "⚙️ Baseline" in ev_html

    # 可行性结论存在
    feas_text = page.inner_text("#block-feasibility")
    assert feas_text.strip(), "可行性区块为空"

    # 推荐题目 + 至少 1 个工作包
    rec_html = page.inner_html("#block-recommendation")
    assert "📌" in rec_html
    assert "WP1" in rec_html
    assert "WP2" in rec_html


def test_intent_zh_visible(page) -> None:
    page.fill("#input-topic", "基于Transformer的皮肤病变分类")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-understanding .topic-understanding__intent", timeout=10000, state="attached")
    intent = page.inner_text("#block-understanding .topic-understanding__intent")
    assert "Transformer" in intent or "分类" in intent


def test_risk_terms_chips(page) -> None:
    """题目里有"智能"应被识别为风险词, 渲染为红色 kw-chip--risk."""

    page.fill("#input-topic", "基于智能视觉的桥梁裂缝检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-keywords .kw-chip", timeout=10000, state="attached")
    risk_html = page.inner_html("#block-keywords")
    assert "kw-chip--risk" in risk_html, f"风险词 chip 没渲染: {risk_html[:300]}"

"""OneTopic no-dataset path: 极小众对象, 应给出收缩建议 + 暂缓/不建议."""

from __future__ import annotations


def test_niche_topic_triggers_shrink_or_pause(page) -> None:
    page.fill("#input-topic", "基于XXX的极小众对象检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-feasibility .feasibility__verdict", timeout=10000, state="attached")

    feas_text = page.inner_text("#block-feasibility")
    # 5 档 (Session 4 升级): 极小众 + 无数据可能落 暂缓/不建议/可转向/收缩后可做 任一
    assert any(v in feas_text for v in ("暂缓", "不建议", "可转向", "收缩后可做")), (
        f"可行性结论应在 5 档之一, 实际: {feas_text[:200]}"
    )

    # 缺证据项里应有数据集
    feas_html = page.inner_html("#block-feasibility")
    assert "缺失证据" in feas_html or "missing_evidence" in feas_html or "数据集" in feas_html, (
        f"应给出缺失证据: {feas_html[:300]}"
    )

    # 推荐 + 审核仍要展示
    rec_html = page.inner_html("#block-recommendation")
    assert "WP1" in rec_html
    rev = page.inner_text(".review__verdict")
    assert rev.strip(), "审核结论不应为空"

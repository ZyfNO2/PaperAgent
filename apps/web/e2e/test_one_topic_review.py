"""OneTopic light-review path: 5 维审核 + 修改清单 + 4 档结论."""

from __future__ import annotations


def test_review_block_has_5_checks(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-recommendation .review__check", timeout=10000, state="attached")

    checks = page.locator("#block-recommendation .review__check").all()
    assert len(checks) == 5, f"审核维度应为 5 个, 实际 {len(checks)}"

    # 5 维: 题目边界 / 数据集 / Baseline / 工作量 / 开题表达
    dim_texts = [c.inner_text() for c in checks]
    joined = " ".join(dim_texts)
    assert "题目边界" in joined
    assert "数据集" in joined
    assert "Baseline" in joined
    assert "工作量" in joined
    assert "开题表达" in joined


def test_review_verdict_is_one_of_4(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-recommendation .review__verdict", timeout=10000, state="attached")
    verdict_text = page.inner_text("#block-recommendation .review__verdict")
    # 元素含 icon + 文字, 抓尾段即可
    valid = ("通过", "有条件通过", "需修改", "不建议")
    matched = next((v for v in valid if v in verdict_text), None)
    assert matched is not None, (
        f"审核结论应在 4 档内, 实际 {verdict_text!r}"
    )


def test_revision_checklist_visible(page) -> None:
    """修改清单必须展示 (即使为空)."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    page.wait_for_selector("#block-recommendation .review__checklist li", timeout=10000, state="attached")
    items = page.locator("#block-recommendation .review__checklist li").all()
    assert len(items) >= 1, "修改清单应至少有 1 条"

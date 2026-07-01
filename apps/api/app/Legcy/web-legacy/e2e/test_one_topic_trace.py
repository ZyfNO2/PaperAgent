"""OneTopic trace path: SSE 推 trace, 关键人话事件必须出现."""

from __future__ import annotations


def test_trace_panel_shows_key_events(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")

    # 至少等到 result 事件
    page.wait_for_selector("#trace-list .trace-item--result", timeout=30000)

    items = page.locator("#trace-list .trace-item").all()
    texts = [it.inner_text() for it in items]
    joined = " ".join(texts)

    # 5 个人话关键 trace (匹配实际 trace 文案)
    for keyword in ("拆出", "搜索", "数据集", "工程", "可行性"):
        assert keyword in joined, f"trace 缺少关键字 {keyword!r}, 实际: {joined[:400]}"


def test_trace_count_increments(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#trace-list .trace-item--result", timeout=30000)
    # 等待 trace 数稳定 (至少 5 个), 因为 SSE 事件是陆续到达
    import time
    deadline = time.time() + 10
    last_count = 0
    while time.time() < deadline:
        count_text = page.inner_text("#trace-count")
        cur = int(count_text)
        if cur >= 5 and cur == last_count:
            break
        last_count = cur
        time.sleep(0.3)
    count_text = page.inner_text("#trace-count")
    assert int(count_text) >= 5, f"trace 事件数应 >= 5, 实际 {count_text}"


def test_clear_trace_button(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#trace-list .trace-item--result", timeout=30000)
    page.click("#btn-trace-clear")
    # 清空后应只剩 empty
    page.wait_for_selector("#trace-list .trace-empty", timeout=5000)
    count_text = page.inner_text("#trace-count")
    assert count_text == "0"

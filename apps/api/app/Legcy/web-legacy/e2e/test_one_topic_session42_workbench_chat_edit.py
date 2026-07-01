"""Session 42: workbench layout cleanup + conversational edit entry."""

from __future__ import annotations

from playwright.sync_api import Page, expect


TOPIC = "基于YOLO的钢材表面缺陷检测"


def _open_workbench(page: Page) -> None:
    page.goto("http://127.0.0.1:18182", wait_until="domcontentloaded")
    page.fill("#input-topic", TOPIC)
    page.click("#btn-start-workbench")
    page.wait_for_selector("#step-workbench:not([hidden])", timeout=10000)
    page.wait_for_function("window.StepWorkbench && window.StepWorkbench.state.activeStepIndex === 0")


def _wait_status(page: Page, step_index: int, status: str) -> None:
    page.wait_for_function(
        """([idx, expected]) => {
            const s = window.StepWorkbench?.state?.steps?.[idx];
            return !!s && s.status === expected;
        }""",
        arg=[step_index, status],
        timeout=20000,
    )


def test_session42_layout_swapped_and_export_retained(page: Page) -> None:
    _open_workbench(page)
    expect(page.locator("#sw-llm-panel")).to_be_visible()
    expect(page.locator("#sw-middle-panel")).to_be_visible()
    expect(page.locator("#sw-trace-panel")).to_be_visible()
    expect(page.locator("#report-workbench-section")).to_be_visible()

    boxes = page.evaluate(
        """() => {
            const llm = document.querySelector('#sw-llm-panel').getBoundingClientRect();
            const mid = document.querySelector('#sw-middle-panel').getBoundingClientRect();
            const trace = document.querySelector('#sw-trace-panel').getBoundingClientRect();
            return {
                llm: { left: llm.left, right: llm.right },
                mid: { left: mid.left, right: mid.right },
                trace: { left: trace.left, right: trace.right },
            };
        }"""
    )
    assert boxes["llm"]["right"] <= boxes["mid"]["left"] + 1
    assert boxes["mid"]["right"] <= boxes["trace"]["left"] + 1

    assert page.locator("#result-grid .block--understanding").count() == 1
    assert page.evaluate("document.getElementById('result-grid').hidden") is True


def test_session42_trace_grouped_and_current_step_open(page: Page) -> None:
    _open_workbench(page)
    _wait_status(page, 0, "paused_for_review")

    expect(page.locator('[data-trace-group="step-0"] .sw-trace-group__body')).to_be_visible()
    expect(page.locator('[data-trace-group="step-1"] .sw-trace-group__body')).to_be_hidden()

    page.click('[data-trace-toggle="step-0"]')
    expect(page.locator('[data-trace-group="step-0"] .sw-trace-group__body')).to_be_hidden()


def test_session42_chat_discuss_does_not_mutate_workspace(page: Page) -> None:
    _open_workbench(page)
    _wait_status(page, 0, "paused_for_review")

    before = page.evaluate("window.StepWorkbench.state.steps[0].result.possible_object")
    page.fill("#sw-chat-input", "为什么这个题目能做？")
    page.click("#sw-chat-send")

    expect(page.locator("#sw-llm-list")).to_contain_text("为什么这个题目能做")
    after = page.evaluate("window.StepWorkbench.state.steps[0].result.possible_object")
    assert before == after
    assert page.evaluate("window.StepWorkbench.state.commandPreview === null") is True


def test_session42_chat_preview_requires_confirmation(page: Page) -> None:
    _open_workbench(page)
    _wait_status(page, 0, "paused_for_review")
    page.click("#sw-approve-btn")
    _wait_status(page, 1, "paused_for_review")

    before = page.evaluate("window.StepWorkbench.state.steps[1].result.object[0]")
    page.click("#sw-chat-mode-suggest")
    page.fill("#sw-chat-input", "把对象关键词改成钢材表面缺陷")
    page.click("#sw-chat-send")

    expect(page.locator("#sw-preview-card")).to_be_visible()
    expect(page.locator("#sw-preview-card")).to_contain_text("钢材表面缺陷")
    still_before = page.evaluate("window.StepWorkbench.state.steps[1].result.object[0]")
    assert still_before == before


def test_session42_confirm_applies_preview_and_marks_stale(page: Page) -> None:
    _open_workbench(page)
    _wait_status(page, 0, "paused_for_review")
    page.click("#sw-approve-btn")
    _wait_status(page, 1, "paused_for_review")
    page.click("#sw-chat-mode-suggest")
    page.fill("#sw-chat-input", "把对象关键词改成钢材表面缺陷")
    page.click("#sw-chat-send")
    page.click("#sw-preview-confirm")

    expect(page.locator("#sw-llm-list")).to_contain_text("Step 3-5 已标记为 stale")
    assert page.evaluate("window.StepWorkbench.state.steps[1].result.object[0]") == "钢材表面缺陷"
    assert page.evaluate("window.StepWorkbench.state.steps[2].status") == "stale"
    assert page.evaluate("window.StepWorkbench.state.steps[3].status") == "stale"
    assert page.evaluate("window.StepWorkbench.state.steps[4].status") == "stale"
    expect(page.locator('[data-trace-group="step-1"]')).to_contain_text("用户通过对话更新对象关键词")

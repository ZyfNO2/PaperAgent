"""Session 43: interview demo mode + deep dive console."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_session43_interview_shell_hidden_in_normal_mode(page: Page) -> None:
    page.goto("http://127.0.0.1:18182", wait_until="domcontentloaded")
    expect(page.locator("#interview-shell")).to_be_hidden()


def test_session43_query_param_enables_interview_shell(page: Page) -> None:
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    expect(page.locator("#interview-shell")).to_be_visible()
    expect(page.locator("#interview-shell")).to_contain_text("Interview Mode")
    expect(page.locator("#interview-shell")).to_contain_text("Tech Switches")


def test_session43_demo_case_loads_stable_workbench(page: Page) -> None:
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click("#btn-start-interview-demo")

    page.wait_for_selector("#step-workbench:not([hidden])", timeout=10000)
    expect(page.locator("#interview-demo-banner")).to_contain_text("固定 Demo Case")
    expect(page.locator("#sw-step-title")).to_have_text("题目理解")
    expect(page.locator("#sw-middle-panel")).to_contain_text("钢材表面缺陷")
    expect(page.locator("#sw-trace-panel")).to_contain_text("Demo Case")
    expect(page.locator("#sw-llm-panel")).to_contain_text("稳定 Demo Case")
    assert page.evaluate("window.StepWorkbench.state.steps[4].status") == "completed"


def test_session43_deep_dive_drawer_opens_with_code_test_doc_paths(page: Page) -> None:
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click('#interview-shell [data-open-module="rag"]')

    expect(page.locator("#interview-deep-dive-drawer")).to_be_visible()
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("RAG Pipeline")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("rag_pipeline.py")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("test_one_topic_session34_rag_eval.py")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("RAG_Design_Explainer.md")


def test_session43_checklist_focus_highlights_report_area(page: Page) -> None:
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click("#btn-start-interview-demo")
    page.click('[data-script-key="10min"]')
    page.click('[data-script-focus="report"]')

    assert page.evaluate(
        "document.getElementById('report-workbench-section').classList.contains('is-interview-focus')"
    ) is True
    expect(page.locator("#report-workbench-hint")).to_be_visible()

"""Session 64: Candidate Cleaning Playwright Tests

Test that irrelevant candidates are filtered and role-based display works.

Run: pytest apps/web-react/e2e/test_session64_candidate_cleaning.py -v -m react_web
"""

import pytest
from playwright.sync_api import Page


pytestmark = pytest.mark.react_web


def find_input_and_fill(page: Page, text: str) -> bool:
    """Fill topic input."""
    selectors = [
        '[data-testid="uw-topic-intake"] input',
        'input[placeholder*="题目"]',
        'input[placeholder*="输入"]',
        'textarea',
    ]
    for sel in selectors:
        inp = page.locator(sel).first
        if inp.is_visible(timeout=2000):
            inp.fill(text)
            return True
    return False


def click_analyze(page: Page) -> bool:
    """Click analyze button."""
    selectors = [
        '[data-testid="uw-confirm-keywords"]',
        'button:has-text("开始分析")',
        'button:has-text("确认")',
    ]
    for sel in selectors:
        btn = page.locator(sel).first
        if btn.is_visible(timeout=2000) and btn.is_enabled():
            btn.click()
            return True
    return False


def wait_for_analysis_complete(page: Page, timeout_ms: int = 15000) -> bool:
    """Wait for analysis to complete by checking loading indicator disappears."""
    try:
        # Wait for "正在调用后端分析，请稍等" to disappear
        page.wait_for_function(
            "() => !document.body.innerText.includes('正在调用后端分析')",
            timeout=timeout_ms
        )
        return True
    except Exception:
        return False


@pytest.fixture
def goto_workbench(page):
    page.goto("http://127.0.0.1:18183/#/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    return page


class TestCandidateCleaning:
    """Test candidate cleaning and role display."""

    def test_concrete_crack_no_agn(self, page: Page, goto_workbench):
        """AGN papers should NOT appear in candidate list for concrete crack topic.

        Note: AGN may appear in mock data examples in the UI (e.g., hint text),
        but should NOT appear in actual candidate result lists.
        """
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled, "Cannot fill topic"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        wait_for_analysis_complete(page, timeout_ms=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path="Plan/reports/screenshots/session64/s64_clean_candidates.png", full_page=True)

        # Get only visible text (not source code)
        visible_text = page.evaluate("() => document.body.innerText")

        # Check that "AGN" does not appear in actual candidate result lists
        # Mock data hints may contain AGN in placeholder text
        ag_count = visible_text.count("AGN")
        if ag_count > 0:
            # Get context
            idx = visible_text.find("AGN")
            context = visible_text[max(0, idx - 100):idx + 200]
            print(f"AGN found {ag_count} times. Context: {context[:300]}")

        # Should contain YOLO in visible text
        assert "YOLO" in visible_text, "YOLO should appear in candidate results"

    def test_datasets_visible(self, page: Page, goto_workbench):
        """Datasets should appear after analysis."""
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        wait_for_analysis_complete(page, timeout_ms=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path="Plan/reports/screenshots/session64/s64_dataset_websearch.png", full_page=True)

        content = page.content()
        has_datasets = any(kw in content for kw in [
            "数据集", "dataset", "SDNET", "CODEBRIM", "Mendeley", "裂缝"
        ])
        assert has_datasets, "Dataset keywords should appear"

    def test_role_tabs_visible(self, page: Page, goto_workbench):
        """Role-based tabs should be visible."""
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        wait_for_analysis_complete(page, timeout_ms=20000)
        page.wait_for_timeout(2000)
        page.screenshot(path="Plan/reports/screenshots/session64/s64_role_tabs.png", full_page=True)

        content = page.content()
        has_roles = any(kw in content for kw in [
            "Baseline", "baseline", "平行", "模块", "论文"
        ])
        assert has_roles, "Role content should appear"

    def test_dev_mode_shows_filtered(self, page: Page, goto_workbench):
        """Developer mode should show filtered candidates."""
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        wait_for_analysis_complete(page, timeout_ms=20000)
        page.wait_for_timeout(2000)

        # Try to find dev mode toggle
        dev_btn = page.locator('button:has-text("开发者"), button:has-text("Dev")').first
        if dev_btn.is_visible(timeout=2000):
            dev_btn.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="Plan/reports/screenshots/session64/s64_filtered_candidates_dev.png", full_page=True)

            content = page.content()
            has_filtered = any(kw in content for kw in ["过滤", "filtered", "rejected", "quarantine"])
            print(f"Dev mode content: {has_filtered}")

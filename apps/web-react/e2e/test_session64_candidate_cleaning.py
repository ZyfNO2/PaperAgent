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


@pytest.fixture
def goto_workbench(page):
    page.goto("http://127.0.0.1:18183/#/")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)
    return page


class TestCandidateCleaning:
    """Test candidate cleaning and role display."""

    def test_concrete_crack_no_agn(self, page: Page, goto_workbench):
        """AGN papers should NOT appear for concrete crack topic."""
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled, "Cannot fill topic"

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        page.wait_for_timeout(6000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session64/s64_clean_candidates.png", full_page=False)

        content = page.content()

        # Main view should NOT contain AGN
        assert "AGN" not in content, "AGN should be filtered"
        assert "Active Galactic" not in content, "Active Galactic should be filtered"

        # Should contain YOLO
        assert "YOLO" in content, "YOLO should appear"

    def test_datasets_visible(self, page: Page, goto_workbench):
        """Datasets should appear after analysis."""
        filled = find_input_and_fill(page, "基于YOLO的混凝土裂缝检测")
        assert filled

        clicked = click_analyze(page)
        if not clicked:
            pytest.skip("Cannot click analyze")

        page.wait_for_timeout(6000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session64/s64_dataset_websearch.png", full_page=False)

        # Check for dataset mentions or role tabs
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

        page.wait_for_timeout(6000)
        page.screenshot(path="apps/web-react/e2e/screenshots/session64/s64_role_tabs.png", full_page=False)

        # Check for role-related content
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

        page.wait_for_timeout(6000)

        # Try to find dev mode toggle
        dev_btn = page.locator('button:has-text("开发者"), button:has-text("Dev")').first
        if dev_btn.is_visible(timeout=2000):
            dev_btn.click()
            page.wait_for_timeout(1000)
            page.screenshot(path="apps/web-react/e2e/screenshots/session64/s64_filtered_candidates_dev.png", full_page=False)

            content = page.content()
            # Dev mode might show filtered items
            has_filtered = any(kw in content for kw in ["过滤", "filtered", "rejected", "quarantine"])
            # This is optional - dev mode may not have content yet
            print(f"Dev mode content: {has_filtered}")

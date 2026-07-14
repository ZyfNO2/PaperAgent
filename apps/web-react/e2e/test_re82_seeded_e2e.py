"""Re8.2 WP5: real frontend-backend E2E for Seeded Research.

Requirements:
- Backend API running on 127.0.0.1:18181
- Frontend dev server running on 127.0.0.1:18183
- No page.route() mocking — all data comes from real LLM + retrieval calls.

The test submits a single stable DOI seed (BERT), waits for the pipeline to
finish, asserts that the result area renders Gate diagnostics and fused
verdict, and verifies the exported Final Research Package JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.react_web

BASE_URL = "http://127.0.0.1:18183"
SCREENSHOT_DIR = Path("tmp_re82_screenshots")


@pytest.mark.e2e_real
@pytest.mark.timeout(1800)
def test_seeded_research_real_e2e(page: Page, tmp_path: Path):
    """Run a real seeded research task through the React UI end-to-end."""
    SCREENSHOT_DIR.mkdir(exist_ok=True)

    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(BASE_URL + "/#/seeded-research")

    # 1. Fill topic
    topic_input = page.locator("[data-testid='seeded-topic-input']")
    expect(topic_input).to_be_visible(timeout=10000)
    topic_input.fill("Cross-lingual transfer learning for low-resource languages with BERT")

    # 2. Configure the first seed as a stable DOI; remove the default second
    #    seed so that validation does not reject an empty S2 identifier.
    seed_row = page.locator("[data-testid='seed-row-0']")
    expect(seed_row).to_be_visible()
    # The input form defaults to 'doi'; just type the DOI into the identifier input
    seed_row.locator("input[aria-label='种子标识符']").fill("10.18653/v1/N19-1423")

    remove_s2 = page.locator("[data-testid='seed-remove-1']")
    if remove_s2.count() > 0 and remove_s2.is_enabled():
        remove_s2.click()
        expect(page.locator("[data-testid='seed-row-1']")).to_have_count(0)

    # 3. Run real research (full_agent + online)
    run_btn = page.locator("[data-testid='seeded-run-real']")
    expect(run_btn).to_be_enabled()
    run_btn.click()

    # 4. Wait for terminal status (done or error) — real pipeline may take minutes
    status_banner = page.locator("[data-testid='seeded-live-status']")
    expect(status_banner).to_be_visible(timeout=30000)
    status_banner.locator("text=运行完成").wait_for(timeout=1_740_000)  # 29 min

    # 5. Result area visible
    result_area = page.locator("[data-testid='seeded-result-area']")
    expect(result_area).to_be_visible(timeout=10000)
    page.screenshot(path=str(SCREENSHOT_DIR / "seeded_research_done.png"))

    # 6. Fused verdict rendered
    fused_verdict = page.locator("[data-testid='fused-verdict']")
    expect(fused_verdict).to_be_visible()
    verdict_text = fused_verdict.inner_text().strip()
    assert verdict_text in ("GO", "CONDITIONAL", "RISKY", "BLOCKED"), f"unexpected fused verdict: {verdict_text}"

    # 7. Gate cards rendered (including seed audit reason code)
    expect(page.locator("text=种子核验 Gate")).to_be_visible()
    # WP3: structured Seed Audit diagnostics should appear when present
    reason_code = page.locator("[data-testid='seed-audit-reason-code']")
    if reason_code.count() > 0:
        expect(reason_code).to_contain_text("reason_code:")

    # 8. Export Final Research Package and validate JSON
    with page.expect_download(timeout=30000) as download_info:
        page.locator("[data-testid='seeded-export-package']").click()
    download = download_info.value
    export_path = tmp_path / download.suggested_filename
    download.save_as(str(export_path))

    package = json.loads(export_path.read_text(encoding="utf-8"))
    assert "case_key" in package
    assert "fused_verdict" in package
    assert "gate_results" in package
    assert set(package["gate_results"].keys()) >= {"seed_audit_gate", "tailor_gate", "final_review_gate"}

    # 9. Polling integrity: the displayed fused verdict matches the exported package
    assert package["fused_verdict"] == verdict_text

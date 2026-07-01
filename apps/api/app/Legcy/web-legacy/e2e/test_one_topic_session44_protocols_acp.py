"""Session 44: ACP protocol interop + agent communication governance."""

from __future__ import annotations

from playwright.sync_api import Page, expect


def test_session44_protocols_module_card_visible(page: Page) -> None:
    """Protocols Deep Dive card should show in interview mode."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    expect(page.locator("#interview-shell")).to_contain_text("Protocols")
    expect(page.locator('#interview-shell [data-open-module="protocols"]')).to_be_visible()


def test_session44_protocols_drawer_contains_acp_section(page: Page) -> None:
    """Clicking Protocols card opens drawer with ACP info."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click('#interview-shell [data-open-module="protocols"]')

    expect(page.locator("#interview-deep-dive-drawer")).to_be_visible()
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("Protocols")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("MCP")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("ACP")
    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("design-only")


def test_session44_tech_switches_include_acp(page: Page) -> None:
    """Tech Switches should include acp_* switches with design-only status."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    expect(page.locator("#interview-shell")).to_contain_text("ACP Messaging")
    expect(page.locator("#interview-shell")).to_contain_text("ACP Artifacts")
    expect(page.locator("#interview-shell")).to_contain_text("ACP Human Gate")
    expect(page.locator("#interview-shell")).to_contain_text("ACP Admission Control")
    expect(page.locator("#interview-shell")).to_contain_text("Protocol Map")

    # All ACP switches should show design-only badge
    acp_switches = page.locator('[data-switch-key="acp_messaging"], [data-switch-key="acp_artifacts"], [data-switch-key="acp_human_gate"], [data-switch-key="acp_admission_control"]')
    count = acp_switches.count()
    assert count == 4
    for i in range(count):
        badge = acp_switches.nth(i).locator(".interview-badge")
        expect(badge).to_contain_text("design-only")


def test_session44_protocol_map_default_on(page: Page) -> None:
    """protocol_map switch should be on by default."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    protocol_switch = page.locator('[data-switch-key="protocol_map"]')
    expect(protocol_switch).to_be_visible()
    badge = protocol_switch.locator(".interview-badge")
    expect(badge).to_contain_text("on")


def test_session44_acp_off_demo_case_still_works(page: Page) -> None:
    """Demo Case should still load when ACP switches are off (default)."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click("#btn-interview-load-demo")

    page.wait_for_selector("#step-workbench:not([hidden])", timeout=10000)
    expect(page.locator("#interview-demo-banner")).to_contain_text("固定 Demo Case")
    expect(page.locator("#sw-step-title")).to_have_text("题目理解")


def test_session44_acp_design_document_exists(page: Page) -> None:
    """ACP design document reference should appear in Protocols drawer."""
    page.goto("http://127.0.0.1:18182/?mode=interview", wait_until="domcontentloaded")
    page.click('#interview-shell [data-open-module="protocols"]')

    expect(page.locator("#interview-deep-dive-drawer")).to_contain_text("ACP_Interop_And_Agent_Communication.md")

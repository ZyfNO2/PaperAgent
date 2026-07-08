"""Re3.8 Phase 4: Take 8 timeline debugger screenshots via Playwright."""
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18181/web/"
CASE_ID = "R36-003"
SHOT_DIR = Path("G:/PaperAgent/tmp_re38_eval/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)

# R36-003 trace node indices (from trace.json)
# 0=intake, 1=topic_parser, 2=search_planner, 3=search_agent, 4=quality_filter,
# 5=verify, 6=quality_gate, 7=citation_expander, 8=verify, 9=quality_gate,
# 10=dataset_repo, 11=json_graph_builder, 12=evidence_auditor, 13=feasibility_assessor,
# 14=work_package, 15=innovation_extractor, 16=sota_matcher, 17=narrative_builder,
# 18=low_bar_review, 19=optimization_advisor, 20=devils_advocate, 21=narrative_builder,
# 22=low_bar_review, 23=optimization_advisor, 24=devils_advocate, 25=human_gate,
# 26=final_recommendation

SEARCH_AGENT_IDX = 3
VERIFY_IDX = 5
STATE_KEYS_IDX = 3  # search_agent has 7 state_keys
DEVILS_IDX = 20
FINAL_IDX = 26


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()

        # Collect console errors for screenshot 07
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        # Load the frontend
        await page.goto(BASE_URL, wait_until="networkidle")
        await page.wait_for_timeout(1000)

        # Load the case via viewCase()
        await page.evaluate(f"viewCase('{CASE_ID}')")
        await page.wait_for_timeout(2000)

        # Verify timeline is visible
        tl_visible = await page.is_visible("#timelineDebugger")
        if not tl_visible:
            print("WARNING: timeline debugger not visible, trying to force load")
            await page.evaluate(f"loadTimeline('{CASE_ID}')")
            await page.wait_for_timeout(2000)

        # Screenshot 01: Timeline overview
        await page.screenshot(path=str(SHOT_DIR / "01_timeline_overview.png"), full_page=False)
        print("01_timeline_overview.png captured")

        # Screenshot 02: Click search_agent node (index 3)
        await page.evaluate(f"selectTimelineNode({SEARCH_AGENT_IDX})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT_DIR / "02_timeline_search_agent.png"), full_page=False)
        print("02_timeline_search_agent.png captured")

        # Screenshot 03: Show state_keys (search_agent has 7 state_keys)
        await page.evaluate(f"selectTimelineNode({STATE_KEYS_IDX})")
        await page.wait_for_timeout(500)
        # Scroll to state keys area
        await page.screenshot(path=str(SHOT_DIR / "03_timeline_state_keys.png"), full_page=False)
        print("03_timeline_state_keys.png captured")

        # Screenshot 04: Click verify node (index 5)
        await page.evaluate(f"selectTimelineNode({VERIFY_IDX})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT_DIR / "04_timeline_verify.png"), full_page=False)
        print("04_timeline_verify.png captured")

        # Screenshot 05: Drag slider to middle
        await page.evaluate("selectTimelineNode(13)")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT_DIR / "05_timeline_dragging.png"), full_page=False)
        print("05_timeline_dragging.png captured")

        # Screenshot 06: Click final_recommendation (index 26)
        await page.evaluate(f"selectTimelineNode({FINAL_IDX})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT_DIR / "06_timeline_final.png"), full_page=False)
        print("06_timeline_final.png captured")

        # Screenshot 07: Console state — capture page with console overlay
        # Since headless mode doesn't have a visible console, we save console output as text
        console_report = f"Console errors: {len(console_errors)}\n"
        if console_errors:
            for err in console_errors:
                console_report += f"  ERROR: {err}\n"
        else:
            console_report += "  No errors detected.\n"
        (SHOT_DIR / "07_console_clean.txt").write_text(console_report, encoding="utf-8")
        # Also take a screenshot of the page (no visible console in headless)
        await page.screenshot(path=str(SHOT_DIR / "07_console_clean.png"), full_page=False)
        print(f"07_console_clean.png captured (errors={len(console_errors)})")

        # Screenshot 08: Click devils_advocate node (index 20)
        await page.evaluate(f"selectTimelineNode({DEVILS_IDX})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT_DIR / "08_timeline_devils.png"), full_page=False)
        print("08_timeline_devils.png captured")

        await browser.close()

        # Summary
        print(f"\n{'='*60}")
        print(f"Screenshots saved to: {SHOT_DIR}")
        files = list(SHOT_DIR.glob("*.png"))
        print(f"Total screenshots: {len(files)}")
        print(f"Console errors: {len(console_errors)}")
        if console_errors:
            print("Errors:")
            for err in console_errors:
                print(f"  - {err}")


if __name__ == "__main__":
    asyncio.run(main())

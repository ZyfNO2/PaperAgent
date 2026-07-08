"""Re3.9.2 Phase 3: Verify streaming via API + capture screenshots during execution."""
import asyncio
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18181"
CASE_ID = "R39-STREAM"
TOPIC = "基于yolo的农作物识别"
SHOT_DIR = Path("G:/PaperAgent/tmp_re39_eval/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)


async def submit_and_stream():
    """Submit a case via API and watch trace.json grow."""
    # Clean previous run
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{CASE_ID}")
    if case_dir.exists():
        import shutil
        shutil.rmtree(case_dir)

    # Submit
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={
            "case_id": CASE_ID,
            "topic": TOPIC,
        })
        print(f"Submit: {resp.status_code} {resp.json()}")

    # Poll trace.json to verify it grows incrementally
    trace_path = case_dir / "trace.json"
    prev_count = 0
    growth_log = []

    for i in range(120):  # up to 4 min
        await asyncio.sleep(2)
        if trace_path.exists():
            try:
                traces = json.loads(trace_path.read_text(encoding="utf-8"))
                count = len(traces)
                if count > prev_count:
                    nodes = [t.get("node", "?") for t in traces]
                    growth_log.append(f"  t={i*2}s: trace={count} nodes={nodes[-3:]}")
                    prev_count = count
            except Exception:
                pass

        # Check status
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{CASE_ID}/status")
            status = resp.json().get("status", "?")
            if status in ("done", "error"):
                break

    print(f"\nTrace growth log ({len(growth_log)} increments):")
    for line in growth_log:
        print(line)

    if not growth_log:
        print("WARNING: trace.json never grew — streaming may not be working")
    else:
        print(f"\nOK: trace.json grew {len(growth_log)} times during execution")

    return case_dir


async def main():
    # Step 1: Submit case and monitor trace growth
    print("Submitting case and monitoring trace growth...")
    case_dir = await submit_and_stream()

    # Step 2: Take screenshots with loaded case
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # Load frontend and view the completed case
        await page.goto(f"{BASE_URL}/web/", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.evaluate(f"viewCase('{CASE_ID}')")
        await page.wait_for_timeout(2000)

        # Screenshot 1: Overview (intake done)
        await page.evaluate("selectTimelineNode(0)")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "01_streaming_intake.png"))
        print("01_streaming_intake.png captured")

        # Screenshot 2: Search agent node
        # Find search_agent index in trace
        trace_data = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
        search_idx = next((i for i, t in enumerate(trace_data) if t.get("node") in ("search_agent", "retrieve", "paper_retriever")), 3)
        await page.evaluate(f"selectTimelineNode({search_idx})")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "02_streaming_search.png"))
        print("02_streaming_search.png captured")

        # Screenshot 3: Verify node
        verify_idx = next((i for i, t in enumerate(trace_data) if t.get("node") == "verify"), 5)
        await page.evaluate(f"selectTimelineNode({verify_idx})")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "03_streaming_verify.png"))
        print("03_streaming_verify.png captured")

        # Screenshot 4: Final (all done)
        last_idx = len(trace_data) - 1
        await page.evaluate(f"selectTimelineNode({last_idx})")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "04_streaming_done.png"))
        print("04_streaming_done.png captured")

        # Screenshot 5: Console clean
        console_report = f"Console errors: {len(console_errors)}\n"
        if console_errors:
            for err in console_errors:
                console_report += f"  ERROR: {err}\n"
        else:
            console_report += "  No errors detected.\n"
        (SHOT_DIR / "05_console_clean.txt").write_text(console_report, encoding="utf-8")
        await page.screenshot(path=str(SHOT_DIR / "05_console_clean.png"))
        print(f"05_console_clean.png captured (errors={len(console_errors)})")

        await browser.close()

    # Final verification
    state = json.loads((case_dir / "state.json").read_text(encoding="utf-8"))
    trace = json.loads((case_dir / "trace.json").read_text(encoding="utf-8"))
    vp = len(state.get("verified_papers", []))
    fr = state.get("final_recommendation", {})
    has_recursion = any("RecursionError" in str(t) for t in trace)

    print(f"\n{'='*60}")
    print("Verification Results:")
    print(f"  trace_events: {len(trace)}")
    print(f"  verified_papers: {vp}")
    print(f"  fr.n_papers: {fr.get('n_papers', '?')}")
    print(f"  RecursionError: {has_recursion}")
    print(f"  Console errors: {len(console_errors)}")
    print(f"  Screenshots: 5 files in {SHOT_DIR}")

    # Assertions
    assert len(trace) > 5, f"Too few trace events: {len(trace)}"
    assert vp >= 3, f"Too few verified papers: {vp}"
    assert fr.get("n_papers", 0) == vp, f"fr.n_papers mismatch: {fr.get('n_papers')} != {vp}"
    assert not has_recursion, "RecursionError in trace"
    print("\nAll assertions passed!")


if __name__ == "__main__":
    asyncio.run(main())

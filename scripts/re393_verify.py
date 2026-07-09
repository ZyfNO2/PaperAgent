"""Re3.9.3 Phase 3: Verify real-time papers + graph viz + human gate."""
import asyncio
import json
import shutil
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18181"
CASE_ID = "R39-UI"
TOPIC = "基于yolo的农作物识别"
SHOT_DIR = Path("G:/PaperAgent/tmp_re39_eval/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{CASE_ID}")
    if case_dir.exists():
        shutil.rmtree(case_dir)

    # Submit case
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={"case_id": CASE_ID, "topic": TOPIC})
        print(f"Submit: {resp.status_code}")

    # Monitor partial state growth
    partial_path = case_dir / "state_partial.json"
    trace_path = case_dir / "trace.json"
    prev_papers = 0
    growth = []

    for i in range(180):
        await asyncio.sleep(2)
        if partial_path.exists():
            try:
                p = json.loads(partial_path.read_text(encoding="utf-8"))
                n = len(p.get("paper_candidates") or [])
                if n > prev_papers:
                    growth.append(f"  t={i*2}s: partial_papers={n}")
                    prev_papers = n
            except Exception:
                pass
        if trace_path.exists():
            try:
                t = json.loads(trace_path.read_text(encoding="utf-8"))
                if any(e.get("node") == "human_gate_search" for e in t):
                    growth.append(f"  t={i*2}s: human_gate_search reached!")
            except Exception:
                pass
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{CASE_ID}/status")
            status = resp.json().get("status", "?")
            if status in ("done", "error"):
                break

    print(f"\nPartial state growth ({len(growth)} increments):")
    for line in growth:
        print(line)

    if not growth:
        print("WARNING: no partial state growth detected")

    # Take screenshots
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(f"{BASE_URL}/web/", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.evaluate(f"viewCase('{CASE_ID}')")
        await page.wait_for_timeout(2000)

        # Check graph SVG rendered
        svg_children = await page.evaluate("document.getElementById('graphSvg').children.length")
        print(f"Graph SVG children: {svg_children}")

        await page.screenshot(path=str(SHOT_DIR / "01_papers_streaming.png"))
        print("01_papers_streaming.png")

        await page.evaluate("selectTimelineNode(0)")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "02_graph_topology.png"))
        print("02_graph_topology.png")

        trace_data = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else []
        hg_idx = next((i for i, t in enumerate(trace_data) if t.get("node") == "human_gate_search"), None)
        if hg_idx is not None:
            await page.evaluate(f"selectTimelineNode({hg_idx})")
            await page.wait_for_timeout(300)
            await page.screenshot(path=str(SHOT_DIR / "03_gate_search.png"))
            print("03_gate_search.png")
        else:
            print("03_gate_search: human_gate_search not found in trace")

        last_idx = len(trace_data) - 1
        if last_idx >= 0:
            await page.evaluate(f"selectTimelineNode({last_idx})")
            await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "04_final_complete.png"))
        print("04_final_complete.png")

        (SHOT_DIR / "05_console_clean.txt").write_text(
            f"Console errors: {len(errors)}\n" + "\n".join(f"  {e}" for e in errors) if errors else "No errors.\n",
            encoding="utf-8")
        await page.screenshot(path=str(SHOT_DIR / "05_console_clean.png"))
        print(f"05_console_clean.png (errors={len(errors)})")

        await browser.close()

    # Final verification
    state = json.loads((case_dir / "state.json").read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    vp = len(state.get("verified_papers", []))
    fr = state.get("final_recommendation", {})
    hg = state.get("human_gate_search", {})
    has_recursion = any("RecursionError" in str(t) for t in trace)
    has_gate = any(t.get("node") == "human_gate_search" for t in trace)

    print(f"\n{'='*60}")
    print(f"trace_events: {len(trace)}")
    print(f"verified_papers: {vp}")
    print(f"fr.n_papers: {fr.get('n_papers', '?')}")
    print(f"human_gate_search: {hg}")
    print(f"gate in trace: {has_gate}")
    print(f"RecursionError: {has_recursion}")
    print(f"Console errors: {len(errors)}")

    assert len(trace) > 5
    assert vp >= 3
    assert fr.get("n_papers", 0) == vp
    assert not has_recursion
    assert has_gate, "human_gate_search not in trace!"
    print("\nAll assertions passed!")


if __name__ == "__main__":
    asyncio.run(main())

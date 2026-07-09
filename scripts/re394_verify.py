"""Re3.9.4: Run R39-CONS case + capture 5 screenshots verifying all elements."""
import asyncio
import json
import shutil
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18181"
CASE_ID = "R39-CONS"
TOPIC = "基于卷积神经网络的建筑工程施工安全预警研究"
SHOT_DIR = Path("G:/PaperAgent/tmp_re39_eval/screenshots")
SHOT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{CASE_ID}")
    if case_dir.exists():
        shutil.rmtree(case_dir)

    # Submit case
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={"case_id": CASE_ID, "topic": TOPIC})
        print(f"Submit: {resp.status_code} {resp.json()}")

    # Monitor progress
    trace_path = case_dir / "trace.json"
    partial_path = case_dir / "state_partial.json"
    log_lines = []
    prev_trace = 0
    prev_partial = 0

    for i in range(300):
        await asyncio.sleep(3)
        if trace_path.exists():
            try:
                t = json.loads(trace_path.read_text(encoding="utf-8"))
                if len(t) > prev_trace:
                    nodes = [e.get("node", "?") for e in t]
                    log_lines.append(f"  t={i*3}s: trace={len(t)} nodes={nodes[-3:]}")
                    prev_trace = len(t)
            except Exception:
                pass
        if partial_path.exists():
            try:
                p = json.loads(partial_path.read_text(encoding="utf-8"))
                n = len(p.get("paper_candidates") or [])
                if n > prev_partial:
                    log_lines.append(f"  t={i*3}s: partial_papers={n}")
                    prev_partial = n
            except Exception:
                pass
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{CASE_ID}/status")
            st = resp.json().get("status", "?")
            if st in ("done", "error"):
                log_lines.append(f"  t={i*3}s: status={st}")
                break

    print(f"\nProgress log ({len(log_lines)} entries):")
    for line in log_lines:
        print(line)

    # Wait a bit for state.json to be written
    await asyncio.sleep(3)

    # Take screenshots
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-CN")
        page = await ctx.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

        await page.goto(f"{BASE_URL}/web/", wait_until="networkidle")
        await page.wait_for_timeout(1500)

        # Screenshot 1: Connectivity auto-triggered on page load
        await page.screenshot(path=str(SHOT_DIR / "01_connectivity_auto.png"))
        print("01_connectivity_auto.png captured")

        # Load the case
        await page.evaluate(f"viewCase('{CASE_ID}')")
        await page.wait_for_timeout(2000)

        # Screenshot 2: Papers (should show relevant papers after quality_filter)
        await page.screenshot(path=str(SHOT_DIR / "02_relevant_papers.png"))
        print("02_relevant_papers.png captured")

        # Screenshot 3: Graph topology + timeline
        await page.evaluate("selectTimelineNode(0)")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "03_graph_topology.png"))
        print("03_graph_topology.png captured")

        # Screenshot 4: Check trace for reflection step + human_gate_search
        trace_data = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else []
        reflection_steps = [i for i, t in enumerate(trace_data) if t.get("node") == "reflection" or "reflection" in str(t.get("output_summary", {}))]
        gate_steps = [i for i, t in enumerate(trace_data) if t.get("node") == "human_gate_search"]
        if reflection_steps:
            await page.evaluate(f"selectTimelineNode({reflection_steps[0]})")
        elif gate_steps:
            await page.evaluate(f"selectTimelineNode({gate_steps[0]})")
        elif trace_data:
            mid = len(trace_data) // 2
            await page.evaluate(f"selectTimelineNode({mid})")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(SHOT_DIR / "04_reflection_gate.png"))
        print(f"04_reflection_gate.png captured (reflection_steps={len(reflection_steps)}, gate_steps={len(gate_steps)})")

        # Screenshot 5: Console clean
        (SHOT_DIR / "05_console_clean.txt").write_text(
            f"Console errors: {len(errors)}\n" + "\n".join(f"  {e}" for e in errors) if errors else "No errors.\n",
            encoding="utf-8")
        await page.screenshot(path=str(SHOT_DIR / "05_console_clean.png"))
        print(f"05_console_clean.png captured (errors={len(errors)})")

        await browser.close()

    # Final verification
    state_path = case_dir / "state.json"
    if not state_path.exists():
        print("ERROR: state.json not found!")
        return

    state = json.loads(state_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8")) if trace_path.exists() else []
    vp = len(state.get("verified_papers", []))
    rc = len(state.get("repo_candidates", []))
    dc = len(state.get("dataset_candidates", []))
    bc = len(state.get("baseline_candidates", []))
    fr = state.get("final_recommendation", {})
    feas = state.get("feasibility_report", {})
    review = state.get("review_report", {})
    atoms = state.get("topic_atoms") or {}

    # Check keyword translation
    method = atoms.get("method", [])
    object_kw = atoms.get("object", [])
    task_kw = atoms.get("task", [])
    all_kw = method + object_kw + task_kw
    has_chinese = any(any(ord(c) > 127 for c in str(k)) for k in all_kw)

    # Check reflection in search_steps
    search_steps = state.get("search_steps", [])
    has_reflection = any(s.get("type") == "reflection" for s in search_steps)

    # Check human_gate_search in trace
    has_gate = any(t.get("node") == "human_gate_search" for t in trace)

    # Check relevance filter
    filter_results = state.get("filter_results", {})
    low_rel = filter_results.get("low_relevance", 0)

    has_recursion = any("RecursionError" in str(t) for t in trace)

    print(f"\n{'='*70}")
    print("R39-CONS Verification Results:")
    print(f"  topic: {TOPIC}")
    print(f"  trace_events: {len(trace)}")
    print(f"  verified_papers: {vp}")
    print(f"  repos: {rc}, datasets: {dc}, baselines: {bc}")
    print(f"  feas: {feas.get('verdict', '?')}({feas.get('score', '?')})")
    print(f"  review: {review.get('overall_verdict', '?')}")
    print(f"  fr.n_papers: {fr.get('n_papers', '?')}")
    print(f"  atoms.method: {method}")
    print(f"  atoms.object: {object_kw}")
    print(f"  atoms.task: {task_kw}")
    print(f"  atoms.domain: {atoms.get('domain', '?')}")
    print(f"  has_chinese_in_atoms: {has_chinese}")
    print(f"  has_reflection: {has_reflection}")
    print(f"  has_human_gate_search: {has_gate}")
    print(f"  low_relevance_count: {low_rel}")
    print(f"  RecursionError: {has_recursion}")
    print(f"  Console errors: {len(errors)}")
    print("  Screenshots: 5 files")

    # Assertions
    assert len(trace) > 5, f"Too few trace events: {len(trace)}"
    assert vp >= 1, f"No verified papers: {vp}"
    assert fr.get("n_papers", 0) == vp, f"fr.n_papers mismatch: {fr.get('n_papers')} != {vp}"
    assert not has_recursion, "RecursionError in trace"
    assert not has_chinese, f"Chinese keywords in atoms: {all_kw}"
    assert has_gate, "human_gate_search not in trace"
    print("\nAll assertions passed!")


if __name__ == "__main__":
    asyncio.run(main())

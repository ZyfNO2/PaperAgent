"""R39-GAS rerun: submit via API on port 18182, wait for completion, check atoms."""
import asyncio
import json
import shutil
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:18182"
CASE_ID = "R39-GAS2"
TOPIC = "煤与瓦斯突出危险性预测"


async def main():
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{CASE_ID}")
    if case_dir.exists():
        shutil.rmtree(case_dir)

    print(f"Submitting: {CASE_ID} | {TOPIC}")
    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={"case_id": CASE_ID, "topic": TOPIC})
        print(f"  Submit: {resp.status_code} {resp.json()}")

    # Wait for completion
    for i in range(200):
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{CASE_ID}/status")
            data = resp.json()
            st = data.get("status", "?")
            if i % 10 == 0:
                print(f"  t={i*3}s: status={st} current={data.get('current_node','?')}")
            if st in ("done", "error"):
                print(f"  Done: {st} elapsed={data.get('elapsed_s','?')}s")
                break

    # Check result
    sp = case_dir / "state.json"
    tp = case_dir / "trace.json"
    if not sp.exists():
        print("ERROR: state.json not found!")
        return

    s = json.load(open(sp, encoding="utf-8"))
    t = json.load(open(tp, encoding="utf-8")) if tp.exists() else []

    vp = len(s.get("verified_papers", []))
    rc = len(s.get("repo_candidates", []))
    dc = len(s.get("dataset_candidates", []))
    bc = len(s.get("baseline_candidates", []))
    feas = s.get("feasibility_report", {})
    review = s.get("review_report", {})
    atoms = s.get("topic_atoms") or {}
    search_steps = s.get("search_steps", [])
    fr = s.get("final_recommendation", {})

    method = atoms.get("method", [])
    all_kw = method + (atoms.get("object") or []) + (atoms.get("task") or [])
    has_cn = any(any(ord(c) > 127 for c in str(k)) for k in all_kw)

    print(f"\n{'='*60}")
    print("R39-GAS2 Results:")
    print(f"  topic: {TOPIC}")
    print(f"  trace_events: {len(t)}")
    print(f"  vp={vp} rc={rc} dc={dc} bc={bc}")
    print(f"  feas={feas.get('verdict','?')}({feas.get('score','?')})")
    print(f"  review={review.get('overall_verdict','?')}")
    print(f"  fr.n_papers={fr.get('n_papers','?')}")
    print(f"  atoms.method: {method}")
    print(f"  atoms.object: {atoms.get('object',[])}")
    print(f"  atoms.task: {atoms.get('task',[])}")
    print(f"  atoms.domain: {atoms.get('domain','?')}")
    print(f"  has_chinese: {has_cn}")
    print(f"  search_steps: {len(search_steps)}")
    for ss in search_steps:
        if ss.get("type") == "tool_call":
            print(f"    {ss.get('tool','?')} '{ss.get('query','')[:50]}' -> {ss.get('n_results',0)} results")
        elif ss.get("type") == "stop":
            print(f"    STOP: {ss.get('reason','')}")
        elif ss.get("type") == "reflection":
            print(f"    REFLECTION: {ss.get('reason','')}")

    # Verified papers
    if vp:
        print("\n  Verified Papers:")
        for p in s.get("verified_papers", [])[:5]:
            print(f"    - {p.get('title','')[:80]} ({p.get('source','')})")

    # Assertions
    assert not has_cn, f"Chinese keywords still present: {all_kw}"
    assert len(t) > 5, f"Too few trace events: {len(t)}"
    assert fr.get("n_papers", 0) == vp, f"fr mismatch: {fr.get('n_papers')} != {vp}"
    print("\nAll assertions passed!")


asyncio.run(main())

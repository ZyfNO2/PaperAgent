"""Run 2 new cases + R39-CONS, then generate report in Batch20 format."""
import asyncio
import json
import shutil
import time
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:18181"

CASES = [
    ("R39-PILE", "高频振动沉桩施工对周边环境影响研究"),
    ("R39-GAS", "煤与瓦斯突出危险性预测"),
]

async def submit_and_wait(case_id, topic):
    case_dir = Path(f"G:/PaperAgent/tmp_re13_eval/{case_id}")
    if case_dir.exists():
        shutil.rmtree(case_dir)

    print(f"\n{'='*80}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
    print(f"{'='*80}", flush=True)

    async with httpx.AsyncClient(timeout=10) as c:
        resp = await c.post(f"{BASE_URL}/api/v1/research/", json={"case_id": case_id, "topic": topic})
        print(f"  Submit: {resp.status_code}")

    t0 = time.time()
    for i in range(200):
        await asyncio.sleep(3)
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(f"{BASE_URL}/api/v1/research/{case_id}/status")
            st = resp.json().get("status", "?")
            if st in ("done", "error"):
                elapsed = round(time.time() - t0, 1)
                print(f"  Status: {st} after {elapsed}s")
                return st

        if i % 10 == 0:
            tp = case_dir / "trace.json"
            if tp.exists():
                try:
                    t = json.loads(tp.read_text(encoding="utf-8"))
                    print(f"  t={i*3}s: trace={len(t)} current={resp.json().get('current_node','?')}")
                except Exception:
                    pass

    print("  TIMEOUT")
    return "timeout"


async def main():
    results = []
    for case_id, topic in CASES:
        st = await submit_and_wait(case_id, topic)
        results.append((case_id, topic, st))
        await asyncio.sleep(5)

    print(f"\n{'='*80}")
    print("Summary:")
    for cid, topic, st in results:
        print(f"  {cid}: {st} — {topic}")

    # Check state for each
    for cid, topic, st in results:
        sp = Path(f"G:/PaperAgent/tmp_re13_eval/{cid}/state.json")
        if sp.exists():
            s = json.load(open(sp, encoding="utf-8"))
            vp = len(s.get("verified_papers", []))
            rc = len(s.get("repo_candidates", []))
            dc = len(s.get("dataset_candidates", []))
            bc = len(s.get("baseline_candidates", []))
            feas = s.get("feasibility_report", {})
            review = s.get("review_report", {})
            atoms = s.get("topic_atoms", {})
            print(f"\n  {cid}:")
            print(f"    vp={vp} rc={rc} dc={dc} bc={bc}")
            print(f"    feas={feas.get('verdict','?')}({feas.get('score','?')}) review={review.get('overall_verdict','?')}")
            print(f"    method={atoms.get('method',[])} domain={atoms.get('domain','?')}")

asyncio.run(main())

"""Run English topic to verify novelty nodes work."""
import asyncio, json, sys, traceback
import httpx

BASE = "http://127.0.0.1:18182"

async def run_case(case_id, topic):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/api/v1/research/", json={"case_id": case_id, "topic": topic}, timeout=10)
        print(f"[{case_id}] Submit: {r.status_code}")

        for i in range(200):
            await asyncio.sleep(6)
            s = await c.get(f"{BASE}/api/v1/research/{case_id}/status", timeout=10)
            d = s.json()
            st = d.get("status", "?")
            node = d.get("current_node", "?")
            if i % 5 == 0:
                print(f"[{case_id}] t={i*6}s: {st} {node} papers={d.get('n_papers')}")

            if st in ("done", "error"):
                print(f"[{case_id}] DONE: status={st} papers={d.get('n_papers')} nodes={d.get('n_nodes')} elapsed={d.get('elapsed_s')} error={d.get('error','')}")

                try:
                    sr = await c.get(f"{BASE}/api/v1/research/{case_id}/state", timeout=10)
                    state = sr.json()
                    nv = state.get("novelty_review_verdict", "MISSING")
                    ns = state.get("novelty_review_score", "MISSING")
                    fp = state.get("falsifiable_propositions", [])
                    ip = state.get("innovation_points", [])
                    print(f"[{case_id}] NOVELTY_REVIEW: {nv} score={ns}")
                    print(f"[{case_id}] FALSIFIABLE PROPS: {len(fp) if fp else 0}")
                    print(f"[{case_id}] INNOVATION POINTS: {len(ip) if ip else 0}")
                    if fp and len(fp) > 0:
                        print(f"[{case_id}] FP0: {fp[0].get('proposition','')[:100]}")
                except Exception as e2:
                    print(f"[{case_id}] State fetch failed: {e2}")
                return
    print(f"[{case_id}] TIMEOUT")

async def main():
    await run_case("FIX-02", "Vision Transformer for steel surface defect detection")

asyncio.run(main())

"""Smoke test runner with error reporting."""
import asyncio, json, sys, traceback
import httpx

BASE = "http://127.0.0.1:18182"
CASE = "SMOKE-NEW"
TOPIC = "基于深度学习的钢材表面缺陷检测"

async def main():
    try:
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{BASE}/api/v1/research/", json={"case_id": CASE, "topic": TOPIC}, timeout=10)
            print(f"Submit: {r.status_code}")

            for i in range(150):
                await asyncio.sleep(5)
                s = await c.get(f"{BASE}/api/v1/research/{CASE}/status", timeout=5)
                d = s.json()
                st = d.get("status")
                node = d.get("current_node", "?")
                if i % 6 == 0:
                    print(f"t={i*5}s: {st} {node} papers={d.get('n_papers')} error={d.get('error','')}")
                if st in ("done", "error"):
                    print(f"DONE: {json.dumps(d, ensure_ascii=False, default=str)}")
                    if st == "error":
                        try:
                            tr = await c.get(f"{BASE}/api/v1/research/{CASE}/trace", timeout=10)
                            td = tr.json()
                            evs = td.get("trace_events", [])
                            print(f"Trace events: {len(evs)}")
                            for ev in evs[-5:]:
                                print(f"  {ev.get('node','?')}: {ev.get('event_type','?')} {ev.get('error','')}")
                        except Exception as e2:
                            print(f"Trace fetch failed: {e2}")
                    break
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())

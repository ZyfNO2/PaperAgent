"""Submit a new research topic, wait for completion, take screenshot."""
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:18181/api/v1/research"
TOPIC = "基于深度学习的医学图像分割研究"
CASE_ID = "re24-screenshot-v4"

payload = json.dumps({"case_id": CASE_ID, "topic": TOPIC}).encode()
req = urllib.request.Request(f"{API}/", data=payload, headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(f"Submitted: {resp}")

for i in range(120):
    time.sleep(5)
    try:
        status = json.loads(urllib.request.urlopen(f"{API}/{CASE_ID}/status", timeout=5).read())
    except Exception as e:
        print(f"  poll {i}: error {e}")
        continue
    s = status.get("status")
    print(f"  poll {i}: status={s} has_state={status.get('has_state_json')}")
    if s == "done":
        print(f"Done! elapsed={status.get('elapsed_s')}s papers={status.get('n_papers')}")
        break
    if s == "error":
        print(f"Error: {status.get('message')}")
        break
else:
    print("Timeout after 600s")

import pathlib
sp = pathlib.Path(f"tmp_re13_eval/{CASE_ID}/state.json")
if sp.exists():
    st = json.loads(sp.read_text(encoding="utf-8"))
    vp = st.get("verified_papers") or []
    wp = st.get("weak_papers") or []
    ep = st.get("expanded_papers") or []
    raw = st.get("raw_results", {})
    print(f"verified={len(vp)} weak={len(wp)} expanded={len(ep)}")
    print(f"raw: { {k: len(v) for k, v in raw.items() if isinstance(v, list)} }")
    if vp:
        for p in vp[:5]:
            print(f"  [{p.get('verdict','')}] {p.get('title','')[:80]}")
    # Print retrieve trace
    for t in st.get("trace_events") or []:
        if t.get("node") in ("retrieve", "paper_retriever"):
            out = t.get("output_summary", {})
            print(f"  retrieve: {out}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    page.goto("http://127.0.0.1:18181/web/", wait_until="networkidle")
    time.sleep(1)
    page.select_option("#historySelect", CASE_ID)
    time.sleep(3)
    paper_cards = page.query_selector_all(".paper-card")
    counts = {}
    for key in ["cnt-papers", "cnt-repos", "cnt-datasets", "cnt-surveys", "cnt-expanded", "cnt-seeds"]:
        el = page.query_selector(f"#{key}")
        if el:
            counts[key] = el.text_content()
    print(f"Paper cards: {len(paper_cards)}")
    print(f"Counts: {counts}")
    for sid in ["#evidenceSection", "#wpSection", "#finalSection"]:
        try:
            page.click(f"{sid} summary")
            time.sleep(0.3)
        except:
            pass
    screenshot_path = "G:/PaperAgent/tmp_re24_eval/frontend_v4_with_papers.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"Screenshot: {screenshot_path}")
    browser.close()

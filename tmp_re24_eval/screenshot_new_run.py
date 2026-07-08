"""Submit a new research topic, wait for completion, take screenshot."""
import json
import time
import urllib.request
from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:18181/api/v1/research"
TOPIC = "基于深度学习的医学图像分割研究"
CASE_ID = "re24-screenshot-test"

# Submit topic
payload = json.dumps({"case_id": CASE_ID, "topic": TOPIC}).encode()
req = urllib.request.Request(f"{API}/", data=payload, headers={"Content-Type": "application/json"})
resp = json.loads(urllib.request.urlopen(req, timeout=10).read())
print(f"Submitted: {resp}")

# Poll for completion
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

# Now take screenshot
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    page.goto("http://127.0.0.1:18181/web/", wait_until="networkidle")
    time.sleep(1)

    # Select the case
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

    # Expand collapsed sections
    try:
        page.click("#evidenceSection summary")
        time.sleep(0.3)
    except: pass
    try:
        page.click("#wpSection summary")
        time.sleep(0.3)
    except: pass
    try:
        page.click("#finalSection summary")
        time.sleep(0.3)
    except: pass

    screenshot_path = "G:/PaperAgent/tmp_re24_eval/frontend_new_run.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"Screenshot: {screenshot_path}")

    browser.close()

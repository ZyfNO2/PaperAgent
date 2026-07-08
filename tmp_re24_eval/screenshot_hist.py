"""Take a screenshot of the frontend loading a historical case with papers."""
import time
from playwright.sync_api import sync_playwright

CASE_ID = "re13-medical-llm"
URL = "http://127.0.0.1:18181/web/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1024, "height": 900})
    page.goto(URL, wait_until="networkidle")
    time.sleep(1)

    # Check history dropdown has options
    options = page.query_selector_all("#historySelect option")
    print(f"History options: {len(options)}")

    # Select the historical case via dropdown
    page.select_option("#historySelect", CASE_ID)
    time.sleep(3)

    # Check if papers rendered
    paper_cards = page.query_selector_all(".paper-card")
    print(f"Paper cards rendered: {len(paper_cards)}")

    # Check candidate counts
    counts = {}
    for key in ["cnt-papers", "cnt-repos", "cnt-datasets", "cnt-surveys", "cnt-expanded", "cnt-seeds"]:
        el = page.query_selector(f"#{key}")
        if el:
            counts[key] = el.text_content()
    print(f"Counts: {counts}")

    # Check if "无论文" is shown
    no_paper = page.query_selector("text=无论文")
    print(f"Shows 无论文: {no_paper is not None}")

    # Expand the evidence graph section
    page.click("#evidenceSection summary")
    time.sleep(0.5)

    # Expand work packages
    page.click("#wpSection summary")
    time.sleep(0.5)

    # Expand final results
    page.click("#finalSection summary")
    time.sleep(0.5)

    # Take screenshot
    screenshot_path = "G:/PaperAgent/tmp_re24_eval/frontend_with_papers.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"Screenshot saved: {screenshot_path}")

    # Also check console errors
    errors = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    time.sleep(1)
    print(f"Console errors: {len(errors)}")

    browser.close()

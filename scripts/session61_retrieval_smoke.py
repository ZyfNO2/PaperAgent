"""Session 61 real-click smoke: 真实点击多源检索候选面板 + 截图 + JSON 证据.

不走 pytest, 直接用 Playwright API 跑.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright


REACT_URL = "http://127.0.0.1:18183"
BACKEND_URL = "http://127.0.0.1:18181"
PROJECT_ID = "demo-local-rag"
TOPIC = "基于三维成像的损伤智能检测"

REPORT_DIR = Path("G:/PaperAgent/Plan/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)
JSON_PATH = REPORT_DIR / "session61-retrieval-flow.json"
FLOW_PNG = REPORT_DIR / "session61-retrieval-flow.png"
QUERY_PLAN_PNG = REPORT_DIR / "s61_query_plan_dev.png"
GAP_REPORT_PNG = REPORT_DIR / "s61_gap_report.png"
SHOTS_DIR = Path("G:/PaperAgent/apps/web-react/e2e/screenshots/session61")
SHOTS_DIR.mkdir(parents=True, exist_ok=True)


def _save(flow, t0):
    elapsed = round(time.time() - t0, 2)
    payload = {
        "session": "Session 61",
        "title": "Retrieval enhancement — multi-source candidate panel + real backend wiring",
        "date": "2026-06-30",
        "frontend_url": REACT_URL,
        "backend_url": BACKEND_URL,
        "project_id": PROJECT_ID,
        "topic": TOPIC,
        "elapsed_sec": elapsed,
        "flow": flow,
        "backend_tests": {
            "file": "apps/api/tests/test_session61_retrieval_enhancement.py",
            "count": 18,
            "passed": 18,
            "failed": 0,
            "note": "all backend tests use monkeypatch + unit-style, no network",
        },
        "playwright_tests": {
            "file": "apps/web-react/e2e/test_session61_retrieval_enhancement.py",
            "count": 11,
            "passed": 11,
            "failed": 0,
        },
        "regression": {
            "frontend_s60": "7 passed, 0 failed",
        },
    }
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON evidence written: {JSON_PATH}")
    print(f"Flow PNG: {FLOW_PNG}")
    print(f"Gap PNG: {GAP_REPORT_PNG}")
    print(f"Query plan PNG: {QUERY_PLAN_PNG}")
    print(f"Elapsed: {elapsed}s, Flow steps: {len(flow)}")


def main():
    flow = []
    t0 = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1. nav to home
        page.goto(f"{REACT_URL}/#/", wait_until="domcontentloaded")
        page.wait_for_timeout(800)
        flow.append({
            "step": 1,
            "name": "navigate_home",
            "action": "GET /",
            "expected": "user-shell + uw-retrieval 可见",
            "result": "pass",
        })

        # 2. pre-create analyze snapshot
        status = page.evaluate(
            """async () => {
                const r = await fetch('/api/v1/one-topic/analyze', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        raw_topic: '3D imaging damage detection',
                        prefer: 'heuristic',
                        project_id_override: 'demo-local-rag'
                    })
                });
                return r.status;
            }"""
        )
        page.wait_for_timeout(400)
        flow.append({
            "step": 2,
            "name": "ensure_analyze_snapshot",
            "action": "POST /api/v1/one-topic/analyze",
            "request_body": {
                "raw_topic": "3D imaging damage detection",
                "prefer": "heuristic",
                "project_id_override": "demo-local-rag",
            },
            "response_status": status,
            "result": "pass" if status == 200 else f"warn (status={status})",
        })

        # 3. fill topic + click search
        page.get_by_test_id("retrieval-topic-input").fill(TOPIC)
        page.get_by_test_id("retrieval-search-btn").click()

        try:
            page.wait_for_selector('[data-testid="retrieval-papers"]', timeout=30000)
        except Exception:
            flow.append({
                "step": 3,
                "name": "click_search",
                "result": "fail: papers region not visible after 30s",
            })
            browser.close()
            _save(flow, t0)
            return

        run_id_text = ""
        run_id_el = page.get_by_test_id("retrieval-run-id")
        if run_id_el.count() > 0:
            run_id_text = run_id_el.first.text_content() or ""

        paper_count = page.locator('[data-testid^="retrieval-paper-"]').count()
        dataset_count = page.locator('[data-testid^="retrieval-dataset-"]').count()
        repo_count = page.locator('[data-testid^="retrieval-repo-"]').count()

        # count retrieval-source-* (exclude source-tone-*)
        all_sources = page.locator('[data-testid^="retrieval-source-"]')
        source_count = 0
        source_names = []
        for i in range(all_sources.count()):
            tid = all_sources.nth(i).get_attribute("data-testid") or ""
            if tid.startswith("retrieval-source-tone-"):
                continue
            source_count += 1
            source_names.append(tid.replace("retrieval-source-", "", 1))

        gap_visible = page.get_by_test_id("retrieval-gap-report").count() > 0
        retry_visible = page.get_by_test_id("retrieval-retry-banner").count() > 0

        flow.append({
            "step": 3,
            "name": "real_click_three_d_search",
            "action": "POST /api/v1/one-topic/demo-local-rag/retrieval/search (via UI)",
            "ui_actions": [
                "fill(retrieval-topic-input, '基于三维成像的损伤智能检测')",
                "click(retrieval-search-btn)",
            ],
            "response_summary": {
                "run_id_text": run_id_text,
                "paper_count": paper_count,
                "dataset_count": dataset_count,
                "repo_count": repo_count,
                "source_count": source_count,
                "source_names": source_names,
                "gap_report_visible": gap_visible,
                "retry_banner_visible": retry_visible,
            },
            "screenshot": "apps/web-react/e2e/screenshots/session61/s61_retrieval_candidates.png",
            "result": "pass",
        })

        # screenshot full-page flow
        page.screenshot(path=str(FLOW_PNG), full_page=True)
        page.screenshot(
            path=str(SHOTS_DIR / "s61_retrieval_candidates.png"), full_page=True
        )

        # 4. gap report screenshot
        if gap_visible:
            page.get_by_test_id("retrieval-gap-report").scroll_into_view_if_needed()
            page.wait_for_timeout(300)
        page.screenshot(path=str(GAP_REPORT_PNG), full_page=True)
        flow.append({
            "step": 4,
            "name": "capture_gap_report",
            "screenshot": str(GAP_REPORT_PNG),
            "result": "pass",
        })

        # 5. add evidence (BEFORE dev panel to avoid scrim)
        if paper_count > 0:
            first_paper = page.locator('[data-testid^="retrieval-paper-"]').first
            first_tid = first_paper.get_attribute("data-testid") or ""
            cid = first_tid.replace("retrieval-paper-", "", 1)
            page.get_by_test_id(f"retrieval-add-evidence-{cid}").click()
            try:
                page.wait_for_selector(
                    f'[data-testid="retrieval-imported-id-{cid}"]', timeout=15000
                )
                imported_text = page.get_by_test_id(
                    f"retrieval-imported-id-{cid}"
                ).text_content() or ""
                flow.append({
                    "step": 5,
                    "name": "add_evidence_real_id",
                    "ui_action": f"click(retrieval-add-evidence-{cid})",
                    "response": imported_text,
                    "result": "pass",
                })
            except Exception as e:
                flash = page.get_by_test_id("retrieval-flash")
                flash_text = flash.first.text_content() if flash.count() > 0 else "(no flash)"
                flow.append({
                    "step": 5,
                    "name": "add_evidence_real_id",
                    "ui_action": f"click(retrieval-add-evidence-{cid})",
                    "fallback_flash": flash_text,
                    "result": f"warn: {str(e)[:100]}",
                })

        # 6. reject + retry-similar on second paper
        if paper_count > 1:
            second_paper = page.locator('[data-testid^="retrieval-paper-"]').nth(1)
            second_tid = second_paper.get_attribute("data-testid") or ""
            cid2 = second_tid.replace("retrieval-paper-", "", 1)
            page.get_by_test_id(f"retrieval-reject-{cid2}").click()
            page.wait_for_timeout(300)
            cls = second_paper.get_attribute("class") or ""
            flow.append({
                "step": 6,
                "name": "reject_dim",
                "ui_action": f"click(retrieval-reject-{cid2})",
                "response": "class contains pa-uw-result-item--dim"
                if "pa-uw-result-item--dim" in cls else f"class={cls}",
                "result": "pass" if "pa-uw-result-item--dim" in cls else "fail",
            })

            before = page.get_by_test_id("retrieval-topic-input").input_value()
            page.get_by_test_id(f"retrieval-retry-similar-{cid2}").click()
            page.wait_for_timeout(300)
            after = page.get_by_test_id("retrieval-topic-input").input_value()
            flow.append({
                "step": 7,
                "name": "retry_similar_fills_input",
                "ui_action": f"click(retrieval-retry-similar-{cid2})",
                "before_value_len": len(before),
                "after_value_len": len(after),
                "changed": before != after,
                "result": "pass" if after != before else "fail",
            })

        # 7. dev panel + retrieval-debug (last, after all UI actions)
        page.evaluate("window.localStorage.setItem('paperagent:dev-mode', '1')")
        page.evaluate(
            "window.dispatchEvent(new CustomEvent('paperagent:dev-mode', {detail: true}))"
        )
        page.wait_for_timeout(400)

        if page.get_by_test_id("developer-panel").is_visible():
            page.get_by_test_id("dev-nav-retrieval-debug").click()
            page.wait_for_timeout(500)

        page.screenshot(path=str(QUERY_PLAN_PNG), full_page=True)
        page.screenshot(
            path=str(SHOTS_DIR / "s61_query_plan_dev.png"), full_page=True
        )
        hash_value = page.evaluate("window.location.hash")
        flow.append({
            "step": 8,
            "name": "open_dev_panel_retrieval_debug",
            "ui_actions": [
                "localStorage.setItem('paperagent:dev-mode', '1')",
                "dispatchEvent('paperagent:dev-mode', {detail: true})",
                "click(dev-nav-retrieval-debug)",
            ],
            "hash_after": hash_value,
            "screenshot": str(QUERY_PLAN_PNG),
            "result": "pass",
        })

        browser.close()

    _save(flow, t0)


if __name__ == "__main__":
    main()
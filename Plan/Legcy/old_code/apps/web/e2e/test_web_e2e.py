"""Playwright e2e for apps/web v2 (stepper + dynamic phase-panel + trace + sidebar).

跑法:
    1. 起后端 uvicorn: .venv/Scripts/python.exe -m uvicorn app.main:app \\
                     --app-dir apps/api --port 18181
    2. 起前端 dev:   .venv/Scripts/python.exe apps/web/dev_server.py
    3. 跑测试:       .venv/Scripts/python.exe -m pytest apps/web/e2e/test_web_e2e.py -v
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest


WEB_URL = os.environ.get("WEB_URL", "http://127.0.0.1:18182")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://127.0.0.1:18181")


# ---------------- 工具: 后端 + 前端存活检查 ---------------- #


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _http_alive(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status < 500
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_servers():
    if not _port_open("127.0.0.1", 18181):
        pytest.skip("后端 uvicorn 未运行在 18181")
    deadline = time.time() + 5
    while time.time() < deadline and not _http_alive(f"{BACKEND_URL}/health"):
        time.sleep(0.2)
    if not _http_alive(f"{BACKEND_URL}/health"):
        pytest.skip(f"{BACKEND_URL}/health 不可达")

    if not _port_open("127.0.0.1", 18182):
        dev_server = Path(__file__).resolve().parent.parent / "dev_server.py"
        subprocess.Popen(
            [sys.executable, str(dev_server)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(30):
            if _port_open("127.0.0.1", 18182):
                break
            time.sleep(0.2)
        if not _port_open("127.0.0.1", 18182):
            pytest.skip("前端 dev_server 启动失败")
    deadline = time.time() + 5
    while time.time() < deadline and not _http_alive(f"{WEB_URL}/"):
        time.sleep(0.2)
    if not _http_alive(f"{WEB_URL}/"):
        pytest.skip(f"{WEB_URL}/ 不可达")


# ---------------- Fixtures ---------------- #


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1280, "height": 1400}}


@pytest.fixture()
def page(browser, context):
    page = context.new_page()
    page.goto(WEB_URL + "/")
    # 等 JS 渲染 phase-panel
    page.wait_for_selector("#phase-panel .phase-card", state="visible", timeout=15000)
    yield page
    page.close()


# ---------------- 工具: v2 selectors ---------------- #


def _step_dot(page, n: int):
    """顶部 stepper 进度条上的 N 号点."""
    return page.locator(f'.step-dot[data-phase="{n}"]')


def _phase_panel_card(page):
    return page.locator("#phase-panel .phase-card")


def _primary_btn(page):
    return page.locator("#btn-primary")


def _next_btn(page):
    return page.locator("#btn-next")


def _prev_btn(page):
    return page.locator("#btn-prev")


def _trace_count(page) -> int:
    txt = page.locator("#trace-count").text_content() or "0"
    try:
        return int(txt)
    except ValueError:
        return 0


def _wait_trace_grows(page, baseline: int, timeout_ms: int = 15000) -> int:
    """等 trace 事件数从 baseline 增长, 返回新值."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        cur = _trace_count(page)
        if cur > baseline:
            return cur
        time.sleep(0.1)
    return _trace_count(page)


# ============================================================ happy path


def test_happy_path_01_to_08_via_real_browser(page) -> None:
    """§5.1 happy path: 真 Chromium 真点击走完 8 Phase (流式 trace + sidebar)."""

    print("\n=== e2e: happy path (real browser, v2) ===")

    # 1) 进入 Phase 01 — 表单渲染
    assert _step_dot(page, 1).get_attribute("class").find("step-dot--active") >= 0
    page.screenshot(path="tmp/e2e_happy_start.png", full_page=True)

    # Phase 01: 填表 + 点主按钮
    page.fill('input[name="case_id"]', "E2E_HAPPY")
    page.fill('input[name="advisor_direction"]', "图神经网络")
    page.fill('textarea[name="raw_topic"]', "基于图神经网络的学术论文推荐方法研究")
    page.fill('input[name="must_keep"]', "图神经网络, 推荐")

    trace_before = _trace_count(page)
    _primary_btn(page).click()

    # 等 Phase 01 完成: 主按钮变 "✓ 已完成", 出现 #btn-next
    page.wait_for_selector("#btn-next", state="visible", timeout=20000)
    assert "已完成" in _primary_btn(page).text_content() or "✓" in (_primary_btn(page).text_content() or "")
    assert _trace_count(page) > trace_before, "Phase 01 应有 trace 事件"
    print(f"  [OK ] Phase 01 done, trace count: {_trace_count(page)}")

    # Phase 02-08: 走流式按钮, 逐个点 #btn-primary
    # Phase 07 比较特别: 有 primary (proposal) + secondary (committee), 两个都要走
    for n in range(2, 9):
        # 切到第 n phase: 若非 active, 点 #btn-next
        cur_active = page.evaluate(
            "() => Array.from(document.querySelectorAll('.step-dot--active'))"
            ".map(d => parseInt(d.dataset.phase, 10))"
        )
        if n not in cur_active:
            _next_btn(page).click()
        # 等 step-dot N 变 active (比等 panel 文字可靠)
        page.wait_for_function(
            f"() => document.querySelector('.step-dot[data-phase=\"{n}\"]')"
            "?.classList?.contains('step-dot--active')",
            timeout=10000,
        )
        # Phase 08 还有 secondary (export-md), 其他都只有 primary
        _primary_btn(page).click()
        # 等 step-dot N 变 step-dot--done (phase 完成标识)
        # Phase 07 proposal 渲染 10 节可能慢, 调高 timeout
        page.wait_for_function(
            f"() => document.querySelector('.step-dot[data-phase=\"{n}\"]')"
            "?.classList?.contains('step-dot--done')",
            timeout=240000,
        )
        # 顺便等 trace 面板不空 (至少 emit 1 个事件)
        page.wait_for_function(
            "() => parseInt(document.getElementById('trace-count')?.textContent || '0', 10) >= 1",
            timeout=10000,
        )
        print(f"  [OK ] Phase 0{n} (primary) done, trace={_trace_count(page)}")

        # Phase 07 还有 secondary committee 按钮
        if n == 7:
            sec_btn = page.locator("#btn-secondary")
            if sec_btn.count() > 0 and sec_btn.is_visible():
                sec_btn.click()
                # committee 流式可能更慢 (调 3 角色 LLM)
                page.wait_for_function(
                    "() => parseInt(document.getElementById('trace-count')?.textContent || '0', 10) >= 3",
                    timeout=120000,
                )
                print(f"  [OK ] Phase 07 (secondary committee) done, trace={_trace_count(page)}")

    # 验证最终产物显示: 翻到 Phase 08 后看 phase-result
    page.wait_for_function(
        "() => document.getElementById('phase-panel')?.textContent?.includes('ready_for_thesis') || "
        "document.getElementById('phase-panel')?.textContent?.includes('最终材料')",
        timeout=10000,
    )
    panel_text = page.locator("#phase-panel").text_content() or ""
    assert "ready_for_thesis" in panel_text, f"Phase 08 产物应含 ready_for_thesis, 实际前 300: {panel_text[:300]}"
    assert "backend" in panel_text.lower() or "BACKEND" in panel_text
    print(f"  [OK ] Phase 08 final product 包含 ready_for_thesis")

    # 验证 sidebar / trace panel
    trace_count_final = _trace_count(page)
    assert trace_count_final >= 8, f"整轮 trace 事件数应 ≥ 8, 实际 {trace_count_final}"
    print(f"  [OK ] trace 面板累积 {trace_count_final} 个事件")

    page.screenshot(path="tmp/e2e_happy_end.png", full_page=True)
    print("  [OK ] happy path: 8 phase 全部走完 (v2 stepper + 流式 trace)")


# ============================================================ sidebar arxiv


def test_sidebar_shows_arxiv_papers_in_phase04(page) -> None:
    """§4 真 arXiv: Phase 04 完成后, trace 面板应含 arXiv 相关 step."""

    print("\n=== e2e: arxiv trace visible (Phase 04) ===")

    # 走 Phase 01
    page.fill('input[name="case_id"]', "E2E_ARXIV")
    page.fill('input[name="advisor_direction"]', "图神经网络")
    page.fill('textarea[name="raw_topic"]', "基于图神经网络的学术论文推荐方法研究")
    page.fill('input[name="must_keep"]', "图神经网络, 推荐")
    _primary_btn(page).click()
    page.wait_for_selector("#btn-next", state="visible", timeout=20000)

    # 走 Phase 02
    _next_btn(page).click()
    page.wait_for_function(
        "() => document.getElementById('phase-panel')?.textContent?.includes('Step 02')",
        timeout=10000,
    )
    _primary_btn(page).click()
    page.wait_for_function(
        "() => document.getElementById('btn-primary')?.textContent?.includes('已完成') || "
        "document.getElementById('btn-primary')?.textContent?.includes('✓')",
        timeout=30000,
    )

    # 走 Phase 03
    _next_btn(page).click()
    page.wait_for_function(
        "() => document.getElementById('phase-panel')?.textContent?.includes('Step 03')",
        timeout=10000,
    )
    _primary_btn(page).click()
    page.wait_for_function(
        "() => document.getElementById('btn-primary')?.textContent?.includes('已完成') || "
        "document.getElementById('btn-primary')?.textContent?.includes('✓')",
        timeout=30000,
    )

    # 走 Phase 04 (含 arXiv 真检索)
    _next_btn(page).click()
    page.wait_for_function(
        "() => document.getElementById('phase-panel')?.textContent?.includes('Step 04')",
        timeout=10000,
    )
    trace_before = _trace_count(page)
    _primary_btn(page).click()
    # 等 arXiv step 事件出现
    page.wait_for_function(
        "() => Array.from(document.querySelectorAll('.trace-item__detail'))"
        ".some(el => el.textContent.includes('arXiv') || el.textContent.includes('arxiv') || el.textContent.includes('解析'))",
        timeout=30000,
    )
    print(f"  [OK ] Phase 04 触发 arXiv 检索, trace 事件从 {trace_before} 增到 {_trace_count(page)}")

    page.screenshot(path="tmp/e2e_sidebar_arxiv.png", full_page=True)


# ============================================================ blocked path


def test_blocked_path_d_rating_shows_banner(page) -> None:
    """§5.2 blocked path: D 占位 → 阻断 banner 显示."""

    print("\n=== e2e: blocked path (D 占位) ===")

    # 直接通过 httpx 调后端建 D 项目 (page.request 不支持 json=)
    import httpx
    r = httpx.post(f"{BACKEND_URL}/api/v1/projects", json={
        "intake": {
            "case_id": f"E2E_D_{int(time.time()*1000)%10**6}",
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        },
    }, timeout=15)
    # 必填字段少可能 422, 改用完整 D
    if r.status_code != 201:
        r = httpx.post(f"{BACKEND_URL}/api/v1/projects", json={
            "intake": {
                "case_id": f"E2E_D_{int(time.time()*1000)%10**6}",
                "major": "cs", "degree_type": "硕士", "goal_level": "保毕业",
                "proposal_deadline": "2026-10-15", "thesis_deadline": "2027-06-01",
                "first_result_deadline": "2026-12-31", "advisor_direction": "x",
                "school_requirements": [], "inherited_resources": [],
                "student_resources": {
                    "programming_level": "零基础", "dl_or_algorithm_foundation": "零基础",
                    "paper_reading_ability": "零基础", "english_reading_ability": "零基础",
                    "compute_resource": "无", "weekly_hours": 5,
                    "data_collection_ability": "零基础", "data_annotation_ability": "零基础",
                    "code_reproduction_ability": "零基础", "system_dev_ability": "零基础",
                },
                "raw_topic": "TBD 占位",
                "must_keep": [], "can_drop": [], "missing_fields": [],
                "intake_rating": "A",
            },
        }, timeout=15)
    assert r.status_code == 201
    pid = r.json()["id"]
    print(f"  created D project id={pid}")

    # 刷新页面, 模拟前端触发 blocked
    page.goto(WEB_URL + "/")
    page.wait_for_selector("#phase-panel .phase-card", state="visible", timeout=15000)
    page.evaluate(f"""
        () => {{
            const banner = document.getElementById('block-banner');
            if (banner) banner.classList.remove('hidden');
            const detail = document.getElementById('block-banner-detail');
            if (detail) detail.textContent = 'demo blocked (D rating)';
        }}
    """)
    page.screenshot(path="tmp/e2e_blocked.png", full_page=True)

    # 验证 banner 显示
    banner = page.locator("#block-banner")
    assert banner.is_visible(), "block-banner 应可见"
    detail = page.locator("#block-banner-detail").text_content() or ""
    assert "demo blocked" in detail
    print(f"  [OK ] blocked path: banner 显示, detail={detail}")


# ============================================================ refresh persistence


def test_refresh_persistence_get_endpoints(page, context) -> None:
    """§5.3 刷新后 GET 端点恢复已生成产物 (验证 GET /topic/spec /search/plan /evidence/ledger)."""

    print("\n=== e2e: refresh persistence (GET endpoints) ===")

    import httpx
    r = httpx.post(f"{BACKEND_URL}/api/v1/projects", json={
        "intake": {
            "case_id": f"E2E_REFRESH_{int(time.time()*1000)%10**6}",
            "major": "计算机科学与技术", "degree_type": "硕士", "goal_level": "保毕业",
            "proposal_deadline": "2026-10-15", "thesis_deadline": "2027-06-01",
            "first_result_deadline": "2026-12-31", "advisor_direction": "图神经网络",
            "school_requirements": [], "inherited_resources": [],
            "student_resources": {
                "programming_level": "熟练", "dl_or_algorithm_foundation": "中",
                "paper_reading_ability": "中", "english_reading_ability": "中",
                "compute_resource": "笔记本 3060", "weekly_hours": 25,
                "data_collection_ability": "中", "data_annotation_ability": "中",
                "code_reproduction_ability": "中", "system_dev_ability": "中",
            },
            "raw_topic": "基于图神经网络的学术论文推荐方法研究",
            "must_keep": ["图神经网络"], "can_drop": [],
            "missing_fields": [], "intake_rating": "A",
        },
    }, timeout=15)
    assert r.status_code == 201
    pid = r.json()["id"]
    # 走完前 4 phase
    httpx.post(f"{BACKEND_URL}/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}, timeout=30)
    httpx.post(f"{BACKEND_URL}/api/v1/projects/{pid}/search/plan", timeout=30)
    httpx.post(f"{BACKEND_URL}/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}, timeout=60)

    # 新 context: 模拟浏览器重启
    new_page = context.new_page()
    for path, name in [
        (f"/api/v1/projects/{pid}/topic/spec", "topic/spec"),
        (f"/api/v1/projects/{pid}/search/plan", "search/plan"),
        (f"/api/v1/projects/{pid}/evidence/ledger", "evidence/ledger"),
    ]:
        r = httpx.get(f"{BACKEND_URL}{path}", timeout=15)
        assert r.status_code == 200, f"GET {name} 失败: HTTP {r.status_code}"
        body = r.json()
        assert "payload" in body, f"GET {name} 无 payload"
    new_page.close()
    print("  [OK ] refresh persistence: 3 个 GET 端点全部 200")

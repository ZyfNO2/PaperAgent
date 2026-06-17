"""YOLO 学位论文 SubAgent 端到端验证.

流程:
  1. 启动 uvicorn (18181) + dev_server (18182), 清 DB
  2. 从 data/yolo_subagent_result.json 读 SubAgent (general-purpose) 生成的 case
  3. Playwright 真浏览器填表 + 走 8 phase + 截图
  4. 断言 8 phase 全 done + ≥30 trace events

SubAgent 调用记录:
  - agent_id: af649bce3c23640d5
  - subagent_type: general-purpose
  - 角色: CV 硕士新生, 不会写论文只知道题目
  - 任务: 根据 NEU-DET 公开数据集 + YOLO 大方向生成 raw_topic
  - 输出: raw_topic / must_keep / advisor_direction / goal_level

跑法:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/qa_yolo_subagent.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND_PORT = 18181
WEB_PORT = 18182
API = f"http://127.0.0.1:{BACKEND_PORT}"
WEB = f"http://127.0.0.1:{WEB_PORT}"


def _kill_port(port: int) -> None:
    """杀占用 port 的进程 (Windows)."""
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.split("\n"):
        if f":{port}" in line and "LISTENING" in line:
            pid = line.strip().split()[-1]
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)


def _wait_alive(url: str, label: str, timeout: float = 20.0) -> None:
    import httpx
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=1)
            if r.status_code < 500:
                print(f"  [{label}] {url} -> {r.status_code}")
                return
        except Exception as e:
            last_err = e
        time.sleep(0.5)
    raise RuntimeError(f"{label} not alive at {url}: {last_err}")


def start_servers() -> tuple[subprocess.Popen, subprocess.Popen]:
    """起 uvicorn + dev_server, 返回 (uvicorn_proc, web_proc). 不等 30s 启动."""
    _kill_port(BACKEND_PORT)
    _kill_port(WEB_PORT)
    db = ROOT / "data" / "topicpilot.db"
    if db.exists():
        db.unlink()

    uvicorn_log = open("/tmp/uvicorn_yolo.log", "w")
    uvicorn_proc = subprocess.Popen(
        [str(ROOT / ".venv/Scripts/python.exe"), "-m", "uvicorn", "app.main:app",
         "--app-dir", "apps/api", "--host", "127.0.0.1", "--port", str(BACKEND_PORT),
         "--log-level", "info"],
        cwd=str(ROOT), stdout=uvicorn_log, stderr=subprocess.STDOUT,
    )

    web_log = open("/tmp/web_yolo.log", "w")
    web_proc = subprocess.Popen(
        [str(ROOT / ".venv/Scripts/python.exe"), "dev_server.py"],
        cwd=str(ROOT / "apps/web"), stdout=web_log, stderr=subprocess.STDOUT,
    )

    _wait_alive(f"{API}/health", "backend")
    _wait_alive(f"{WEB}/", "web")
    return uvicorn_proc, web_proc


def stop_servers(uvicorn_proc: subprocess.Popen, web_proc: subprocess.Popen) -> None:
    for p in [uvicorn_proc, web_proc]:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            p.kill()


def load_subagent_case() -> dict:
    """读 data/yolo_subagent_result.json (SubAgent 真实输出)."""
    p = ROOT / "data" / "yolo_subagent_result.json"
    if not p.exists():
        raise FileNotFoundError(f"Missing {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def fill_form(page, case: dict) -> None:
    """填 Phase 01 表单. 默认表单已经预填 SubAgent 输出, 这里只确认."""
    page.wait_for_selector('input[name="case_id"]', timeout=5000)
    # 用 SubAgent 输出覆盖 (保证测试用例可重复)
    page.fill('input[name="case_id"]', case["case_id"])
    page.fill('input[name="advisor_direction"]', case["advisor_direction"])
    page.fill('textarea[name="raw_topic"]', case["raw_topic"])
    page.fill('input[name="must_keep"]', ", ".join(case["must_keep"]))
    # 选 goal_level
    page.select_option('select[name="goal_level"]', label=case["goal_level"])


def run_e2e(case: dict, screenshots_dir: Path) -> dict:
    """Playwright 真浏览器跑 8 phase, 返回 trace 事件统计."""
    from playwright.sync_api import sync_playwright
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    log: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("pageerror", lambda exc: log.append({"type": "pageerror", "detail": str(exc)}))
        page.on("console", lambda msg: log.append({"type": "console", "level": msg.type, "text": msg.text[:200]})
                if msg.type == "error" else None)

        page.goto(f"{WEB}/")
        page.wait_for_selector(".step-dot--active", timeout=10000)
        page.screenshot(path=str(screenshots_dir / "00_initial.png"), full_page=True)
        print(f"  [00] initial render OK")

        # Phase 01
        fill_form(page, case)
        page.click("#btn-primary")
        page.wait_for_selector(".phase-result", timeout=20000)
        time.sleep(1)
        page.screenshot(path=str(screenshots_dir / "01_phase01.png"), full_page=True)
        cls1 = page.locator('.step-dot[data-phase="1"]').get_attribute("class") or ""
        assert "step-dot--done" in cls1, f"Phase 01 not done: {cls1!r}"
        print(f"  [01] done: case_id={case['case_id']} rating={case['goal_level']}")

        # Phase 02-08
        for n in range(2, 9):
            nxt = page.locator('button:has-text("下一步")')
            if nxt.count() > 0:
                nxt.first.click()
                time.sleep(0.5)
            # 等 active
            for _ in range(30):
                cls = page.locator(f'.step-dot[data-phase="{n}"]').get_attribute("class") or ""
                if "step-dot--active" in cls:
                    break
                time.sleep(0.2)
            # primary
            page.click("#btn-primary")
            # 等 done (work_package LLM 路径可能 30-60s, 拉长 timeout)
            timeout_loops = 200 if n in (6, 7, 8) else 80
            for _ in range(timeout_loops):
                cls = page.locator(f'.step-dot[data-phase="{n}"]').get_attribute("class") or ""
                if "step-dot--done" in cls:
                    break
                time.sleep(0.5)
            page.screenshot(path=str(screenshots_dir / f"0{n}_phase{n:02d}.png"), full_page=True)
            cls = page.locator(f'.step-dot[data-phase="{n}"]').get_attribute("class") or ""
            assert "step-dot--done" in cls, f"Phase {n} not done: {cls!r}"
            print(f"  [0{n}] done")

            if n == 7:
                time.sleep(0.5)
                if page.locator("#btn-secondary").count() > 0:
                    page.click("#btn-secondary")
                    time.sleep(8)
                    page.screenshot(path=str(screenshots_dir / "07_committee.png"), full_page=True)
                    print(f"  [07+] committee done")

        # 收集 trace 统计
        trace_names = page.locator(".trace-item__name").all_text_contents()
        trace_details = page.locator(".trace-item__detail").all_text_contents()
        n_done = page.locator(".step-dot--done").count()
        n_trace = page.locator(".trace-item").count()

        # 验证关键 trace 事件
        trace_text = "\n".join(trace_details)
        has_arxiv = "arXiv" in trace_text or "arxiv" in trace_text.lower()
        has_3role = "supporter" in trace_text or "skeptic" in trace_text or "pragmatist" in trace_text

        print(f"  [stats] done={n_done} trace={n_trace} arxiv={has_arxiv} 3role={has_3role}")

        # Phase 04 卡片: 看 sidebar 关键字段
        # 切回 Phase 04 看 sidebar (需 navigate)
        if n_done >= 4:
            page.locator('.step-dot[data-phase="4"]').click()
            time.sleep(0.5)
            page.screenshot(path=str(screenshots_dir / "04_sidebar_arxiv.png"), full_page=True)
            sidebar_text = page.locator("#sidebar-fields").text_content() or ""
            print(f"  [04 sidebar] {sidebar_text[:200]}")

        # Phase 07 切回去看讨论气泡
        if n_done >= 7:
            page.locator('.step-dot[data-phase="7"]').click()
            time.sleep(0.5)
            page.screenshot(path=str(screenshots_dir / "07_sidebar_committee.png"), full_page=True)
            disc = page.locator(".discussion-bubble").count()
            print(f"  [07 sidebar] discussion-bubbles={disc}")

        browser.close()
        return {
            "n_done": n_done,
            "n_trace": n_trace,
            "has_arxiv": has_arxiv,
            "has_3role": has_3role,
            "trace_count_by_name": dict(
                (name, trace_names.count(name)) for name in set(trace_names)
            ),
        }


def main() -> int:
    print("=== TopicPilot-CN YOLO SubAgent 端到端验证 ===")
    case = load_subagent_case()
    print(f"📋 SubAgent case:")
    print(f"   case_id: {case['case_id']}")
    print(f"   raw_topic: {case['raw_topic']}")
    print(f"   must_keep: {case['must_keep']}")
    print(f"   advisor_direction: {case['advisor_direction']}")
    print(f"   goal_level: {case['goal_level']}")
    print()

    screenshots_dir = ROOT / "tmp" / "yolo_e2e"
    uvicorn_proc = web_proc = None
    try:
        print("🚀 启动服务器...")
        uvicorn_proc, web_proc = start_servers()
        time.sleep(1)

        print("🎭 Playwright 端到端...")
        stats = run_e2e(case, screenshots_dir)
        print()
        print("=== 📊 验证结果 ===")
        print(f"  ✅ done: {stats['n_done']}/8")
        print(f"  ✅ trace events: {stats['n_trace']}")
        print(f"  ✅ arXiv trace: {stats['has_arxiv']}")
        print(f"  ✅ 3 role discussion: {stats['has_3role']}")
        print(f"  📸 截图: {screenshots_dir}")

        # 断言
        assert stats["n_done"] == 8, f"expected 8 done, got {stats['n_done']}"
        assert stats["n_trace"] >= 30, f"expected ≥30 trace, got {stats['n_trace']}"
        assert stats["has_arxiv"], "no arXiv trace event"
        assert stats["has_3role"], "no 3-role discussion trace"
        print()
        print("✅ ALL ASSERTIONS PASSED")
        return 0
    except AssertionError as e:
        print(f"\n❌ ASSERTION FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        return 2
    finally:
        if uvicorn_proc or web_proc:
            print("🛑 关闭服务器...")
            stop_servers(uvicorn_proc, web_proc)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Stop hook: 阶段完工检查 + 编译/单测 + Playwright 自动化 (能跑就跑)。

不阻断 (exit 0)，输出提示到 stderr，让 Claude 在 Stop 时看到。

三件事：
1. 工作区状态 + Phase 报告覆盖检查 (原有)
2. 编译/单测: 若 .venv 可用 → 跑 pytest；否则提示如何补
3. Playwright 浏览器自动化: 若 playwright 模块 + apps/web 都就绪 → 提示可跑；否则明确说缺什么
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO / "Plan" / "reports"
APPS_DIR = REPO / "apps"


# ----------------------------- git helpers ----------------------------- #


def _git(*args: str, timeout: int = 10) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _git_diff_shortstat() -> str:
    return _git("diff", "--shortstat")


def _git_status_short() -> str:
    return _git("status", "--short")


def _git_log_recent(n: int = 5) -> str:
    return _git("log", f"-n{n}", "--oneline")


def _has_uncommitted_phase_work() -> bool:
    if not _git_diff_shortstat():
        return False
    diff_names = _git("diff", "--name-only", "HEAD")
    return any(p.startswith(("packages/", "apps/")) for p in diff_names.splitlines())


def _existing_phase_reports() -> set[str]:
    if not REPORTS_DIR.exists():
        return set()
    return {p.name for p in REPORTS_DIR.glob("Phase_*_*.md")}


def _extract_phase_numbers(commit_msgs: list[str]) -> set[str]:
    nums: set[str] = set()
    for m in commit_msgs:
        m = re.sub(r"^[0-9a-f]+\s+", "", m)
        m_match = re.match(r"Phase\s+(\d+)", m, re.IGNORECASE)
        if m_match:
            nums.add(m_match.group(1))
    return nums


# ----------------------------- environment probes ----------------------------- #


def _python_exe() -> str | None:
    """优先 venv 里的 python；否则系统 python3/python。"""

    candidates = [
        REPO / ".venv" / "Scripts" / "python.exe",
        REPO / ".venv" / "bin" / "python",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    for name in ("python", "python3", "py"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _pytest_available(py: str) -> bool:
    try:
        out = subprocess.check_output(
            [py, "-c", "import pytest; print(pytest.__version__)"],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return out.decode().strip().startswith(("7.", "8.", "9."))
    except Exception:
        return False


def _playwright_available(py: str) -> bool:
    try:
        out = subprocess.check_output(
            [py, "-c", "import playwright; print(playwright.__version__)"],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        return bool(out.decode().strip())
    except Exception:
        return False


def _apps_web_present() -> bool:
    web = APPS_DIR / "web"
    if not web.exists():
        return False
    return (web / "package.json").exists() or (web / "next.config.js").exists() or (web / "next.config.mjs").exists()


# ----------------------------- runners ----------------------------- #


def _run_pytest(py: str) -> tuple[bool, str]:
    """跑 pytest，输出 tail 到 stderr。返回 (ok, summary)。"""

    print("-" * 60, file=sys.stderr)
    print("[step] 编译/单测: uv run pytest", file=sys.stderr)
    try:
        proc = subprocess.run(
            [py, "-m", "pytest", "-q", "--tb=line"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print("[FAIL] pytest 超时 (>300s)", file=sys.stderr)
        return False, "timeout"
    except Exception as exc:
        print(f"[FAIL] pytest 启动失败: {exc}", file=sys.stderr)
        return False, "launch-error"

    tail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-15:]
    for line in tail:
        print(f"    {line}", file=sys.stderr)
    summary = "passed" if proc.returncode == 0 else f"failed (exit {proc.returncode})"
    return proc.returncode == 0, summary


def _probe_playwright(py: str) -> None:
    """探测 Playwright + apps/web 状态，给 Claude 明确指引。"""

    print("-" * 60, file=sys.stderr)
    print("[step] Playwright 浏览器自动化探测", file=sys.stderr)

    if not _apps_web_present():
        print("  [skip] apps/web 不存在 — 无浏览器页面可测", file=sys.stderr)
        print("  [how]  接入前端时:", file=sys.stderr)
        print("         mkdir apps/web", file=sys.stderr)
        print("         # Next.js 初始化或 React + Vite", file=sys.stderr)
        print("         # 把 .claude/hooks/playwright_smoke.py 拷到 apps/web/e2e/", file=sys.stderr)
        return

    if not _playwright_available(py):
        print("  [skip] playwright 模块未安装", file=sys.stderr)
        print("  [how]  uv pip install playwright pytest-playwright", file=sys.stderr)
        print("         uv run playwright install chromium", file=sys.stderr)
        return

    # 探测 uvicorn 是否运行
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:18181/health", timeout=2)
    except Exception:
        print("  [skip] uvicorn (18181) 未运行", file=sys.stderr)
        print("  [how]  另开终端:", file=sys.stderr)
        print("         .venv/Scripts/python.exe -m uvicorn app.main:app \\", file=sys.stderr)
        print("           --app-dir apps/api --port 18181", file=sys.stderr)
        return

    # 全部就绪 → 跑 playwright smoke
    print("  [ok] apps/web + playwright + uvicorn 全部就绪", file=sys.stderr)
    print("  [run] 启动 Playwright 浏览器 smoke", file=sys.stderr)
    try:
        proc = subprocess.run(
            [py, "-m", "pytest", "apps/web/e2e/", "-v", "--tb=short"],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=300,
        )
        tail = (proc.stdout + "\n" + proc.stderr).strip().splitlines()[-15:]
        for line in tail:
            print(f"    {line}", file=sys.stderr)
        if proc.returncode == 0:
            print("  [OK] Playwright smoke 通过", file=sys.stderr)
        else:
            print(f"  [FAIL] Playwright smoke 退出码 {proc.returncode}", file=sys.stderr)
    except Exception as exc:
        print(f"  [FAIL] 启动 playwright 失败: {exc}", file=sys.stderr)


# ----------------------------- main ----------------------------- #


def main() -> int:
    print("=" * 60, file=sys.stderr)
    print("[post_phase_check] TopicPilot-CN Stop hook", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # 1) 工作区 + Phase 报告检查
    if not _has_uncommitted_phase_work() and not _git_status_short():
        print("[ok] 无未提交改动", file=sys.stderr)
    else:
        recent = _git_log_recent(10).splitlines()
        committed_phases = _extract_phase_numbers(recent)
        reports = _existing_phase_reports()
        print(f"[info] 最近 commit 包含的 Phase: {sorted(committed_phases) or '∅'}",
              file=sys.stderr)
        print(f"[info] 现有报告: {sorted(reports) or '∅'}", file=sys.stderr)
        missing = []
        for p in sorted(committed_phases):
            candidates = [
                f"Phase_{int(p):02d}_完工报告.md",
                f"Phase_{int(p):02d}_Demo案例集报告.md",
            ]
            if not any(c in reports for c in candidates):
                missing.append(p)
        if missing:
            print(f"[WARN] Phase {missing} 已 commit 但缺少验收报告", file=sys.stderr)
        if _git_status_short():
            print("[WARN] 工作区有未提交改动:", file=sys.stderr)
            for line in _git_status_short().splitlines()[:20]:
                print(f"    {line}", file=sys.stderr)

    # 2) 编译/单测
    py = _python_exe()
    if py is None:
        print("-" * 60, file=sys.stderr)
        print("[skip] 找不到 python 解释器", file=sys.stderr)
    elif not _pytest_available(py):
        print("-" * 60, file=sys.stderr)
        print(f"[skip] pytest 不可用 ({py})", file=sys.stderr)
        print("  [how]  uv pip install pytest pytest-asyncio httpx", file=sys.stderr)
    else:
        ok, summary = _run_pytest(py)
        mark = "OK" if ok else "FAIL"
        print(f"[{mark}] pytest {summary}", file=sys.stderr)

    # 3) Playwright 探测
    if py is not None:
        _probe_playwright(py)

    print("=" * 60, file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

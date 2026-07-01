"""Playwright e2e config: 跳过慢速 / 跳过已存在的 dev server.

跑法:
    1. 起后端:  .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181
    2. 起前端:  .venv/Scripts/python.exe apps/web/dev_server.py
    3. 跑测试:  .venv/Scripts/python.exe -m pytest apps/web/e2e -v
"""

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
        repo_root = Path(__file__).resolve().parents[3]
        dev_server = repo_root / "apps" / "web" / "dev_server.py"
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


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1400, "height": 1400}}


@pytest.fixture()
def page(browser, context):
    p = context.new_page()
    p.goto(WEB_URL + "/")
    p.wait_for_selector("#btn-analyze", state="visible", timeout=15000)
    yield p
    p.close()


@pytest.fixture()
def page_with_result(page):
    """完成一次分析并等到 result-grid 出现 (含 5 区 + trace)."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=120000)
    return page

"""Session 59: react-web (18183) e2e conftest.

跑法:
    1. 起后端:  .venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181
    2. 起前端:  cd apps/web-react && npm run dev  (18183)
    3. 跑测试:  .venv/Scripts/python.exe -m pytest apps/web-react/e2e -v

跳过慢速: 后端/前端任意一个不可达, 整个 react-web 套件 skip.
"""

import os
import socket
import time
import urllib.request

import pytest


WEB_URL = os.environ.get("REACT_WEB_URL", "http://127.0.0.1:18183")
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

    if not _port_open("127.0.0.1", 18183):
        pytest.skip("React dev server (18183) 未运行")
    deadline = time.time() + 5
    while time.time() < deadline and not _http_alive(f"{WEB_URL}/"):
        time.sleep(0.2)
    if not _http_alive(f"{WEB_URL}/"):
        pytest.skip(f"{WEB_URL}/ 不可达")


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "viewport": {"width": 1440, "height": 900}}


@pytest.fixture()
def page(browser, context):
    p = context.new_page()
    yield p
    p.close()
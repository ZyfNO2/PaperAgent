"""apps/web/e2e/conftest.py — Playwright 浏览器 e2e fixtures.

依赖:
- playwright + chromium 二进制: ``uv pip install playwright pytest-playwright && uv run playwright install chromium``
- uvicorn 在 18181 端口运行
"""

from __future__ import annotations

import os
import socket
import time
import urllib.request
from pathlib import Path

import pytest


BASE_URL = os.environ.get("TOPICPILOT_E2E_BASE", "http://127.0.0.1:18181")
REPO = Path(__file__).resolve().parents[3]


def _is_alive(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def _require_uvicorn():
    """若 uvicorn 不可达, 整个 session 跳过。"""

    host, port = "127.0.0.1", 18181
    if not _port_open(host, port):
        pytest.skip(
            f"uvicorn 未运行在 {host}:{port}. "
            f"请先: .venv/Scripts/python.exe -m uvicorn app.main:app "
            f"--app-dir apps/api --host {host} --port {port}"
        )
    # 等 5s 等 uvicorn 启动
    deadline = time.time() + 5
    while time.time() < deadline and not _is_alive(f"{BASE_URL}/health"):
        time.sleep(0.2)
    if not _is_alive(f"{BASE_URL}/health"):
        pytest.skip(f"{BASE_URL}/health 不可达")

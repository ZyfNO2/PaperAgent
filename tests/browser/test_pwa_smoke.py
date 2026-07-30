from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.browser


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _wait_for_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    for _ in range(120):
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise AssertionError(f"PaperAgent server exited early:\n{output}")
        try:
            with urllib.request.urlopen(f"{base_url}/readyz", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("PaperAgent server did not become ready")


def test_pwa__submit_progress_review_and_export(tmp_path: Path) -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "paperagent",
            "serve",
            "--port",
            str(port),
            "--database",
            str(tmp_path / "browser.db"),
            "--demo-delay",
            "0.02",
            "--log-level",
            "warning",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        _wait_for_ready(base_url, process)
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            context = browser.new_context()
            page = context.new_page()
            console_errors: list[str] = []
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )

            page.add_init_script("sessionStorage.setItem('paperagent.intro.shown', '1')")
            page.goto(f"{base_url}/app", wait_until="networkidle")

            page.locator("#app-shell").wait_for(timeout=10_000)
            assert page.locator("#view-root").is_visible()
            assert page.locator("#page-title").text_content() == "总览"

            nav_items = page.locator(".nav-item")
            assert nav_items.count() >= 10

            page.locator('.nav-item[data-nav="literature"]').click()
            page.wait_for_url(f"{base_url}/app#/literature", timeout=5_000)
            cards = page.locator("article.paper-card")
            cards.first.wait_for(timeout=5_000)
            assert cards.count() >= 3

            page.locator('.nav-item[data-nav="evidence"]').click()
            page.wait_for_url(f"{base_url}/app#/evidence", timeout=5_000)
            evidence_cards = page.locator("article.evidence-card")
            evidence_cards.first.wait_for(timeout=5_000)
            assert evidence_cards.count() >= 1

            accept_buttons = page.locator(
                "article.evidence-card button:has-text('接受'):not([disabled])"
            )
            if accept_buttons.count() > 0:
                accept_buttons.first.click()
                page.locator("article.evidence-card button:has-text('已接受')").first.wait_for(
                    timeout=5_000
                )

            assert console_errors == []
            context.close()
            browser.close()
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

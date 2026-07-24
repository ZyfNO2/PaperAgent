from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any

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
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            console_errors: list[str] = []
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )

            page.goto(f"{base_url}/app", wait_until="networkidle")
            page.locator("#question").fill(
                "Verify the PaperAgent release candidate through the browser"
            )
            page.locator("#submit-button").click()
            page.wait_for_url(f"{base_url}/app/task_*", timeout=10_000)
            page.locator("#status-badge").get_by_text("succeeded", exact=True).wait_for(
                timeout=15_000
            )
            cards = page.locator("article.paper-card")
            assert cards.count() == 3

            first = cards.filter(has_text="Attention Is All You Need")
            first.get_by_role("button", name="接受").click()
            first.get_by_text("review: accepted", exact=True).wait_for(timeout=5_000)

            page.locator("#export-selection").select_option("accepted")
            with page.expect_download(timeout=5_000) as download_info:
                page.locator('.export-button[data-format="json"]').click()
            download = download_info.value
            export_path = tmp_path / download.suggested_filename
            download.save_as(export_path)
            payload: dict[str, Any] = json.loads(export_path.read_text(encoding="utf-8"))
            assert len(payload["papers"]) == 1
            assert payload["papers"][0]["paper_id"] == "demo-attention-2017"

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

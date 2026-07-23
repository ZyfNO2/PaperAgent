from __future__ import annotations

import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

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


def test_pwa__review_evidence_quality_gate_and_export(tmp_path: Path) -> None:
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
            page.get_by_role("button", name="跳过 →", exact=True).click()
            page.get_by_role("button", name="进入工作台 →", exact=True).click()
            expect(page.locator("#page-title")).to_have_text("总览")

            page.locator('[data-nav="literature"]').click()
            expect(page.locator("#page-title")).to_have_text("文献检索")
            paper_cards = page.locator("article.paper-card")
            expect(paper_cards.first).to_be_visible()
            initial_count = paper_cards.count()
            assert initial_count > 0

            keyword = page.get_by_role("searchbox", name="关键词")
            keyword.fill("stereo")
            search_button = page.get_by_role("button", name="检索", exact=True)
            search_button.click()
            expect(search_button).to_be_enabled(timeout=3_000)
            expect(paper_cards.first).to_be_visible()
            filtered_count = paper_cards.count()
            assert 0 < filtered_count <= initial_count

            page.locator('[data-nav="evidence"]').click()
            pending_card = page.locator("article.evidence-card").filter(has_text="待审阅").first
            expect(pending_card).to_be_visible()
            pending_card.get_by_role("button", name="接受", exact=True).click()
            expect(
                pending_card.get_by_role("button", name="已接受", exact=True)
            ).to_be_disabled()
            expect(page.locator("#toast-root")).to_contain_text("已接受")

            page.locator('[data-nav="gate"]').click()
            expect(page.locator(".gate-verdict")).to_contain_text("REVISE")
            page.get_by_role("button", name="触发复检", exact=True).click()
            expect(page.locator("#toast-root")).to_contain_text("复检任务已加入队列")

            page.locator('[data-nav="artifacts"]').click()
            first_artifact = page.locator(".artifact-row").first
            expect(first_artifact).to_be_visible()
            first_artifact.get_by_role("button", name="预览", exact=True).click()
            expect(page.locator("#modal-root")).to_contain_text("Demo 内容")
            page.get_by_role("button", name="关闭", exact=True).click()

            with page.expect_download(timeout=5_000) as download_info:
                first_artifact.get_by_role("button", name="下载", exact=True).click()
            download = download_info.value
            assert download.suggested_filename.endswith((".md", ".json", ".bib"))
            export_path = tmp_path / download.suggested_filename
            download.save_as(export_path)
            assert export_path.read_bytes()

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

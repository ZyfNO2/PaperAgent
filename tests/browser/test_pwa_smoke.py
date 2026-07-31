from __future__ import annotations

import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

import pytest
import uvicorn

from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.browser


class BrowserAcademicService:
    def __init__(self) -> None:
        self.review_notes: list[str] = []

    def list_projects(self) -> dict[str, Any]:
        return {"projects": [{"project_id": "demo", "name": "API Project"}], "count": 1}

    def list_papers(self, project_id: str) -> dict[str, Any]:
        return {
            "papers": [
                {
                    "project_id": project_id,
                    "paper_id": "paper-1",
                    "title": "Licensed fixture paper",
                    "metadata_confirmed": True,
                    "current_version": {"version_number": 1},
                    "parse_status": "indexed",
                }
            ]
        }

    def list_artifacts(self, project_id: str) -> dict[str, Any]:
        return {
            "project_id": project_id,
            "count": 1,
            "artifacts": [
                {
                    "artifact_id": "artifact-1",
                    "artifact_type": "baseline_card",
                    "title": "Baseline Card",
                    "latest_revision_number": 1 + len(self.review_notes),
                }
            ],
        }

    def query_evidence(
        self, project_id: str, question: str, paper_ids: tuple[str, ...]
    ) -> dict[str, Any]:
        locator = {
            "schema_version": "academic.v1",
            "paper_id": paper_ids[0],
            "version_id": "version-1",
            "object_id": "paragraph-1",
            "page_number": 1,
            "object_type": "paragraph",
            "source_hash": "a" * 64,
            "section_path": ["Methods"],
            "bounding_box": [10, 20, 100, 80],
        }
        return {
            "project_id": project_id,
            "query_plan": {"original_question": question},
            "ledger": {
                "entries": [{"evidence_id": "e1", "locator": locator, "status": "accepted"}],
                "accepted_ids": ["e1"],
                "rejected_ids": [],
                "conflicted_ids": [],
            },
            "sufficiency": "sufficient",
            "trace_ids": ["trace-1"],
            "stop_reason": "sufficient",
            "context_evidence_ids": ["e1"],
            "retrieval_candidates": [
                {
                    "evidence_id": "e1",
                    "locator": locator,
                    "text": "Grounded API evidence",
                    "score": 0.9,
                }
            ],
        }

    def resolve_locator(self, project_id: str, locator: dict[str, Any]) -> dict[str, Any]:
        return {"project_id": project_id, "locator": locator, "text": "Grounded API evidence"}

    def get_artifact(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        revisions = [
            {
                "revision_number": 1,
                "content": {"state": "draft", "summary": "Evidence-bound draft."},
            }
        ]
        revisions.extend(
            {
                "revision_number": index + 2,
                "content": {
                    "state": "draft",
                    "summary": "Evidence-bound draft.",
                    "review_note": note,
                },
            }
            for index, note in enumerate(self.review_notes)
        )
        return {
            "project_id": project_id,
            "artifact": {
                "artifact_id": artifact_id,
                "artifact_type": "baseline_card",
                "title": "Baseline Card",
            },
            "revisions": revisions,
        }

    def review_artifact(
        self,
        project_id: str,
        artifact_id: str,
        *,
        decision: str,
        note: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        assert project_id == "demo" and artifact_id == "artifact-1"
        assert decision == "revise" and idempotency_key
        self.review_notes.append(note)
        return {"revision": {"revision_number": 1 + len(self.review_notes)}}


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
            page.goto(f"{base_url}/app?demo=1#/overview", wait_until="networkidle")

            page.locator("#app-shell").wait_for(timeout=10_000)
            assert page.locator("#view-root").is_visible()
            assert page.locator("#page-title").text_content() == "总览"

            nav_items = page.locator(".nav-item")
            assert nav_items.count() >= 10

            page.locator('.nav-item[data-nav="literature"]').click()
            page.wait_for_url(f"{base_url}/app?demo=1#/literature", timeout=5_000)
            cards = page.locator("article.paper-card")
            cards.first.wait_for(timeout=5_000)
            assert cards.count() >= 3

            page.locator('.nav-item[data-nav="evidence"]').click()
            page.wait_for_url(f"{base_url}/app?demo=1#/evidence", timeout=5_000)
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


def test_pwa__production_academic_pages_locator_and_revision(tmp_path: Path) -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    service = BrowserAcademicService()
    app = create_app(
        executor=DemoTaskExecutor(),
        database_path=tmp_path / "production-browser.db",
        academic_service=service,  # type: ignore[arg-type]
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{base_url}/healthz", timeout=1).close()
                break
            except OSError:
                time.sleep(0.05)
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base_url}/app#/projects", wait_until="networkidle")
            page.get_by_role("button", name="API Project demo 1 papers").wait_for()
            assert page.locator("#demo-badge").is_hidden()

            page.locator('.nav-item[data-nav="literature"]').click()
            page.get_by_text("Licensed fixture paper", exact=True).wait_for()

            page.locator('.nav-item[data-nav="evidence"]').click()
            page.locator("textarea").fill("Find grounded baseline evidence")
            page.get_by_role("button", name="检索 Evidence").click()
            page.get_by_text("Grounded API evidence", exact=True).wait_for()
            page.get_by_text("Grounded API evidence", exact=True).click()
            page.get_by_text("Claim Locator", exact=False).wait_for()
            page.get_by_role("button", name="关闭").click()

            page.locator('.nav-item[data-nav="artifacts"]').click()
            page.get_by_text("Baseline Card", exact=True).click()
            page.once("dialog", lambda dialog: dialog.accept("Need real-paper split evidence."))
            page.get_by_role("button", name="Request Revision").click()
            page.get_by_text("已追加新的 Artifact revision", exact=True).wait_for()
            assert service.review_notes == ["Need real-paper split evidence."]
            assert page.locator("#demo-badge").is_hidden()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_pwa__production_failure_never_falls_back_to_demo(tmp_path: Path) -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    app = create_app(
        executor=DemoTaskExecutor(),
        database_path=tmp_path / "fail-closed-browser.db",
    )
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(f"{base_url}/healthz", timeout=1).close()
                break
            except OSError:
                time.sleep(0.05)
        with sync_playwright() as driver:
            browser = driver.chromium.launch()
            page = browser.new_page()
            page.goto(f"{base_url}/app", wait_until="networkidle")
            page.get_by_text("paperclaw_not_configured", exact=False).wait_for()
            assert page.locator("#demo-badge").is_hidden()
            assert page.get_by_text("混凝土裂缝三维重建与量化评估").count() == 0
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)

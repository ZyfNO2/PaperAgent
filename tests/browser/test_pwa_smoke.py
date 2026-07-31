from __future__ import annotations

import hashlib
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
import uvicorn
from fastapi.testclient import TestClient

from paperagent.academic.frontend_service import AcademicFrontendService
from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

pytestmark = pytest.mark.browser


class BrowserAcademicService:
    def __init__(self) -> None:
        self.review_notes: list[str] = []

    def list_projects(self) -> dict[str, Any]:
        return {
            "projects": [
                {"project_id": "demo", "name": "API Project"},
                {"project_id": "other", "name": "Isolated Project"},
            ],
            "count": 2,
        }

    def list_papers(self, project_id: str) -> dict[str, Any]:
        return {
            "papers": [
                {
                    "project_id": project_id,
                    "paper_id": f"paper-{project_id}",
                    "title": f"Licensed fixture paper {project_id}",
                    "metadata_confirmed": True,
                    "current_version": {"version_number": 1},
                    "parse_status": "indexed",
                }
            ]
        }

    def list_artifacts(self, project_id: str) -> dict[str, Any]:
        if project_id == "other":
            return {"project_id": project_id, "count": 0, "artifacts": []}
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
        content = b"fake-png-asset"
        return {
            "project_id": project_id,
            "locator": locator,
            "text": "Grounded API evidence",
            "assets": [{"sha256": hashlib.sha256(content).hexdigest(), "media_type": "image/png"}],
        }

    def read_asset(self, project_id: str, locator: dict[str, Any], asset_hash: str) -> bytes:
        del project_id, locator
        content = b"fake-png-asset"
        assert asset_hash == hashlib.sha256(content).hexdigest()
        return content

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


def _generated_pdf(path: Path, text: str) -> None:
    import fitz

    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(40, 40, 555, 780), text, fontsize=11)
    document.save(path)
    document.close()


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
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
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
            page.get_by_text("Licensed fixture paper demo", exact=True).wait_for()

            page.locator('.nav-item[data-nav="evidence"]').click()
            page.locator("textarea").fill("Find grounded baseline evidence")
            page.get_by_role("button", name="检索 Evidence").click()
            page.get_by_text("Grounded API evidence", exact=True).wait_for()
            page.get_by_text("Grounded API evidence", exact=True).click()
            page.get_by_text("Claim Locator", exact=False).wait_for()
            page.get_by_alt_text("Resolved page/region asset for e1").wait_for()
            page.get_by_role("button", name="关闭").click()

            page.locator('.nav-item[data-nav="artifacts"]').click()
            page.get_by_text("Baseline Card", exact=True).click()
            page.once("dialog", lambda dialog: dialog.accept("Need real-paper split evidence."))
            page.get_by_role("button", name="Request Revision").click()
            page.get_by_text("已追加新的 Artifact revision", exact=True).wait_for()
            assert service.review_notes == ["Need real-paper split evidence."]

            page.locator("#project-switcher").select_option("other")
            page.locator('.nav-item[data-nav="literature"]').click()
            page.get_by_text("Licensed fixture paper other", exact=True).wait_for()
            assert page.get_by_text("Licensed fixture paper demo", exact=True).count() == 0
            page.locator('.nav-item[data-nav="artifacts"]').click()
            page.get_by_text("暂无 Artifact", exact=True).wait_for()

            page.locator('.nav-item[data-nav="runs"]').click()
            page.get_by_label("Research task objective").fill("Verify isolated project run")
            page.get_by_role("button", name="Create Research Task").click()
            page.get_by_text("Verify isolated project run", exact=True).wait_for()
            page.get_by_text("Trace/task:", exact=False).wait_for()
            assert page.locator("#demo-badge").is_hidden()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_pwa__real_paperclaw_two_project_pdf_asset_and_artifact_loop(tmp_path: Path) -> None:
    from paperclaw.academic import AcademicRuntime
    from paperclaw.service.fastapi_app import create_app as create_paperclaw_app

    workspace_root = tmp_path / "paperclaw-projects"
    workspace_root.mkdir()
    paperclaw = TestClient(
        create_paperclaw_app(SimpleNamespace(), paper_workspace_roots=[workspace_root])
    )
    academic = AcademicFrontendService("http://paperclaw.test", client=cast(Any, paperclaw))
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    app = create_app(
        executor=DemoTaskExecutor(),
        database_path=tmp_path / "real-browser.db",
        academic_service=academic,
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
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
            page.locator("input[placeholder='项目名称']").fill("Project A")
            page.get_by_role("button", name="创建项目").click()
            page.get_by_role("button", name="Project A project-a 0 papers").wait_for()
            project_a = page.locator("#project-switcher").input_value()
            workspace_a = next(workspace_root.glob("project-*"))
            baseline = workspace_a / "baseline.pdf"
            module = workspace_a / "module.pdf"
            _generated_pdf(
                baseline,
                "Baseline Method\nFast stereo baseline uses supervised disparity loss. "
                "Dataset: Crack500 split: train. Limitation: reflective concrete surfaces.",
            )
            _generated_pdf(
                module,
                "Module Method\nEdge attention preserves crack boundaries. "
                "Dataset: Crack500 split: train. Compatibility requires aligned masks.",
            )

            page.locator('.nav-item[data-nav="literature"]').click()
            path_input = page.get_by_label("Server-local paper path import")
            for expected_count, pdf in enumerate((baseline, module), start=1):
                path_input.fill(str(pdf))
                page.get_by_role("button", name="Import Server-local PDF").click()
                page.wait_for_function(
                    "expected => document.querySelectorAll('tbody tr').length === expected",
                    arg=expected_count,
                )

            papers = academic.list_papers(project_a)["papers"]
            version = papers[0]["current_version"]["version_id"]
            parsed = AcademicRuntime(workspace_a, project_a).get_parse(
                papers[0]["paper_id"], version
            )
            page_object = next(item for item in parsed.objects if item.object_type == "page")
            assert page_object.assets
            asset_status = page.evaluate(
                """async ({projectId, locator, assetHash}) => {
                  const response = await fetch(`/v1/academic/projects/${projectId}/locator/asset`, {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({locator, asset_hash: assetHash})
                  });
                  return [response.status, (await response.arrayBuffer()).byteLength];
                }""",
                {
                    "projectId": project_a,
                    "locator": page_object.locator.to_dict(),
                    "assetHash": page_object.assets[0].asset_hash,
                },
            )
            assert asset_status[0] == 200 and asset_status[1] > 0

            page.locator('.nav-item[data-nav="evidence"]').click()
            page.locator("textarea").fill(
                "Compare baseline method and edge attention module on Crack500 train split"
            )
            page.get_by_role("button", name="检索 Evidence").click()
            page.get_by_role("button", name="生成八类 Evidence-bound Artifacts").wait_for()
            page.get_by_role("button", name="生成八类 Evidence-bound Artifacts").click()
            page.get_by_text("Artifact 草稿已写入", exact=False).wait_for()
            page.locator('.nav-item[data-nav="artifacts"]').click()
            page.locator("button.card").first.wait_for()
            assert page.locator("button.card").count() == 8

            page.locator('.nav-item[data-nav="projects"]').click()
            page.locator("input[placeholder='项目名称']").fill("Project B")
            page.get_by_role("button", name="创建项目").click()
            page.get_by_role("button", name="Project B project-b 0 papers").wait_for()
            page.locator('.nav-item[data-nav="literature"]').click()
            page.get_by_text("暂无论文", exact=True).wait_for()
            assert page.get_by_text("baseline.pdf", exact=True).count() == 0
            page.locator('.nav-item[data-nav="artifacts"]').click()
            page.get_by_text("暂无 Artifact", exact=True).wait_for()
            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
        paperclaw.close()


def test_pwa__production_failure_never_falls_back_to_demo(tmp_path: Path) -> None:
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    app = create_app(
        executor=DemoTaskExecutor(),
        database_path=tmp_path / "fail-closed-browser.db",
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
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

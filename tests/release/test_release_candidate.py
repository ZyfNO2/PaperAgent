from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from paperagent.api import create_app
from paperagent.cli import main
from paperagent.demo import DemoTaskExecutor
from paperagent.provider_smoke import ProviderSmokeSummary, run_provider_smoke
from paperagent.release import release_readiness


def _wait_for_success(client: TestClient, task_id: str) -> dict[str, Any]:
    for _ in range(200):
        payload = client.get(f"/v1/tasks/{task_id}").json()
        if payload["status"] == "succeeded":
            return payload
        if payload["status"] in {"failed", "cancelled"}:
            raise AssertionError(payload)
        time.sleep(0.01)
    raise AssertionError("demo task did not complete")


def test_release_app__full_demo_review_and_export_path(tmp_path: Path) -> None:
    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=tmp_path / "release.db",
        sse_poll_seconds=0.01,
    )
    with TestClient(app) as client:
        readiness = client.get("/readyz")
        assert readiness.status_code == 200
        assert readiness.json()["status"] == "ready"

        accepted = client.post(
            "/v1/tasks",
            headers={"Idempotency-Key": "release-demo"},
            json={"request": {"question": "Verify the release candidate end to end"}},
        )
        assert accepted.status_code == 202
        task_id = accepted.json()["task_id"]
        task = _wait_for_success(client, task_id)
        assert task["result"]["execution"]["mode"] == "deterministic_demo"
        assert "synthetic" in task["result"]["report"]["notice"].lower()

        events = client.get(f"/v1/tasks/{task_id}/events?after=0&limit=100").json()
        phases = [
            event["payload"].get("phase")
            for event in events["events"]
            if event["event_type"] == "workflow.progress"
        ]
        assert phases == [
            "normalize_request",
            "plan_demo_retrieval",
            "assemble_demo_evidence",
            "render_demo_report",
        ]

        cards = client.get(f"/v1/tasks/{task_id}/papers?limit=100").json()["items"]
        assert [card["paper_id"] for card in cards] == [
            "demo-attention-2017",
            "demo-deep-learning-2015",
            "demo-failed-verification",
        ]

        review = client.put(
            f"/v1/tasks/{task_id}/papers/demo-attention-2017/review",
            json={"decision": "accepted", "favorite": True, "expected_version": 0},
        )
        assert review.status_code == 200
        assert review.json()["version"] == 1
        replay = client.put(
            f"/v1/tasks/{task_id}/papers/demo-attention-2017/review",
            json={"decision": "accepted", "favorite": True, "expected_version": 1},
        )
        assert replay.json()["version"] == 1

        blocked = client.put(
            f"/v1/tasks/{task_id}/papers/demo-failed-verification/review",
            json={"decision": "accepted", "favorite": False, "expected_version": 0},
        )
        assert blocked.status_code == 422

        exported = client.get(f"/v1/tasks/{task_id}/exports/json?selection=all")
        assert exported.status_code == 200
        assert exported.headers["X-PaperAgent-Item-Count"] == "3"
        assert (
            exported.headers["X-PaperAgent-SHA256"] == hashlib.sha256(exported.content).hexdigest()
        )
        assert len(json.loads(exported.text)["papers"]) == 3


@pytest.mark.asyncio
async def test_demo_executor__cancellation_is_checked_before_work() -> None:
    emitted: list[str] = []

    async def emit(event_type: str, payload: dict[str, Any]) -> None:
        del payload
        emitted.append(event_type)

    from paperagent.api.executor import TaskCancelledError
    from paperagent.schemas.request import ResearchRequest

    with pytest.raises(TaskCancelledError):
        await DemoTaskExecutor(delay_seconds=0).execute(
            task_id="cancel-demo",
            request=ResearchRequest(question="Cancel the demo executor"),
            emit=emit,
            should_cancel=lambda: True,
        )
    assert emitted == []


def test_release_readiness__fails_closed_for_invalid_database_path(tmp_path: Path) -> None:
    snapshot = release_readiness(tmp_path)
    assert snapshot["status"] == "not_ready"
    assert snapshot["checks"]["sqlite"]["ok"] is False
    assert snapshot["checks"]["web_assets"]["ok"] is True


def test_cli__serve_is_localhost_first_and_invokes_uvicorn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(app: Any, *, host: str, port: int, log_level: str) -> None:
        captured.update(app=app, host=host, port=port, log_level=log_level)

    monkeypatch.setattr("paperagent.cli.uvicorn.run", fake_run)
    result = main(
        [
            "serve",
            "--database",
            str(tmp_path / "cli.db"),
            "--port",
            "8765",
            "--demo-delay",
            "0",
        ]
    )
    assert result == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["app"].version == "0.5.1"

    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--host", "0.0.0.0"])
    assert exc_info.value.code == 2


def test_cli__non_negative_float_rejects_negative() -> None:
    import argparse

    from paperagent.cli import _non_negative_float

    with pytest.raises(argparse.ArgumentTypeError, match="non-negative"):
        _non_negative_float("-1")


def test_cli__serve_rejects_invalid_port() -> None:
    from paperagent.cli import main

    with pytest.raises(SystemExit):
        main(["serve", "--port", "99999"])


def test_cli__llm_smoke_rejects_missing_key() -> None:
    from paperagent.cli import main

    with pytest.raises(SystemExit):
        main(["llm-smoke"])


def test_cli__provider_smoke_rejects_zero_timeout() -> None:
    from paperagent.cli import main

    with pytest.raises(SystemExit, match="greater than zero"):
        main(["provider-smoke", "--timeout", "0"])


def test_provider_smoke_summary_and_cli_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    passing = ProviderSmokeSummary(
        openalex="success",
        arxiv="success",
        crossref="verified",
        datacite="verified",
    )
    failing = ProviderSmokeSummary(
        openalex="timeout",
        arxiv="success",
        crossref="verified",
        datacite="verified",
    )
    assert passing.passed is True
    assert failing.passed is False

    async def fake_smoke(**_: Any) -> ProviderSmokeSummary:
        return passing

    monkeypatch.setattr("paperagent.cli.run_provider_smoke", fake_smoke)
    assert main(["provider-smoke", "--timeout", "1"]) == 0
    assert json.loads(capsys.readouterr().out)["passed"] is True


@pytest.mark.asyncio
async def test_provider_smoke_runner__normalizes_live_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRuntime:
        transport = object()

        def __init__(self) -> None:
            self.closed = False

        async def aclose(self) -> None:
            self.closed = True

    runtime = FakeRuntime()

    class FakeProvider:
        def __init__(self, **_: Any) -> None:
            pass

        async def search(self, **_: Any) -> SimpleNamespace:
            return SimpleNamespace(status="success")

    class FakeVerifier:
        def __init__(self, **_: Any) -> None:
            pass

        async def verify(self, _: Any) -> SimpleNamespace:
            return SimpleNamespace(status="verified")

    monkeypatch.setattr("paperagent.provider_smoke.build_literature_runtime", lambda _: runtime)
    monkeypatch.setattr("paperagent.provider_smoke.OpenAlexProvider", FakeProvider)
    monkeypatch.setattr("paperagent.provider_smoke.ArxivProvider", FakeProvider)
    monkeypatch.setattr("paperagent.provider_smoke.CrossrefVerifier", FakeVerifier)
    monkeypatch.setattr("paperagent.provider_smoke.DataCiteVerifier", FakeVerifier)

    summary = await run_provider_smoke(timeout_seconds=1)
    assert summary.passed is True
    assert runtime.closed is True

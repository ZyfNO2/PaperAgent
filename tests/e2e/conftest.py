"""End-to-end pytest fixtures: drive the real LangGraph workflow behind the
durable HTTP task contract via FakeLLM/FakeSearch providers.

These tests sit between the graph-level integration tests (``tests/graph``) and
the browser PWA smoke (``tests/browser``): they exercise the full
``/v1/tasks`` -> ``SingleProcessTaskRunner`` -> ``LangGraphTaskExecutor`` ->
``build_graph()`` -> SSE/events -> terminal state pipeline, but without a
browser or real LLM. Each scenario constructs its own ``RuntimeServices`` so the
graph routing can be steered toward happy_path / blocked / repair / timeout.

Shared utilities (fixture loaders, ``build_services``, assertion helpers) live
in ``helpers.py`` to avoid module-name collisions with other ``conftest``
modules when pytest collects across directories.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from helpers import TERMINAL_STATUSES, build_services, load_llm_raw

from paperagent.api import create_app
from paperagent.api.executor import LangGraphTaskExecutor
from paperagent.graph import build_graph

# Re-export load_llm_raw so that ``from conftest import load_llm_raw`` in other
# test directories (tests/graph, tests/nodes, tests/ood, tests/integration) keeps
# working when pytest loads this file as the top-level ``conftest`` module during
# cross-directory collection. The authoritative source remains tests/conftest.py.
__all__ = ["TERMINAL_STATUSES", "build_services", "load_llm_raw"]


@pytest.fixture
def graph_app_factory(tmp_path: Path):
    """Return a factory that builds a TestClient backed by the real LangGraph.

    The factory lets each E2E case customize the FakeLLM/FakeSearch fixtures and
    the LangGraph configurable (scenarios, budgets) so different graph paths can
    be exercised through the same durable HTTP contract.
    """
    created: list[TestClient] = []
    counter = {"n": 0}

    def _build(
        *,
        services: Any | None = None,
        configurable: Mapping[str, Any] | None = None,
        sse_poll_seconds: float = 0.01,
        sse_heartbeat_seconds: float = 5.0,
    ) -> TestClient:
        resolved_services = services or build_services()
        executor = LangGraphTaskExecutor(
            graph=build_graph(),
            services=resolved_services,
            configurable=dict(configurable or {}),
        )
        counter["n"] += 1
        app = create_app(
            executor=executor,
            database_path=tmp_path / f"e2e-{counter['n']}.db",
            sse_poll_seconds=sse_poll_seconds,
            sse_heartbeat_seconds=sse_heartbeat_seconds,
        )
        client = TestClient(app)
        created.append(client)
        return client

    yield _build

    for client in created:
        with contextlib.suppress(Exception):
            client.__exit__(None, None, None)


@pytest.fixture
def submit_task():
    def _submit(
        client: TestClient,
        *,
        question: str = "Evaluate citation reliability for a small RAG system",
        key: str = "e2e-key",
        metadata: dict[str, str] | None = None,
    ) -> str:
        body: dict[str, Any] = {"request": {"question": question}}
        if metadata:
            body["metadata"] = metadata
        response = client.post(
            "/v1/tasks",
            json=body,
            headers={"Idempotency-Key": key},
        )
        assert response.status_code == 202, response.text
        return response.json()["task_id"]

    return _submit


@pytest.fixture
def wait_for_terminal():
    def _wait(client: TestClient, task_id: str, *, timeout: float = 15.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = client.get(f"/v1/tasks/{task_id}").json()
            if last["status"] in TERMINAL_STATUSES:
                return last
            time.sleep(0.01)
        raise AssertionError(
            f"task {task_id} did not reach terminal state within {timeout}s; last={last}"
        )

    return _wait

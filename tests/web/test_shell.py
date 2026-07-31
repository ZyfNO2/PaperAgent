from __future__ import annotations

import json

from fastapi.testclient import TestClient

from paperagent.api import create_app


class NeverCalledExecutor:
    async def execute(self, **kwargs):
        raise AssertionError(f"executor must not be called by static shell tests: {kwargs}")


def test_web_shell__serves_index_and_task_routes_with_security_headers(tmp_path) -> None:
    app = create_app(executor=NeverCalledExecutor(), database_path=tmp_path / "tasks.db")

    with TestClient(app) as client:
        index = client.get("/app")
        task_route = client.get("/app/task_example")
        trailing = client.get("/app/")

    assert index.status_code == task_route.status_code == trailing.status_code == 200
    assert index.text == task_route.text == trailing.text
    assert "PaperAgent" in index.text
    assert 'id="view-root"' in index.text
    assert 'id="app-nav"' in index.text
    assert "/app-static/js/app.js" in index.text
    assert "/app-static/css/tokens.css" in index.text
    assert "cdn." not in index.text.lower()
    assert "default-src 'self'" in index.headers["content-security-policy"]
    assert index.headers["x-frame-options"] == "DENY"
    assert index.headers["cache-control"] == "no-store"


def test_web_shell__serves_manifest_worker_and_static_assets(tmp_path) -> None:
    app = create_app(executor=NeverCalledExecutor(), database_path=tmp_path / "tasks.db")

    with TestClient(app) as client:
        manifest_response = client.get("/app/manifest.webmanifest")
        worker = client.get("/app/service-worker.js")
        javascript = client.get("/app-static/js/app.js")
        academic_api = client.get("/app-static/js/api.js")
        academic_views = client.get("/app-static/js/views/academic.js")
        stylesheet = client.get("/app-static/css/tokens.css")
        icon = client.get("/app-static/icon.svg")

    manifest = manifest_response.json()
    assert manifest_response.status_code == 200
    assert manifest["start_url"] == "/app"
    assert manifest["scope"] == "/app"
    assert manifest["display"] == "standalone"
    assert worker.status_code == 200
    assert worker.headers["service-worker-allowed"] == "/app"
    assert "paperagent-shell-v1.1.0-academic-api" in worker.text
    assert "/v1" not in worker.text
    assert (
        javascript.status_code
        == academic_api.status_code
        == academic_views.status_code
        == stylesheet.status_code
        == icon.status_code
        == 200
    )
    assert javascript.headers["content-type"].startswith(
        ("text/javascript", "application/javascript")
    )
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert icon.headers["content-type"].startswith("image/svg+xml")


def test_web_shell__javascript_contract_covers_bounded_academic_api(tmp_path) -> None:
    app = create_app(executor=NeverCalledExecutor(), database_path=tmp_path / "tasks.db")

    with TestClient(app) as client:
        source = client.get("/app-static/js/app.js").text
        api_source = client.get("/app-static/js/api.js").text

    required_contracts = [
        "location.hash",
        "#/projects",
        "PA.views",
        "serviceWorker.register",
    ]
    for contract in required_contracts:
        assert contract in source
    assert "eval(" not in source
    assert "fetch(" not in source  # 网络边界集中在 PA.api
    assert "fetch(" in api_source
    assert "AbortController" in api_source
    assert "paperclaw_not_configured" in api_source
    assert "readAsset" in api_source
    assert "openai" not in source.lower()
    assert "semantic scholar" not in source.lower()


def test_web_shell__manifest_is_valid_json_and_routes_stay_out_of_openapi(tmp_path) -> None:
    app = create_app(executor=NeverCalledExecutor(), database_path=tmp_path / "tasks.db")

    with TestClient(app) as client:
        manifest_text = client.get("/app/manifest.webmanifest").text
        missing_nested_route = client.get("/app/task/with/slash")
        schema = client.get("/openapi.json").json()

    assert json.loads(manifest_text)["short_name"] == "PaperAgent"
    assert missing_nested_route.status_code == 404
    assert "/app" not in schema["paths"]
    assert "/app/manifest.webmanifest" not in schema["paths"]

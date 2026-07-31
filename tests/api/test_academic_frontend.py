from __future__ import annotations

import hashlib
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from paperagent.academic.artifacts import AcademicArtifactDraft
from paperagent.academic.frontend_service import (
    AcademicFrontendError,
    AcademicFrontendService,
    _RESTArtifactSink,
)
from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor


class StubAcademicService:
    def __init__(self) -> None:
        self.reviews: list[tuple[str, str, str, str]] = []

    def list_projects(self) -> dict[str, Any]:
        return {"projects": [{"project_id": "demo", "name": "Demo"}], "count": 1}

    def create_project(self, name: str) -> dict[str, Any]:
        return {"project": {"project_id": "created", "name": name}}

    def get_project(self, project_id: str) -> dict[str, Any]:
        return {"project": {"project_id": project_id, "name": "Demo"}}

    def list_papers(self, project_id: str) -> dict[str, Any]:
        return {"papers": [{"paper_id": "paper-1", "project_id": project_id}]}

    def import_paper(
        self, project_id: str, source_path: str, paper_id: str | None
    ) -> dict[str, Any]:
        return {
            "paper": {
                "paper_id": paper_id or "paper-imported",
                "project_id": project_id,
                "source_name": source_path.rsplit("/", 1)[-1],
            }
        }

    def parse_paper(self, project_id: str, paper_id: str) -> dict[str, Any]:
        return {"project_id": project_id, "paper_id": paper_id, "status": "parsed"}

    def build_index(self, project_id: str) -> dict[str, Any]:
        return {"project_id": project_id, "status": "ready"}

    def query_evidence(
        self, project_id: str, question: str, paper_ids: tuple[str, ...]
    ) -> dict[str, Any]:
        return {
            "project_id": project_id,
            "question": question,
            "paper_ids": list(paper_ids),
            "sufficiency": "insufficient",
            "stop_reason": "evidence_insufficient",
        }

    def resolve_locator(self, project_id: str, locator: dict[str, Any]) -> dict[str, Any]:
        return {"project_id": project_id, "locator": locator, "text": "resolved"}

    def read_asset(self, project_id: str, locator: dict[str, Any], asset_hash: str) -> bytes:
        assert project_id == "demo" and locator["object_id"] == "object-1"
        content = b"asset"
        assert hashlib.sha256(content).hexdigest() == asset_hash
        return content

    def create_tailoring_artifacts(self, project_id: str, **_: Any) -> dict[str, Any]:
        return {"project_id": project_id, "decision": "REVISE", "revisions": []}

    def list_artifacts(self, project_id: str) -> dict[str, Any]:
        return {"project_id": project_id, "artifacts": [], "count": 0}

    def get_artifact(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        return {"project_id": project_id, "artifact": {"artifact_id": artifact_id}}

    def review_artifact(
        self,
        project_id: str,
        artifact_id: str,
        *,
        decision: str,
        note: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        self.reviews.append((artifact_id, decision, note, idempotency_key))
        return {"revision": {"revision_number": 2}}


def test_academic_routes_fail_closed_without_paperclaw(tmp_path) -> None:
    app = create_app(executor=DemoTaskExecutor(), database_path=tmp_path / "db.sqlite")
    with TestClient(app) as client:
        capabilities = client.get("/v1/academic/capabilities").json()
        response = client.get("/v1/academic/projects")

    assert capabilities == {
        "schema_version": "academic.v1",
        "api_version": "paperagent-academic-frontend.v1",
        "paperclaw_configured": False,
        "demo_mode": False,
    }
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "paperclaw_not_configured"


def test_academic_routes_project_paper_evidence_and_review_projection(tmp_path) -> None:
    service = StubAcademicService()
    app = create_app(
        executor=DemoTaskExecutor(),
        database_path=tmp_path / "db.sqlite",
        academic_service=service,  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        assert client.get("/v1/academic/projects").json()["count"] == 1
        assert (
            client.post("/v1/academic/projects", json={"name": "New Study"}).json()["project"][
                "name"
            ]
            == "New Study"
        )
        assert (
            client.get("/v1/academic/projects/demo/papers").json()["papers"][0]["paper_id"]
            == "paper-1"
        )
        imported = client.post(
            "/v1/academic/projects/demo/papers/import",
            json={"source_path": "allowed/paper.pdf"},
        )
        assert imported.status_code == 201
        assert (
            client.post("/v1/academic/projects/demo/papers/paper-1/parse").json()["status"]
            == "parsed"
        )
        assert client.post("/v1/academic/projects/demo/index").json()["status"] == "ready"
        evidence = client.post(
            "/v1/academic/projects/demo/evidence/query",
            json={"question": "Find the baseline", "paper_ids": ["paper-1"]},
        ).json()
        assert evidence["sufficiency"] == "insufficient"
        locator = {"object_id": "object-1"}
        assert (
            client.post(
                "/v1/academic/projects/demo/locator/resolve", json={"locator": locator}
            ).json()["text"]
            == "resolved"
        )
        asset = b"asset"
        asset_hash = hashlib.sha256(asset).hexdigest()
        asset_response = client.post(
            "/v1/academic/projects/demo/locator/asset",
            json={"locator": locator, "asset_hash": asset_hash},
        )
        assert asset_response.content == asset
        assert (
            client.post(
                "/v1/academic/projects/demo/artifacts/generate",
                json={
                    "hypothesis": "Bounded hypothesis",
                    "baseline_paper_id": "paper-1",
                    "module_paper_ids": ["paper-2"],
                },
            ).json()["decision"]
            == "REVISE"
        )
        assert client.get("/v1/academic/projects/demo/artifacts").json()["count"] == 0
        assert (
            client.get("/v1/academic/projects/demo/artifacts/artifact-1").json()["artifact"][
                "artifact_id"
            ]
            == "artifact-1"
        )
        reviewed = client.post(
            "/v1/academic/projects/demo/artifacts/artifact-1/review",
            json={
                "decision": "revise",
                "note": "Need a split-specific citation.",
                "idempotency_key": "review-1",
            },
        )

    assert reviewed.status_code == 200
    assert service.reviews == [
        ("artifact-1", "revise", "Need a split-specific citation.", "review-1")
    ]


def test_frontend_service_returns_structured_upstream_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") is None
        return httpx.Response(
            409,
            json={"detail": {"code": "artifact_conflict", "message": "stale"}},
        )

    service = AcademicFrontendService(
        "http://paperclaw.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    try:
        service.list_projects()
    except AcademicFrontendError as exc:
        assert exc.code == "artifact_conflict"
        assert exc.status_code == 409
    else:  # pragma: no cover
        raise AssertionError("expected structured upstream error")


def test_frontend_service_proxies_lifecycle_and_validates_asset_hash() -> None:
    asset = b"png-asset"
    asset_hash = hashlib.sha256(asset).hexdigest()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/academic/asset"):
            return httpx.Response(200, content=asset)
        if path == "/v1/projects":
            return httpx.Response(200, json={"projects": [], "count": 0})
        if path.endswith("/papers"):
            return httpx.Response(200, json={"papers": []})
        if path.endswith("/parse"):
            return httpx.Response(200, json={"status": "parsed"})
        if path.endswith("/academic/index"):
            return httpx.Response(200, json={"status": "ready"})
        if path.endswith("/artifacts"):
            return httpx.Response(200, json={"artifacts": [], "count": 0})
        return httpx.Response(200, json={"project": {"project_id": "demo"}})

    service = AcademicFrontendService(
        "http://paperclaw.test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert service.list_projects()["count"] == 0
    assert service.get_project("demo")["project"]["project_id"] == "demo"
    assert service.list_papers("demo")["papers"] == []
    assert service.parse_paper("demo", "paper-1")["status"] == "parsed"
    assert service.build_index("demo")["status"] == "ready"
    assert service.list_artifacts("demo")["count"] == 0
    locator = {"object_id": "object-1", "bounding_box": [0, 0, 1, 1]}
    assert service.read_asset("demo", locator, asset_hash) == asset


class ArtifactRESTService:
    def __init__(self) -> None:
        self.reviewed = False

    def request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        assert method == "POST" and path.endswith("/artifacts")
        assert payload["draft"]["state"] == "draft"
        return {
            "artifact": {"artifact_id": "artifact-1"},
            "revision": {"revision_number": 1, "content_hash": "a" * 64},
        }

    def get_artifact(self, project_id: str, artifact_id: str) -> dict[str, Any]:
        return {"artifact": {"artifact_id": artifact_id, "artifact_type": "baseline_card"}}

    def review_artifact(self, *_: Any, **kwargs: Any) -> dict[str, Any]:
        assert kwargs["decision"] == "approved"
        self.reviewed = True
        return {"revision": {"revision_number": 2, "content_hash": "b" * 64}}


def test_rest_artifact_sink_validates_project_and_maps_revisions() -> None:
    service = ArtifactRESTService()
    sink = _RESTArtifactSink(service, "demo")  # type: ignore[arg-type]
    draft = AcademicArtifactDraft(
        artifact_type="baseline_card",
        title="Baseline",
        project_id="demo",
        summary="Evidence-scoped draft.",
        evidence_ids=("e1",),
        claims=(),
    )

    created = sink.create_draft(draft)
    assert created.revision_number == 1
    approved = sink.review("artifact-1", decision="approved", note="checked")
    assert approved.revision_number == 2
    assert service.reviewed is True

    uncached = _RESTArtifactSink(service, "demo")  # type: ignore[arg-type]
    assert uncached.review("artifact-1", decision="approved", note="checked").revision_number == 2
    try:
        sink.create_draft(draft.model_copy(update={"project_id": "other"}))
    except ValueError as exc:
        assert "project" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected project mismatch")
    try:
        sink.finalize("artifact-1")
    except ValueError as exc:
        assert "automatically finalize" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected bounded finalize failure")
    try:
        sink._mapping([], "artifact")
    except AcademicFrontendError as exc:
        assert exc.code == "paperclaw_malformed_response"
    else:  # pragma: no cover
        raise AssertionError("expected malformed response")


@pytest.mark.parametrize(
    ("url", "timeout"),
    [("file:///tmp/paperclaw", 1.0), ("http://paperclaw.test", 0.0), ("http://x", 61.0)],
)
def test_frontend_service_rejects_invalid_connection_bounds(url: str, timeout: float) -> None:
    with pytest.raises(ValueError):
        AcademicFrontendService(url, timeout_seconds=timeout)


@pytest.mark.parametrize(
    ("response", "expected_code"),
    [
        (httpx.Response(200, text="not-json"), "paperclaw_malformed_response"),
        (httpx.Response(200, json=[]), "paperclaw_malformed_response"),
        (httpx.Response(502, json={}), "paperclaw_upstream_failure"),
    ],
)
def test_frontend_service_rejects_malformed_upstream_responses(
    response: httpx.Response, expected_code: str
) -> None:
    service = AcademicFrontendService(
        "http://paperclaw.test",
        client=httpx.Client(transport=httpx.MockTransport(lambda _: response)),
    )
    with pytest.raises(AcademicFrontendError, match="PaperClaw") as caught:
        service.list_projects()
    assert caught.value.code == expected_code


def test_frontend_service_asset_failures_are_structured() -> None:
    service = AcademicFrontendService(
        "http://paperclaw.test",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(404, content=b"missing"))
        ),
    )
    with pytest.raises(AcademicFrontendError) as invalid:
        service.read_asset("demo", {}, "INVALID")
    assert invalid.value.code == "asset_hash_invalid"
    with pytest.raises(AcademicFrontendError) as rejected:
        service.read_asset("demo", {}, "a" * 64)
    assert rejected.value.code == "paperclaw_asset_failure"

    mismatch = AcademicFrontendService(
        "http://paperclaw.test",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"wrong"))
        ),
    )
    with pytest.raises(AcademicFrontendError) as corrupted:
        mismatch.read_asset("demo", {}, "a" * 64)
    assert corrupted.value.code == "paperclaw_asset_hash_mismatch"

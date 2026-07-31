from __future__ import annotations

from typing import Any

import httpx
from fastapi.testclient import TestClient

from paperagent.academic.frontend_service import (
    AcademicFrontendError,
    AcademicFrontendService,
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
        assert client.post(
            "/v1/academic/projects", json={"name": "New Study"}
        ).json()["project"]["name"] == "New Study"
        assert client.get("/v1/academic/projects/demo/papers").json()["papers"][0][
            "paper_id"
        ] == "paper-1"
        evidence = client.post(
            "/v1/academic/projects/demo/evidence/query",
            json={"question": "Find the baseline", "paper_ids": ["paper-1"]},
        ).json()
        assert evidence["sufficiency"] == "insufficient"
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

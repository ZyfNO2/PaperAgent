from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Annotated, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from paperagent.academic.frontend_service import (
    AcademicFrontendError,
    AcademicFrontendService,
)


class ProjectCreateBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class PaperImportBody(BaseModel):
    source_path: str = Field(min_length=1, max_length=4_096)
    paper_id: str | None = Field(default=None, max_length=200)


class EvidenceQueryBody(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    paper_ids: tuple[str, ...] = Field(default=(), max_length=100)


class TailoringBody(BaseModel):
    hypothesis: str = Field(min_length=1, max_length=10_000)
    baseline_paper_id: str = Field(min_length=1, max_length=200)
    module_paper_ids: tuple[str, ...] = Field(min_length=1, max_length=20)


class ArtifactReviewBody(BaseModel):
    decision: Literal["approved", "rejected", "revise"]
    note: str = Field(min_length=1, max_length=2_000)
    idempotency_key: str = Field(min_length=1, max_length=500)


class LocatorResolveBody(BaseModel):
    locator: dict[str, Any]


class LocatorAssetBody(BaseModel):
    locator: dict[str, Any]
    asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


def register_academic_routes(
    app: FastAPI,
    service: AcademicFrontendService | None,
) -> None:
    def available() -> AcademicFrontendService:
        if service is None:
            raise HTTPException(
                503,
                detail={
                    "code": "paperclaw_not_configured",
                    "message": "PaperClaw Academic API is not configured.",
                    "retryable": False,
                },
            )
        return service

    async def call(method: str, *args: object, **kwargs: object) -> Mapping[str, Any]:
        target = available()
        try:
            operation = getattr(target, method)
            return await asyncio.to_thread(operation, *args, **kwargs)
        except AcademicFrontendError as exc:
            raise HTTPException(
                exc.status_code,
                detail={"code": exc.code, "message": str(exc), "retryable": False},
            ) from exc

    @app.get("/v1/academic/capabilities")
    async def academic_capabilities() -> dict[str, object]:
        return {
            "schema_version": "academic.v1",
            "api_version": "paperagent-academic-frontend.v1",
            "paperclaw_configured": service is not None,
            "demo_mode": False,
        }

    @app.get("/v1/academic/projects")
    async def list_projects() -> Mapping[str, Any]:
        return await call("list_projects")

    @app.post("/v1/academic/projects", status_code=201)
    async def create_project(body: ProjectCreateBody) -> Mapping[str, Any]:
        return await call("create_project", body.name)

    @app.get("/v1/academic/projects/{project_id}")
    async def get_project(project_id: str) -> Mapping[str, Any]:
        return await call("get_project", project_id)

    @app.get("/v1/academic/projects/{project_id}/papers")
    async def list_papers(project_id: str) -> Mapping[str, Any]:
        return await call("list_papers", project_id)

    @app.post("/v1/academic/projects/{project_id}/papers/import", status_code=201)
    async def import_paper(project_id: str, body: PaperImportBody) -> Mapping[str, Any]:
        return await call("import_paper", project_id, body.source_path, body.paper_id)

    @app.post("/v1/academic/projects/{project_id}/papers/{paper_id}/parse")
    async def parse_paper(project_id: str, paper_id: str) -> Mapping[str, Any]:
        return await call("parse_paper", project_id, paper_id)

    @app.post("/v1/academic/projects/{project_id}/index")
    async def build_index(project_id: str) -> Mapping[str, Any]:
        return await call("build_index", project_id)

    @app.post("/v1/academic/projects/{project_id}/evidence/query")
    async def query_evidence(project_id: str, body: EvidenceQueryBody) -> Mapping[str, Any]:
        return await call("query_evidence", project_id, body.question, body.paper_ids)

    @app.post("/v1/academic/projects/{project_id}/locator/resolve")
    async def resolve_locator(project_id: str, body: LocatorResolveBody) -> Mapping[str, Any]:
        return await call("resolve_locator", project_id, body.locator)

    @app.post("/v1/academic/projects/{project_id}/locator/asset")
    async def read_locator_asset(project_id: str, body: LocatorAssetBody) -> Response:
        target = available()
        try:
            content = await asyncio.to_thread(
                target.read_asset, project_id, body.locator, body.asset_hash
            )
        except AcademicFrontendError as exc:
            raise HTTPException(
                exc.status_code,
                detail={"code": exc.code, "message": str(exc), "retryable": False},
            ) from exc
        return Response(
            content=content,
            media_type="image/png",
            headers={"ETag": f'"{body.asset_hash}"', "Cache-Control": "private, no-store"},
        )

    @app.post("/v1/academic/projects/{project_id}/artifacts/generate")
    async def generate_artifacts(project_id: str, body: TailoringBody) -> Mapping[str, Any]:
        return await call(
            "create_tailoring_artifacts",
            project_id,
            hypothesis=body.hypothesis,
            baseline_paper_id=body.baseline_paper_id,
            module_paper_ids=body.module_paper_ids,
        )

    @app.get("/v1/academic/projects/{project_id}/artifacts")
    async def list_artifacts(
        project_id: str,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> Mapping[str, Any]:
        del limit  # PaperClaw currently applies its own bounded default.
        return await call("list_artifacts", project_id)

    @app.get("/v1/academic/projects/{project_id}/artifacts/{artifact_id}")
    async def get_artifact(project_id: str, artifact_id: str) -> Mapping[str, Any]:
        return await call("get_artifact", project_id, artifact_id)

    @app.post("/v1/academic/projects/{project_id}/artifacts/{artifact_id}/review")
    async def review_artifact(
        project_id: str,
        artifact_id: str,
        body: ArtifactReviewBody,
    ) -> Mapping[str, Any]:
        return await call(
            "review_artifact",
            project_id,
            artifact_id,
            decision=body.decision,
            note=body.note,
            idempotency_key=body.idempotency_key,
        )

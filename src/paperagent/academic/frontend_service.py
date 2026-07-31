"""Bounded Application/API projection for the Academic RAG workbench.

PaperClaw remains the project, paper, locator and artifact persistence source.
This module only orchestrates PaperAgent's academic domain and projects public
PaperClaw REST responses for the browser.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Literal, cast

import httpx

from paperagent.academic.artifacts import (
    AcademicArtifactCoordinator,
    AcademicArtifactDraft,
    AcademicArtifactRevision,
    AcademicArtifactSink,
    AcademicArtifactType,
)
from paperagent.academic.paperclaw_rest import (
    PaperClawRESTError,
    PaperClawRetrievalRESTClient,
)
from paperagent.academic.workflow import AcademicRAGWorkflow


class AcademicFrontendError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class _RESTArtifactSink(AcademicArtifactSink):
    def __init__(self, service: AcademicFrontendService, project_id: str) -> None:
        self._service = service
        self._project_id = project_id
        self._types: dict[str, AcademicArtifactType] = {}

    def create_draft(self, draft: AcademicArtifactDraft) -> AcademicArtifactRevision:
        if draft.project_id != self._project_id:
            raise ValueError("artifact draft project does not match configured project")
        payload = draft.model_dump(mode="json")
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        raw = self._service.request(
            "POST",
            f"/v1/projects/{self._project_id}/artifacts",
            {
                "idempotency_key": f"paperagent-draft:{digest}",
                "artifact_type": draft.artifact_type,
                "title": draft.title,
                "draft": payload,
            },
        )
        artifact = self._mapping(raw.get("artifact"), "artifact")
        revision = self._mapping(raw.get("revision"), "revision")
        artifact_id = str(artifact.get("artifact_id", ""))
        self._types[artifact_id] = draft.artifact_type
        return self._revision(artifact_id, draft.artifact_type, "draft", revision)

    def review(
        self,
        artifact_id: str,
        *,
        decision: Literal["approved", "rejected"],
        note: str,
    ) -> AcademicArtifactRevision:
        artifact_type = self._types.get(artifact_id)
        if artifact_type is None:
            detail = self._service.get_artifact(self._project_id, artifact_id)
            artifact = self._mapping(detail.get("artifact"), "artifact")
            artifact_type = cast(AcademicArtifactType, artifact.get("artifact_type"))
        digest = hashlib.sha256(f"{artifact_id}:{decision}:{note}".encode()).hexdigest()
        raw = self._service.review_artifact(
            self._project_id,
            artifact_id,
            decision=decision,
            note=note,
            idempotency_key=f"paperagent-review:{digest}",
        )
        return self._revision(
            artifact_id,
            artifact_type,
            decision,
            self._mapping(raw.get("revision"), "revision"),
        )

    def finalize(self, artifact_id: str) -> AcademicArtifactRevision:
        raise ValueError("frontend approval does not automatically finalize artifacts")

    @staticmethod
    def _mapping(value: Any, label: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise AcademicFrontendError(
                "paperclaw_malformed_response", f"PaperClaw {label} is malformed"
            )
        return value

    @staticmethod
    def _revision(
        artifact_id: str,
        artifact_type: AcademicArtifactType,
        state: Literal["draft", "approved", "rejected", "final"],
        raw: Mapping[str, Any],
    ) -> AcademicArtifactRevision:
        return AcademicArtifactRevision(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            revision_number=int(raw["revision_number"]),
            state=state,
            content_hash=str(raw["content_hash"]),
        )


class AcademicFrontendService:
    """Fail-closed REST orchestrator used by PaperAgent's public API."""

    def __init__(
        self,
        paperclaw_base_url: str,
        *,
        timeout_seconds: float = 15.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not paperclaw_base_url.startswith(("http://", "https://")):
            raise ValueError("PaperClaw base URL must use http or https")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("PaperClaw timeout must be in (0, 60]")
        self._base_url = paperclaw_base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._client = client or httpx.Client(follow_redirects=False)

    def request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> Mapping[str, Any]:
        try:
            response = self._client.request(
                method,
                f"{self._base_url}{path}",
                json=payload,
                timeout=self._timeout,
            )
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise AcademicFrontendError(
                "paperclaw_timeout", "PaperClaw request timed out", status_code=504
            ) from exc
        except (httpx.TransportError, OSError) as exc:
            raise AcademicFrontendError(
                "paperclaw_unavailable", "PaperClaw is unavailable", status_code=503
            ) from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise AcademicFrontendError(
                "paperclaw_malformed_response", "PaperClaw returned non-JSON data"
            ) from exc
        if not isinstance(body, Mapping):
            raise AcademicFrontendError(
                "paperclaw_malformed_response", "PaperClaw response must be an object"
            )
        if not 200 <= response.status_code < 300:
            detail = body.get("detail")
            upstream = detail if isinstance(detail, Mapping) else {}
            code = str(upstream.get("code") or "paperclaw_upstream_failure")
            message = str(upstream.get("message") or "PaperClaw rejected the request")
            raise AcademicFrontendError(code, message[:500], status_code=response.status_code)
        return body

    def list_projects(self) -> Mapping[str, Any]:
        return self.request("GET", "/v1/projects")

    def create_project(self, name: str) -> Mapping[str, Any]:
        return self.request("POST", "/v1/projects", {"name": name})

    def get_project(self, project_id: str) -> Mapping[str, Any]:
        return self.request("GET", f"/v1/projects/{project_id}")

    def list_papers(self, project_id: str) -> Mapping[str, Any]:
        return self.request("GET", f"/v1/projects/{project_id}/papers")

    def import_paper(
        self, project_id: str, source_path: str, paper_id: str | None = None
    ) -> Mapping[str, Any]:
        payload: dict[str, Any] = {"source_path": source_path}
        if paper_id is not None:
            payload["paper_id"] = paper_id
        return self.request("POST", f"/v1/projects/{project_id}/papers/import", payload)

    def parse_paper(self, project_id: str, paper_id: str) -> Mapping[str, Any]:
        return self.request("POST", f"/v1/projects/{project_id}/papers/{paper_id}/parse")

    def build_index(self, project_id: str) -> Mapping[str, Any]:
        return self.request("POST", f"/v1/projects/{project_id}/academic/index")

    def query_evidence(
        self, project_id: str, question: str, paper_ids: tuple[str, ...]
    ) -> Mapping[str, Any]:
        source = PaperClawRetrievalRESTClient(
            self._base_url,
            project_id=project_id,
            timeout_seconds=self._timeout,
            max_retries=0,
            transport=cast(Any, self._client),
        )
        try:
            result = AcademicRAGWorkflow(source).run(
                project_id=project_id, question=question, paper_ids=paper_ids
            )
        except PaperClawRESTError as exc:
            raise AcademicFrontendError(exc.code, str(exc), status_code=502) from exc
        return result.model_dump(mode="json")

    def resolve_locator(
        self, project_id: str, locator: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        wire = dict(locator)
        bounding_box = wire.get("bounding_box")
        if isinstance(bounding_box, (list, tuple)) and len(bounding_box) == 4:
            wire["bounding_box"] = dict(
                zip(("x0", "y0", "x1", "y1"), bounding_box, strict=True)
            )
        return self.request(
            "POST",
            f"/v1/projects/{project_id}/academic/resolve",
            {"locator": wire},
        )

    def create_tailoring_artifacts(
        self,
        project_id: str,
        *,
        hypothesis: str,
        baseline_paper_id: str,
        module_paper_ids: tuple[str, ...],
    ) -> Mapping[str, Any]:
        source = PaperClawRetrievalRESTClient(
            self._base_url,
            project_id=project_id,
            timeout_seconds=self._timeout,
            max_retries=0,
            transport=cast(Any, self._client),
        )
        coordinator = AcademicArtifactCoordinator(
            AcademicRAGWorkflow(source), _RESTArtifactSink(self, project_id)
        )
        return coordinator.create_tailoring_drafts(
            project_id=project_id,
            hypothesis=hypothesis,
            baseline_paper_id=baseline_paper_id,
            module_paper_ids=module_paper_ids,
        ).model_dump(mode="json")

    def list_artifacts(self, project_id: str) -> Mapping[str, Any]:
        return self.request("GET", f"/v1/projects/{project_id}/artifacts")

    def get_artifact(self, project_id: str, artifact_id: str) -> Mapping[str, Any]:
        return self.request("GET", f"/v1/projects/{project_id}/artifacts/{artifact_id}")

    def review_artifact(
        self,
        project_id: str,
        artifact_id: str,
        *,
        decision: str,
        note: str,
        idempotency_key: str,
    ) -> Mapping[str, Any]:
        return self.request(
            "POST",
            f"/v1/projects/{project_id}/artifacts/{artifact_id}/review",
            {
                "idempotency_key": idempotency_key,
                "decision": decision,
                "note": note,
            },
        )

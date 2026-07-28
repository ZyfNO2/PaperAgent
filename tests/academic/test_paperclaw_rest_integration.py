from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytest.importorskip("paperclaw")

from fastapi.testclient import TestClient  # noqa: E402
from paperclaw.academic import AcademicObjectIndex, AcademicRuntime, RetrievalService  # noqa: E402
from paperclaw.papers import PaperImportRequest, PaperService  # noqa: E402
from paperclaw.projects import ProjectManifestStore  # noqa: E402
from paperclaw.service.fastapi_app import create_app  # noqa: E402

from paperagent.academic.contracts import (  # noqa: E402
    AcademicLocator,
    AcademicRetrievalRequest,
)
from paperagent.academic.paperclaw_adapter import (  # noqa: E402
    PaperClawAcademicEvidenceSource,
)
from paperagent.academic.paperclaw_rest import (  # noqa: E402
    PaperClawRetrievalRESTClient,
)


class _EmptyService:
    pass


def _request(project_id: str, paper_id: str) -> AcademicRetrievalRequest:
    return AcademicRetrievalRequest(
        project_id=project_id,
        query="dual encoder",
        original_question="Which method is used?",
        kind="method",
        round_kind="primary",
        channels=("lexical",),
        paper_ids=(paper_id,),
        object_types=("paragraph",),
    )


def test_real_pdf_python_and_rest_seams_have_identity_parity_after_restart(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    project = ProjectManifestStore(workspace).initialize("REST tracer")
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Method", fontsize=18)
    page.insert_text((72, 110), "The fracture detector uses a dual encoder.")
    source = workspace / "fixture.pdf"
    document.save(source)
    document.close()
    papers = PaperService.for_workspace(workspace, project_id=project.project_id)
    imported = papers.import_paper(PaperImportRequest(project.project_id, source))
    runtime = AcademicRuntime.for_workspace(workspace, project.project_id)
    parsed = runtime.parse_paper(imported.paper.paper_id)
    runtime.sync_index_version(imported.paper.paper_id, parsed.version_id)

    app_client = TestClient(create_app(_EmptyService(), paper_workspace_roots=[tmp_path]))
    rest = PaperClawRetrievalRESTClient(
        "http://testserver",
        project_id=project.project_id,
        transport=app_client,
    )
    openapi = app_client.get("/openapi.json").json()
    assert (
        openapi["components"]["schemas"]["EvidenceBundleWire"]["$ref"]
        == "#/components/schemas/AcademicV1Contract/$defs/evidence_bundle"
    )
    assert (
        openapi["paths"]["/v1/projects/{project_id}/academic/search"]["post"]["responses"]["200"][
            "content"
        ]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/RetrievalResponseWire"
    )
    request = _request(project.project_id, imported.paper.paper_id)
    python_result = PaperClawAcademicEvidenceSource(RetrievalService(runtime)).retrieve(request)
    rest_result = rest.retrieve(request)

    assert [item.locator for item in rest_result.candidates] == [
        item.locator for item in python_result.candidates
    ]
    assert rest_result.sufficiency == python_result.sufficiency

    page_object = next(item for item in parsed.objects if item.object_type == "page")
    locator_payload = page_object.locator.to_dict()
    bbox = locator_payload.get("bounding_box")
    if isinstance(bbox, dict):
        locator_payload["bounding_box"] = (
            bbox["x0"],
            bbox["y0"],
            bbox["x1"],
            bbox["y1"],
        )
    locator = AcademicLocator.model_validate(locator_payload)
    assert rest.resolve(locator).locator == locator
    asset_hash = page_object.assets[0].asset_hash
    png = rest.read_asset(project.project_id, locator, asset_hash)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert hashlib.sha256(png).hexdigest() == asset_hash

    restarted = PaperClawRetrievalRESTClient(
        "http://testserver",
        project_id=project.project_id,
        transport=TestClient(create_app(_EmptyService(), paper_workspace_roots=[tmp_path])),
    )
    repeated = restarted.retrieve(request)
    assert [item.locator for item in repeated.candidates] == [
        item.locator for item in rest_result.candidates
    ]

    revised = workspace / "fixture-v2.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "2 Revised Method", fontsize=18)
    page.insert_text((72, 110), "The revised detector uses sparse attention.")
    document.save(revised)
    document.close()
    imported_v2 = papers.import_paper(
        PaperImportRequest(
            project.project_id,
            revised,
            paper_id=imported.paper.paper_id,
        )
    )
    parsed_v2 = runtime.parse_paper(imported.paper.paper_id)
    runtime.sync_index_version(imported.paper.paper_id, parsed_v2.version_id)
    explicit_v1 = app_client.post(
        f"/v1/projects/{project.project_id}/academic/search",
        json={
            "query": "dual encoder",
            "channels": ["lexical"],
            "version_ids": [parsed.version_id],
        },
    )
    assert explicit_v1.json()["bundle"]["candidates"]

    AcademicObjectIndex(runtime).delete_version(imported.paper.paper_id, parsed.version_id)
    no_ghost = app_client.post(
        f"/v1/projects/{project.project_id}/academic/search",
        json={
            "query": "dual encoder",
            "channels": ["lexical"],
            "version_ids": [parsed.version_id],
        },
    )
    assert no_ghost.status_code == 200
    assert no_ghost.json()["bundle"]["candidates"] == []
    stale_locator = app_client.post(
        f"/v1/projects/{project.project_id}/academic/resolve",
        json={"locator": page_object.locator.to_dict()},
    )
    assert stale_locator.status_code == 404
    assert stale_locator.json()["detail"]["code"] == "academic_locator_not_found"
    assert imported_v2.version.version_id == parsed_v2.version_id

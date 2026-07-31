from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

fitz = pytest.importorskip("fitz")
pytest.importorskip("paperclaw")

from paperagent.academic.frontend_service import AcademicFrontendService  # noqa: E402
from paperclaw.service.fastapi_app import create_app as create_paperclaw_app  # noqa: E402


def _pdf(path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(50, 50, 545, 792), text, fontsize=11)
    document.save(path)
    document.close()


def test_generated_pdf_frontend_tracer_replays_locator_and_append_only_revision(
    tmp_path,
) -> None:
    paperclaw = TestClient(
        create_paperclaw_app(SimpleNamespace(), paper_workspace_roots=[tmp_path])
    )
    service = AcademicFrontendService(
        "http://testserver",
        client=cast(Any, paperclaw),
    )

    project = service.create_project("Frontend Tracer")["project"]
    project_id = str(project["project_id"])
    workspace = next(tmp_path.glob("project-*"))
    baseline_pdf = workspace / "baseline.pdf"
    module_pdf = workspace / "module.pdf"
    _pdf(
        baseline_pdf,
        "Baseline Method\nFast stereo matching baseline uses supervised disparity loss. "
        "Dataset: Crack500 split: train. Limitation: reflective concrete surfaces.",
    )
    _pdf(
        module_pdf,
        "Module Method\nEdge attention module preserves crack boundaries. "
        "Dataset: Crack500 split: train. Proposed compatibility requires mask alignment.",
    )

    baseline = service.import_paper(project_id, str(baseline_pdf))["paper"]
    module = service.import_paper(project_id, str(module_pdf))["paper"]
    for paper in (baseline, module):
        service.parse_paper(project_id, str(paper["paper_id"]))
    index = service.build_index(project_id)
    assert int(index["object_count"]) > 0

    evidence = service.query_evidence(
        project_id,
        "Compare baseline method and edge attention module on Crack500 train split",
        (str(baseline["paper_id"]), str(module["paper_id"])),
    )
    assert evidence["ledger"]["accepted_ids"]
    assert set(evidence["context_evidence_ids"]) <= set(
        evidence["ledger"]["accepted_ids"]
    )
    assert not set(evidence["context_evidence_ids"]) & set(
        evidence["ledger"]["rejected_ids"] + evidence["ledger"]["conflicted_ids"]
    )
    candidate = evidence["retrieval_candidates"][0]
    resolved = service.resolve_locator(project_id, candidate["locator"])
    assert resolved["locator"]["object_id"] == candidate["locator"]["object_id"]
    assert list(resolved["locator"]["bounding_box"].values()) == candidate["locator"][
        "bounding_box"
    ]
    assert resolved["text"]

    generated = service.create_tailoring_artifacts(
        project_id,
        hypothesis="Edge attention may preserve crack boundaries without changing the split.",
        baseline_paper_id=str(baseline["paper_id"]),
        module_paper_ids=(str(module["paper_id"]),),
    )
    assert generated["decision"] == "REVISE"
    assert {item["artifact_type"] for item in generated["revisions"]} >= {
        "evidence_bundle",
        "baseline_card",
        "compatibility_matrix",
        "experiment_matrix",
    }
    artifact_id = generated["revisions"][0]["artifact_id"]
    before = service.get_artifact(project_id, artifact_id)
    review = service.review_artifact(
        project_id,
        artifact_id,
        decision="revise",
        note="Generated-PDF control flow only; add licensed real-paper evidence.",
        idempotency_key="tracer-review-1",
    )
    after = service.get_artifact(project_id, artifact_id)

    assert review["revision"]["revision_number"] == 2
    assert [item["revision_number"] for item in before["revisions"]] == [1]
    assert [item["revision_number"] for item in after["revisions"]] == [1, 2]
    assert after["revisions"][1]["content"]["state"] == "draft"
    assert "Generated-PDF" in after["revisions"][1]["content"]["review_note"]

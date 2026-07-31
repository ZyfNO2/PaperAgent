from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paperagent.academic.frontend_service import AcademicFrontendService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the bounded PaperClaw -> PaperAgent frontend integration tracer."
    )
    parser.add_argument("--paperclaw-base-url", required=True)
    parser.add_argument("--baseline-pdf", type=Path, required=True)
    parser.add_argument("--module-pdf", type=Path, required=True)
    parser.add_argument("--project-name", default="Academic frontend tracer")
    parser.add_argument(
        "--hypothesis",
        default="The candidate module may address the baseline limitation under a fixed split.",
    )
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    for path in (args.baseline_pdf, args.module_pdf):
        if not path.is_file() or path.suffix.casefold() != ".pdf":
            raise ValueError(f"licensed/test PDF is unavailable: {path.name}")
    service = AcademicFrontendService(args.paperclaw_base_url)
    project = service.create_project(args.project_name)["project"]
    project_id = str(project["project_id"])
    papers = [
        service.import_paper(project_id, str(path.resolve()))["paper"]
        for path in (args.baseline_pdf, args.module_pdf)
    ]
    for paper in papers:
        service.parse_paper(project_id, str(paper["paper_id"]))
    index = service.build_index(project_id)
    evidence = service.query_evidence(
        project_id,
        args.hypothesis,
        tuple(str(paper["paper_id"]) for paper in papers),
    )
    generated = service.create_tailoring_artifacts(
        project_id,
        hypothesis=args.hypothesis,
        baseline_paper_id=str(papers[0]["paper_id"]),
        module_paper_ids=(str(papers[1]["paper_id"]),),
    )
    revisions = generated.get("revisions", [])
    reviewed: dict[str, Any] | None = None
    if revisions:
        artifact_id = str(revisions[0]["artifact_id"])
        reviewed = dict(
            service.review_artifact(
                project_id,
                artifact_id,
                decision="revise",
                note="Tracer verification only; scientific and human review remain pending.",
                idempotency_key=f"tracer-review:{artifact_id}",
            )
        )
        history = service.get_artifact(project_id, artifact_id)["revisions"]
        if [item["revision_number"] for item in history] != [1, 2]:
            raise RuntimeError("append-only artifact revision replay failed")
    accepted = set(evidence["ledger"]["accepted_ids"])
    if not set(evidence["context_evidence_ids"]) <= accepted:
        raise RuntimeError("generation context contains non-accepted evidence")
    return {
        "status": "engineering_control_flow_verified",
        "scientific_validation": "not_verified",
        "project_id": project_id,
        "paper_ids": [paper["paper_id"] for paper in papers],
        "index_generation_id": index.get("generation_id"),
        "accepted_evidence_count": len(accepted),
        "stop_reason": evidence["stop_reason"],
        "artifact_count": len(revisions),
        "review_revision": reviewed["revision"]["revision_number"] if reviewed else None,
    }


def main() -> int:
    args = build_parser().parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


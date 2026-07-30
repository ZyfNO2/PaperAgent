from __future__ import annotations

import argparse
import json
from pathlib import Path

from paperagent.projects.cli import configure_memory_rag_parser, run_memory_rag_cli


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    configure_memory_rag_parser(subparsers)
    return parser


def _run(parser: argparse.ArgumentParser, capsys, argv: list[str]) -> dict[str, object]:
    assert run_memory_rag_cli(parser.parse_args(argv)) == 0
    return json.loads(capsys.readouterr().out)


def test_academic_query_and_tailoring_cli_report_paperclaw_sync_state(
    tmp_path: Path,
    capsys,
) -> None:
    parser = _parser()
    database = tmp_path / "academic.sqlite"
    project = _run(
        parser,
        capsys,
        [
            "project-create",
            "--database",
            str(database),
            "--name",
            "Academic",
            "--question",
            "Can attention improve the baseline?",
        ],
    )
    project_id = str(project["project_id"])
    for paper_id, text in {
        "baseline": "Residual baseline architecture uses shortcut connections.",
        "module": "Channel attention module captures cross-channel interaction.",
    }.items():
        source = tmp_path / f"{paper_id}.md"
        source.write_text(f"# {paper_id}\n\n## Method\n{text}", encoding="utf-8")
        _run(
            parser,
            capsys,
            [
                "paper-ingest",
                "--database",
                str(database),
                "--project-id",
                project_id,
                "--paper-id",
                paper_id,
                "--file",
                str(source),
            ],
        )

    query = _run(
        parser,
        capsys,
        [
            "academic-query",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--query",
            "Explain the baseline method.",
            "--paper-id",
            "baseline",
        ],
    )
    assert query["ledger"]["accepted_ids"]
    assert query["paperclaw_sync"] == "pending"

    tailoring = _run(
        parser,
        capsys,
        [
            "academic-tailor",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--baseline-paper-id",
            "baseline",
            "--module-paper-id",
            "module",
            "--hypothesis",
            "Add channel attention to the residual baseline.",
        ],
    )
    assert tailoring["decision"] == "REVISE"
    assert len(tailoring["revisions"]) == 8
    assert tailoring["artifact_persistence"] == "in_memory_pending_paperclaw_sync"

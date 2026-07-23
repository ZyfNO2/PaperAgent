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


def test_project_create_and_ingest_cli(tmp_path: Path, capsys) -> None:
    parser = _parser()
    database = tmp_path / "db.sqlite"
    args = parser.parse_args(
        [
            "project-create",
            "--database",
            str(database),
            "--name",
            "Demo",
            "--question",
            "How does ECA change ResNet?",
        ]
    )
    assert run_memory_rag_cli(args) == 0
    project = json.loads(capsys.readouterr().out)

    paper = tmp_path / "paper.txt"
    paper.write_text("Channel attention improves image classification.", encoding="utf-8")
    ingest = parser.parse_args(
        [
            "paper-ingest",
            "--database",
            str(database),
            "--project-id",
            project["project_id"],
            "--paper-id",
            "eca",
            "--title",
            "ECA-Net",
            "--file",
            str(paper),
        ]
    )
    assert run_memory_rag_cli(ingest) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["paper"]["paper_id"] == "eca"
    assert payload["evidence_units"]


def test_non_memory_command_returns_none() -> None:
    args = argparse.Namespace(command="serve")
    assert run_memory_rag_cli(args) is None

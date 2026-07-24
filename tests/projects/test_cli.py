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


def _ingest(
    parser: argparse.ArgumentParser,
    capsys,
    *,
    database: Path,
    project_id: str,
    paper_id: str,
    title: str,
    path: Path,
) -> dict[str, object]:
    return _run(
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
            "--title",
            title,
            "--file",
            str(path),
        ],
    )


def test_project_create_and_ingest_cli(tmp_path: Path, capsys) -> None:
    parser = _parser()
    database = tmp_path / "db.sqlite"
    project = _run(
        parser,
        capsys,
        [
            "project-create",
            "--database",
            str(database),
            "--name",
            "Demo",
            "--question",
            "How does ECA change ResNet?",
        ],
    )

    paper = tmp_path / "paper.txt"
    paper.write_text("Channel attention improves image classification.", encoding="utf-8")
    payload = _ingest(
        parser,
        capsys,
        database=database,
        project_id=str(project["project_id"]),
        paper_id="eca",
        title="ECA-Net",
        path=paper,
    )
    assert payload["paper"]["paper_id"] == "eca"
    assert payload["evidence_units"]


def test_memory_rag_cli_query_memory_and_tailoring(tmp_path: Path, capsys) -> None:
    parser = _parser()
    database = tmp_path / "vertical.sqlite"
    project = _run(
        parser,
        capsys,
        [
            "project-create",
            "--database",
            str(database),
            "--name",
            "ResNet ECA mixup",
            "--question",
            "Can attention and mixup improve robustness?",
        ],
    )
    project_id = str(project["project_id"])

    sources = {
        "resnet": "Residual learning uses identity shortcut connections for classification.",
        "eca": "Efficient channel attention captures local cross-channel interaction.",
        "mixup": "Mixup trains on convex combinations and improves robustness.",
    }
    ingestions: dict[str, dict[str, object]] = {}
    for paper_id, text in sources.items():
        path = tmp_path / f"{paper_id}.md"
        path.write_text(f"# {paper_id}\n\n## Method\n{text}", encoding="utf-8")
        ingestions[paper_id] = _ingest(
            parser,
            capsys,
            database=database,
            project_id=project_id,
            paper_id=paper_id,
            title=paper_id.upper(),
            path=path,
        )

    query = _run(
        parser,
        capsys,
        [
            "rag-query",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--query",
            "channel attention robustness",
            "--limit",
            "5",
            "--paper-id",
            "eca",
            "--paper-id",
            "mixup",
        ],
    )
    assert {hit["unit"]["paper_id"] for hit in query["hits"]} == {"eca"}

    evidence_unit_id = ingestions["resnet"]["evidence_units"][0]["unit_id"]
    proposal = _run(
        parser,
        capsys,
        [
            "memory-propose",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--scope",
            "long_term",
            "--category",
            "decision",
            "--content",
            "Use ResNet as the frozen baseline.",
            "--evidence-unit-id",
            evidence_unit_id,
        ],
    )
    assert proposal["status"] == "proposed"

    reviewed = _run(
        parser,
        capsys,
        [
            "memory-review",
            "--database",
            str(database),
            "--memory-id",
            str(proposal["memory_id"]),
            "--approve",
            "--note",
            "Evidence checked.",
        ],
    )
    assert reviewed["status"] == "approved"

    memory = _run(
        parser,
        capsys,
        [
            "memory-show",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--include-pending",
        ],
    )
    assert [entry["content"] for entry in memory["memory"]] == [
        "Use ResNet as the frozen baseline."
    ]

    plan = _run(
        parser,
        capsys,
        [
            "tailor",
            "--database",
            str(database),
            "--project-id",
            project_id,
            "--baseline-paper-id",
            "resnet",
            "--module-paper-id",
            "eca",
            "--module-paper-id",
            "mixup",
            "--hypothesis",
            "Attention and mixup should improve robustness without changing the backbone contract.",
            "--evidence-query",
            "residual attention robustness",
        ],
    )
    assert plan["decision"] == "REVISE"
    assert {module["paper_id"] for module in plan["modules"]} == {"eca", "mixup"}
    assert plan["citations"]


def test_memory_rag_cli_reports_domain_errors(tmp_path: Path, capsys) -> None:
    parser = _parser()
    args = parser.parse_args(
        [
            "rag-query",
            "--database",
            str(tmp_path / "missing.sqlite"),
            "--project-id",
            "missing-project",
            "--query",
            "anything",
        ]
    )
    assert run_memory_rag_cli(args) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "ProjectNotFoundError"


def test_non_memory_command_returns_none() -> None:
    args = argparse.Namespace(command="serve")
    assert run_memory_rag_cli(args) is None

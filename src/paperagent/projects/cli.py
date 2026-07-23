from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, cast

from paperagent.projects.models import MemoryCategory, MemoryScope
from paperagent.projects.repository import (
    MemoryEntryNotFoundError,
    PaperNotFoundError,
    ProjectNotFoundError,
)
from paperagent.projects.workflow import MemoryRAGWorkflow

_COMMANDS = {
    "project-create",
    "paper-ingest",
    "rag-query",
    "memory-propose",
    "memory-review",
    "memory-show",
    "tailor",
}


def _database_default() -> Path:
    return Path(os.getenv("PAPERAGENT_DATABASE", "paperagent.db"))


def _add_database(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", type=Path, default=_database_default())


def configure_memory_rag_parser(subparsers: Any) -> None:
    project_create = subparsers.add_parser(
        "project-create", help="create a persistent research project"
    )
    _add_database(project_create)
    project_create.add_argument("--name", required=True)
    project_create.add_argument("--question", required=True)

    ingest = subparsers.add_parser(
        "paper-ingest", help="ingest a PDF, Markdown, or text paper into a project corpus"
    )
    _add_database(ingest)
    ingest.add_argument("--project-id", required=True)
    ingest.add_argument("--file", type=Path, required=True)
    ingest.add_argument("--title", default=None)
    ingest.add_argument("--paper-id", default=None)

    query = subparsers.add_parser(
        "rag-query", help="query project evidence with deterministic hybrid retrieval"
    )
    _add_database(query)
    query.add_argument("--project-id", required=True)
    query.add_argument("--query", required=True)
    query.add_argument("--limit", type=int, default=8)
    query.add_argument("--paper-id", action="append", default=[])

    memory_propose = subparsers.add_parser(
        "memory-propose", help="propose a gated project-memory write"
    )
    _add_database(memory_propose)
    memory_propose.add_argument("--project-id", required=True)
    memory_propose.add_argument(
        "--scope",
        choices=[item.value for item in MemoryScope],
        required=True,
    )
    memory_propose.add_argument(
        "--category", choices=[item.value for item in MemoryCategory], required=True
    )
    memory_propose.add_argument("--content", required=True)
    memory_propose.add_argument("--evidence-unit-id", action="append", default=[])

    memory_review = subparsers.add_parser(
        "memory-review", help="approve or reject a proposed project-memory write"
    )
    _add_database(memory_review)
    memory_review.add_argument("--memory-id", required=True)
    decision = memory_review.add_mutually_exclusive_group(required=True)
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    memory_review.add_argument("--note", default=None)

    memory_show = subparsers.add_parser(
        "memory-show", help="show approved project memory or include pending proposals"
    )
    _add_database(memory_show)
    memory_show.add_argument("--project-id", required=True)
    memory_show.add_argument("--include-pending", action="store_true")

    tailor = subparsers.add_parser(
        "tailor", help="produce an evidence-bound baseline and module design decision"
    )
    _add_database(tailor)
    tailor.add_argument("--project-id", required=True)
    tailor.add_argument("--baseline-paper-id", required=True)
    tailor.add_argument("--module-paper-id", action="append", default=[])
    tailor.add_argument("--hypothesis", required=True)
    tailor.add_argument("--evidence-query", default=None)


def run_memory_rag_cli(args: argparse.Namespace) -> int | None:
    command = cast(str, args.command)
    if command not in _COMMANDS:
        return None
    try:
        workflow = MemoryRAGWorkflow(cast(Path, args.database))
        if command == "project-create":
            result = workflow.create_project(
                name=cast(str, args.name),
                research_question=cast(str, args.question),
            )
            _print_json(result.model_dump(mode="json"))
            return 0
        if command == "paper-ingest":
            result = workflow.ingest_paper(
                project_id=cast(str, args.project_id),
                path=cast(Path, args.file),
                title=cast(str | None, args.title),
                paper_id=cast(str | None, args.paper_id),
            )
            _print_json(result.model_dump(mode="json"))
            return 0
        if command == "rag-query":
            hits = workflow.query(
                project_id=cast(str, args.project_id),
                query=cast(str, args.query),
                limit=cast(int, args.limit),
                paper_ids=cast(list[str], args.paper_id) or None,
            )
            _print_json({"hits": [hit.model_dump(mode="json") for hit in hits]})
            return 0
        if command == "memory-propose":
            result = workflow.propose_memory(
                project_id=cast(str, args.project_id),
                scope=MemoryScope(cast(str, args.scope)),
                category=MemoryCategory(cast(str, args.category)),
                content=cast(str, args.content),
                evidence_unit_ids=cast(list[str], args.evidence_unit_id),
            )
            _print_json(result.model_dump(mode="json"))
            return 0
        if command == "memory-review":
            result = workflow.review_memory(
                cast(str, args.memory_id),
                approve=cast(bool, args.approve),
                note=cast(str | None, args.note),
            )
            _print_json(result.model_dump(mode="json"))
            return 0
        if command == "memory-show":
            entries = workflow.repository.list_memory(
                cast(str, args.project_id),
                include_pending=cast(bool, args.include_pending),
            )
            _print_json({"memory": [entry.model_dump(mode="json") for entry in entries]})
            return 0
        if command == "tailor":
            result = workflow.design_tailoring_plan(
                project_id=cast(str, args.project_id),
                hypothesis=cast(str, args.hypothesis),
                baseline_paper_id=cast(str, args.baseline_paper_id),
                module_paper_ids=cast(list[str], args.module_paper_id),
                evidence_query=cast(str | None, args.evidence_query),
            )
            _print_json(result.model_dump(mode="json"))
            return 0 if result.decision.value in {"GO", "REVISE"} else 3
        raise RuntimeError(f"unhandled command: {command}")
    except (
        FileNotFoundError,
        MemoryEntryNotFoundError,
        OSError,
        PaperNotFoundError,
        ProjectNotFoundError,
        sqlite3.Error,
        ValueError,
    ) as exc:
        print(
            json.dumps(
                {"error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))

from __future__ import annotations

import json
from pathlib import Path

from paperagent.api import SQLiteTaskRepository
from paperagent.cli import main


def test_diagnostics_cli_prints_runtime_snapshot(tmp_path: Path, capsys: object) -> None:
    database = tmp_path / "paperagent.db"
    SQLiteTaskRepository(database)

    assert main(["diagnostics", "--database", str(database)]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)

    assert payload["service"] == "paperagent"
    assert payload["database"]["schema"]["current_version"] == 1
    assert payload["tasks"]["total"] == 0

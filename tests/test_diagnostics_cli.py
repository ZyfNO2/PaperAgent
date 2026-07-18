from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperagent.api import SQLiteReviewRepository, SQLiteTaskRepository
from paperagent.cli import main


def test_diagnostics_cli_prints_runtime_snapshot(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "paperagent.db"
    repository = SQLiteTaskRepository(database)
    SQLiteReviewRepository(repository)

    assert main(["diagnostics", "--database", str(database)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["service"] == "paperagent"
    assert payload["database"]["schema"]["current_version"] == 1
    assert payload["tasks"]["total"] == 0


def test_diagnostics_cli_reports_missing_database(tmp_path: Path) -> None:
    database = tmp_path / "missing.db"

    with pytest.raises(SystemExit, match="diagnostics failed: .* does not exist"):
        main(["diagnostics", "--database", str(database)])

    assert not database.exists()
